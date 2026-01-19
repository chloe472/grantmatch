"""
Service for integrating with OurSG Grants Portal
https://oursggrants.gov.sg/
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import urljoin
from .models import Grant, Agency
import asyncio
from playwright.async_api import async_playwright


class SGGrantsService:
    """Service to fetch and parse grants from OurSG Grants Portal"""
    
    BASE_URL = "https://oursggrants.gov.sg"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_grants(self):
        """
        Fetch grants from OurSG Grants Portal
        This method attempts to fetch grants via API or web scraping
        """
        grants_data = []
        
        try:
            # Try to fetch via API if available
            grants_data = self._fetch_via_api()
        except Exception as e:
            print(f"API fetch failed: {e}")
            # Fallback to web scraping
            try:
                grants_data = self._fetch_via_scraping()
            except Exception as e:
                print(f"Scraping failed: {e}")
        
        return grants_data
    
    def _fetch_via_api(self):
        """
        Fetch grants from OurSG Grants Portal API
        Uses the official API endpoint: /api/v1/grant_metadata/explore_grants
        """
        api_url = f"{self.BASE_URL}/api/v1/grant_metadata/explore_grants"
        response = self.session.get(api_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        grants_metadata = data.get('grant_metadata', [])
        
        grants_data = []
        for grant_meta in grants_metadata:
            # Skip inactive grants
            if grant_meta.get('active') != 'true' or grant_meta.get('enabled') != 'true':
                continue
            
            # Parse closing dates
            closing_dates = grant_meta.get('closing_dates', {})
            closing_date_str = None
            if isinstance(closing_dates, dict):
                # Get the first available closing date
                for key, value in closing_dates.items():
                    if value and value != "Open for Applications" and "closed" not in value.lower():
                        closing_date_str = value
                        break
                    elif value and "Open for Applications" in value:
                        # Keep as open, no specific date
                        closing_date_str = None
                        break
            
            # Parse funding amount
            grant_amount = grant_meta.get('grant_amount')
            funding_min, funding_max = None, None
            if grant_amount:
                funding_min, funding_max = self._parse_funding(grant_amount)
            
            # Determine status from API
            status = grant_meta.get('status', 'open')
            if status == 'green':
                grant_status = 'open'
            elif status == 'red' or 'closed' in str(closing_dates).lower():
                grant_status = 'closed'
            else:
                grant_status = 'open'
            
            # Build application URL
            grant_value = grant_meta.get('value', '')
            application_url = f"{self.BASE_URL}/grants/{grant_value}/instruction" if grant_value else ""
            
            # Build source URL
            source_url = application_url
            
            grant_data = {
                'external_id': grant_meta.get('id', ''),
                'title': grant_meta.get('name', ''),
                'description': grant_meta.get('desc', ''),
                'agency_name': grant_meta.get('agency_name', 'Unknown'),
                'agency_code': grant_meta.get('agency_code', ''),
                'closing_date': self._parse_date(closing_date_str) if closing_date_str else None,
                'closing_date_text': closing_date_str or "Open for Applications",
                'funding_min': funding_min,
                'funding_max': funding_max,
                'grant_amount_text': grant_amount,
                'application_url': application_url,
                'source_url': source_url,
                'status': grant_status,
                'applicable_to': grant_meta.get('applicable_to', []),
                'icon_name': grant_meta.get('agency_code', '').lower(),
            }
            
            grants_data.append(grant_data)
        
        return grants_data
    
    def fetch_grant_detail(self, grant_value=None, external_id=None):
        """
        Fetch detailed grant information from OurSG Grants Portal
        Uses Playwright to render JavaScript and extract real content
        """
        # First, fetch all grants to find the specific one
        all_grants = self._fetch_via_api()
        
        # Find the specific grant
        grant_detail = None
        for grant in all_grants:
            if grant_value and grant.get('application_url', '').endswith(f'/{grant_value}/instruction'):
                grant_detail = grant
                break
            elif external_id and grant.get('external_id') == external_id:
                grant_detail = grant
                break
        
        if not grant_detail:
            return None
        
        # Fetch real content from the instruction page using Playwright
        instruction_url = grant_detail.get('application_url', '')
        if instruction_url:
            try:
                page_content = self._fetch_instruction_page_with_playwright(instruction_url)
                if page_content:
                    grant_detail.update(page_content)
                    return grant_detail
            except Exception as e:
                print(f"Could not fetch detailed content with Playwright: {e}")
                # Fall back to basic formatting
        
        # Fallback: Use formatted data from API
        grant_detail['about_grant'] = grant_detail.get('description', '')
        grant_detail['who_can_apply'] = self._format_applicable_to(grant_detail) if grant_detail.get('applicable_to') else 'Please check the official grant page for eligibility criteria.'
        grant_detail['when_to_apply'] = self._format_closing_dates(grant_detail.get('closing_date_text', ''))
        grant_detail['funding_info'] = self._format_funding(grant_detail.get('funding_min'), grant_detail.get('funding_max'), grant_detail.get('grant_amount_text', ''))
        grant_detail['how_to_apply'] = grant_detail.get('how_to_apply_html', 'Please visit the official OurSG Grants Portal for detailed application instructions.')
        grant_detail['required_documents'] = 'Please refer to the official grant page for required supporting documents.'
        grant_detail['document_links'] = [
            {
                'name': 'View Required Documents on OurSG',
                'url': instruction_url,
                'size': 'External Link'
            }
        ]
        
        return grant_detail
    
    def _fetch_instruction_page_with_playwright(self, instruction_url):
        """
        Use Playwright to fetch and parse the instruction page
        Extracts real content from the rendered JavaScript page
        """
        try:
            # Run the async function to fetch and parse
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._async_fetch_instruction_page(instruction_url))
            loop.close()
            return result
        except Exception as e:
            print(f"Error in Playwright fetch: {e}")
            return None
    
    async def _async_fetch_instruction_page(self, instruction_url):
        """
        Async function to fetch instruction page with Playwright
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                await page.goto(instruction_url, wait_until="load", timeout=60000)
                await page.wait_for_timeout(3000)  # Wait for dynamic content
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract content sections
                extracted_data = self._extract_grant_sections(soup)
                
                return extracted_data
                
            finally:
                await context.close()
                await browser.close()
    
    def _extract_grant_sections(self, soup):
        """
        Extract grant sections from the rendered HTML
        """
        # Get all text lines that are meaningful
        all_text = soup.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip() and len(line.strip()) > 10]
        
        # Join to get full text
        full_text = '\n'.join(lines)
        
        extracted = {
            'about_grant': self._extract_section_text(full_text, ['about this grant', 'the aim']),
            'who_can_apply': self._extract_section_text(full_text, ['who can apply', 'eligibility', 'who is eligible']),
            'when_to_apply': self._extract_section_text(full_text, ['when to apply', 'when can i apply', 'application is open', 'application timeline']),
            'funding_info': self._extract_section_text(full_text, ['how much funding', 'funding amount', 'grant amount', 'up to s$']),
            'how_to_apply': self._extract_section_text(full_text, ['how to apply', 'completing the grant', 'application process']),
            'required_documents': self._extract_section_text(full_text, ['documents required', 'required documents', 'supporting documents']),
            'document_links': self._extract_document_links(soup)
        }
        
        return extracted
    
    def _extract_section_text(self, full_text, keywords):
        """
        Extract text content for a specific section using keywords
        """
        for keyword in keywords:
            idx = full_text.lower().find(keyword.lower())
            if idx != -1:
                # Get content from this keyword onwards (next 600 chars)
                section_start = idx
                section_end = min(len(full_text), idx + 600)
                section_text = full_text[section_start:section_end]
                
                # Split into lines
                lines = section_text.split('\n')
                
                # Build result, stopping at next section heading
                result_lines = []
                seen_keyword = False
                
                for line in lines:
                    # Stop if we detect a new section heading
                    section_headings = ['who can apply', 'when to apply', 'how much funding', 'how to apply', 'documents required', 'about this grant', 'apply as']
                    
                    clean_line = line.strip()
                    
                    # Skip empty lines
                    if not clean_line or len(clean_line) < 5 or 'javascript' in clean_line.lower():
                        continue
                    
                    # Skip the duplicate keyword line at the start
                    if not seen_keyword and any(kw.lower() in clean_line.lower() for kw in keywords):
                        seen_keyword = True
                        continue
                    
                    # Stop if we hit a different section heading
                    if any(h in clean_line.lower() for h in section_headings):
                        if not any(kw.lower() in clean_line.lower() for kw in keywords):
                            if len(result_lines) > 2:  # Make sure we have content
                                break
                    
                    result_lines.append(clean_line)
                
                # Return the result
                if result_lines:
                    return '\n'.join(result_lines[:12])  # Limit to 12 lines
        
        return ''
    
    def _extract_document_links(self, soup):
        """
        Extract document links from the instruction page
        """
        links = []
        
        # Find all links that might be documents
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Look for file extensions or download patterns
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xlsx', '.xls', '.zip']) or 'download' in text.lower():
                # Try to extract file size if present
                size = ''
                # Look for parenthetical content like (DOCX 256 KB)
                size_match = re.search(r'\(([^)]+)\)', text)
                if size_match:
                    size = size_match.group(1)
                
                # Clean file name
                clean_name = re.sub(r'\s*\([^)]+\)', '', text).strip()
                
                # Make absolute URL if relative
                if href and not href.startswith('http'):
                    href = urljoin(self.BASE_URL, href)
                
                links.append({
                    'name': clean_name or text[:50],
                    'url': href,
                    'size': size
                })
        
        return links
    
    def _format_applicable_to(self, grant_detail):
        """Format the applicable_to field into readable text"""
        applicable = grant_detail.get('applicable_to', [])
        if not applicable:
            return 'Please check the official grant page for eligibility criteria.'
        
        # Capitalize and join
        formatted = ', '.join([item.capitalize() for item in applicable])
        return f"This grant is applicable to: {formatted}. Please check the official OurSG Grants Portal for detailed eligibility criteria."
    
    def _format_closing_dates(self, closing_date_text):
        """Format closing date information"""
        if not closing_date_text or closing_date_text == "Open for Applications":
            return "This grant is currently open for applications. Check the OurSG Grants Portal for the latest deadline information."
        return f"Application deadline: {closing_date_text}. Please visit the OurSG Grants Portal for more details."
    
    def _format_funding(self, funding_min, funding_max, grant_amount_text):
        """Format funding information"""
        if funding_min and funding_max:
            return f"Funding available: SGD {funding_min:,.0f}K to SGD {funding_max:,.0f}K. {grant_amount_text or 'Check the official grant page for more details.'}"
        elif funding_max:
            return f"Maximum funding: SGD {funding_max:,.0f}K. {grant_amount_text or 'Check the official grant page for more details.'}"
        elif grant_amount_text:
            return f"Funding information: {grant_amount_text}"
        else:
            return "Please check the OurSG Grants Portal for funding details."
    
    def _fetch_grant_instruction_page(self, instruction_url):
        """
        Fetch detailed grant information from the instruction page
        Note: The OurSG instruction pages are JavaScript-rendered, so direct scraping is limited
        We'll attempt to extract what we can and fall back to API data
        """
        try:
            response = self.session.get(instruction_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            additional_data = {}
            
            # Since the pages are JavaScript-rendered, we'll have limited content
            # But we'll try to extract any statically available data
            
            # Look for any pre-rendered JSON data
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    # Check if this contains grant information
                    if 'about' in str(data).lower() or 'eligibility' in str(data).lower():
                        additional_data.update(data)
                except:
                    pass
            
            return additional_data
        except Exception as e:
            print(f"Error fetching instruction page: {e}")
            return {}
    
    def _extract_section_by_heading(self, soup, headings):
        """
        Extract text content following a specific heading
        """
        for heading_text in headings:
            # Find heading by text (case insensitive) - can be in various tags
            heading = None
            
            # Try to find as direct text node
            for text_node in soup.find_all(string=re.compile(rf'{re.escape(heading_text)}', re.I)):
                # Check if it's a heading or strong text
                parent = text_node.find_parent(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'p'])
                if parent:
                    heading = parent
                    break
            
            # If not found, try finding by tag with text
            if not heading:
                for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'p']:
                    heading = soup.find(tag, string=re.compile(rf'{re.escape(heading_text)}', re.I))
                    if heading:
                        break
            
            if heading:
                # Collect all following content until next heading
                texts = []
                current = heading
                
                # Get all following siblings
                for sibling in current.next_siblings:
                    if hasattr(sibling, 'name'):
                        # Stop if we hit another major heading
                        if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                            sibling_text = sibling.get_text(strip=True)
                            # Check if it's another section heading
                            if any(h.lower() in sibling_text.lower() for h in ['Who Can Apply', 'When to Apply', 'How much', 'How to apply', 'Documents']):
                                break
                        
                        # Get text from this element
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 10:  # Only meaningful text
                            # Skip if it's another heading
                            if not any(h.lower() in text.lower() for h in ['Who Can Apply', 'When to Apply', 'How much', 'How to apply', 'Documents Required']):
                                texts.append(text)
                    elif isinstance(sibling, str):
                        text = sibling.strip()
                        if text and len(text) > 10:
                            texts.append(text)
                
                # Also check parent's following siblings if heading is in a paragraph
                if heading.name == 'p':
                    parent = heading.find_parent(['div', 'section'])
                    if parent:
                        for sibling in parent.next_siblings:
                            if hasattr(sibling, 'name'):
                                if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                                    break
                                text = sibling.get_text(strip=True)
                                if text and len(text) > 10:
                                    texts.append(text)
                
                if texts:
                    # Clean up and join
                    cleaned_texts = []
                    for text in texts[:15]:  # Limit to 15 paragraphs
                        # Remove very short texts
                        if len(text) > 20:
                            cleaned_texts.append(text)
                    
                    if cleaned_texts:
                        return '\n\n'.join(cleaned_texts)
        
        return None
    
    def _extract_documents_section(self, soup):
        """
        Extract documents section with download links
        Returns dict with 'text' and 'links' (list of dicts with 'name', 'url', 'size')
        """
        documents_data = {'text': '', 'links': []}
        
        # Find documents section heading
        doc_headings = ['Documents Required', 'Required Documents', 'DOCUMENTS REQUIRED FOR APPLICATION']
        heading = None
        
        for heading_text in doc_headings:
            for text_node in soup.find_all(string=re.compile(rf'{re.escape(heading_text)}', re.I)):
                parent = text_node.find_parent(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'p', 'div'])
                if parent:
                    heading = parent
                    break
            if heading:
                break
        
        if heading:
            # Get text content
            section_text = []
            current = heading
            
            # Find all links in the section
            section = heading.find_parent(['div', 'section']) or heading
            links = section.find_all('a', href=True)
            
            for link in links:
                link_text = link.get_text(strip=True)
                link_url = link.get('href', '')
                # Make absolute URL if relative
                if link_url and not link_url.startswith('http'):
                    link_url = urljoin(self.BASE_URL, link_url)
                
                # Try to extract file size from text (e.g., "file.pdf (PDF 1.2 MB)")
                size_match = re.search(r'\(([^)]+)\)', link_text)
                file_size = size_match.group(1) if size_match else ''
                
                # Extract file name (remove size info)
                file_name = re.sub(r'\s*\([^)]+\)', '', link_text).strip()
                
                documents_data['links'].append({
                    'name': file_name,
                    'url': link_url,
                    'size': file_size
                })
            
            # Get section text
            for sibling in heading.next_siblings:
                if hasattr(sibling, 'name'):
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        break
                    text = sibling.get_text(strip=True)
                    if text:
                        section_text.append(text)
                elif isinstance(sibling, str):
                    text = sibling.strip()
                    if text:
                        section_text.append(text)
            
            documents_data['text'] = '\n'.join(section_text)
        
        return documents_data
    
    def _fetch_via_scraping(self):
        """
        Scrape grants from OurSG Grants Portal website
        Note: This should be used responsibly and in compliance with terms of service
        Note: The OurSG Grants Portal uses an API, so scraping is not the primary method
        """
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 is required for web scraping. Install it with: pip install beautifulsoup4")
        
        grants_data = []
        
        try:
            # Try the main page first
            urls_to_try = [
                f"{self.BASE_URL}",
                f"{self.BASE_URL}/explore",
            ]
            
            for url in urls_to_try:
                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Parse grant listings (adjust selectors based on actual HTML structure)
                        grant_items = soup.find_all(['div', 'article'], class_=re.compile(r'grant|card|item', re.I))
                        
                        for item in grant_items:
                            try:
                                grant_data = self._parse_grant_item(item)
                                if grant_data:
                                    grants_data.append(grant_data)
                            except Exception as e:
                                print(f"Error parsing grant item: {e}")
                                continue
                        
                        if grants_data:
                            break
                except Exception as e:
                    print(f"Error fetching from {url}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching grants via scraping: {e}")
            # Return empty list instead of raising - API should be primary method
        
        return grants_data
        
        return grants_data
    
    def _parse_grant_item(self, item):
        """Parse a single grant item from HTML"""
        # This is a placeholder - actual parsing logic depends on website structure
        # You'll need to inspect the actual HTML structure of oursggrants.gov.sg
        # and adjust the selectors accordingly
        
        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name', re.I))
        title = title_elem.get_text(strip=True) if title_elem else None
        
        if not title:
            return None
        
        # Extract other fields similarly
        description_elem = item.find(['p', 'div'], class_=re.compile(r'description|summary', re.I))
        description = description_elem.get_text(strip=True) if description_elem else ""
        
        # Extract agency
        agency_elem = item.find(['span', 'div'], class_=re.compile(r'agency|organization', re.I))
        agency_name = agency_elem.get_text(strip=True) if agency_elem else "Unknown"
        
        # Extract dates
        date_elem = item.find(['span', 'div'], class_=re.compile(r'date|deadline|closing', re.I))
        closing_date = self._parse_date(date_elem.get_text(strip=True) if date_elem else None)
        
        # Extract funding amount
        funding_elem = item.find(['span', 'div'], class_=re.compile(r'funding|amount|budget', re.I))
        funding_min, funding_max = self._parse_funding(funding_elem.get_text(strip=True) if funding_elem else "")
        
        # Extract link
        link_elem = item.find('a', href=True)
        link = link_elem['href'] if link_elem else ""
        if link and not link.startswith('http'):
            link = f"{self.BASE_URL}{link}"
        
        return {
            'title': title,
            'description': description,
            'agency_name': agency_name,
            'closing_date': closing_date,
            'funding_min': funding_min,
            'funding_max': funding_max,
            'application_url': link,
            'source_url': link,
        }
    
    def _parse_date(self, date_str):
        """Parse date string to date object"""
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Skip if it's a status message rather than a date
        if any(keyword in date_str.lower() for keyword in ['open', 'closed', 'applications', 'tba', 'n/a']):
            return None
        
        # Common date formats
        date_formats = [
            '%d %b %Y',
            '%d %B %Y',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y-%m-%d %H:%M:%S',  # Handle datetime strings
        ]
        
        # Try parsing with each format
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                continue
        
        # Try parsing ISO format or other variations
        try:
            # Handle dates like "2024-10-30"
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        except:
            pass
        
        return None
    
    def _parse_funding(self, funding_str):
        """Parse funding amount string to min/max values (in thousands)"""
        if not funding_str:
            return None, None
        
        # Handle different formats:
        # "Up to $20,000.00" -> max = 20
        # "$50K - $100K" -> min = 50, max = 100
        # "$50,000 - $100,000" -> min = 50, max = 100
        
        funding_str = str(funding_str).strip()
        
        # Check for "Up to" format
        if 'up to' in funding_str.lower():
            # Extract the number
            numbers = re.findall(r'[\d,]+\.?\d*', funding_str.replace(',', ''))
            if numbers:
                try:
                    val = Decimal(numbers[0])
                    # Convert to thousands
                    if val >= 1000:
                        val = val / 1000
                    return None, val
                except:
                    pass
        
        # Check for range format (e.g., "$50K - $100K" or "$50,000 - $100,000")
        if '-' in funding_str or 'to' in funding_str.lower():
            numbers = re.findall(r'[\d,]+\.?\d*', funding_str.replace(',', ''))
            if len(numbers) >= 2:
                try:
                    min_val = Decimal(numbers[0])
                    max_val = Decimal(numbers[1])
                    # Convert to thousands if needed
                    if min_val >= 1000:
                        min_val = min_val / 1000
                    if max_val >= 1000:
                        max_val = max_val / 1000
                    return min_val, max_val
                except:
                    pass
            elif len(numbers) == 1:
                try:
                    val = Decimal(numbers[0])
                    if val >= 1000:
                        val = val / 1000
                    return val, val
                except:
                    pass
        
        # Try to extract any number
        numbers = re.findall(r'[\d,]+\.?\d*', funding_str.replace(',', ''))
        if numbers:
            try:
                val = Decimal(numbers[0])
                if val >= 1000:
                    val = val / 1000
                return None, val
            except:
                pass
        
        return None, None
    
    def sync_grants_to_db(self):
        """
        Fetch grants and sync them to the database
        Creates agencies and grants if they don't exist
        """
        grants_data = self.fetch_grants()
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for grant_data in grants_data:
            # Skip grants with missing critical data
            external_id = grant_data.get('external_id', '').strip()
            if not external_id:
                skipped_count += 1
                continue
            
            title = grant_data.get('title', '').strip()
            if not title:
                skipped_count += 1
                continue
            
            application_url = grant_data.get('application_url', '').strip()
            if not application_url:
                skipped_count += 1
                continue
            
            # Get or create agency - use agency_code if available, otherwise extract acronym
            agency_code = grant_data.get('agency_code', '').upper().strip()
            agency_name = grant_data.get('agency_name', 'Unknown').strip()
            
            if agency_code:
                # Try to get by acronym first
                agency, created_agency = Agency.objects.get_or_create(
                    acronym=agency_code,
                    defaults={'name': agency_name}
                )
                # Update name if it changed
                if not created_agency and agency.name != agency_name:
                    agency.name = agency_name
                    agency.save()
            else:
                # Fallback to name-based lookup
                agency, _ = Agency.objects.get_or_create(
                        name=agency_name,
                        defaults={'acronym': self._extract_acronym(agency_name)}
                    )
            
            # Use external_id as primary identifier
            lookup_kwargs = {'external_id': external_id}
            
            # Get or create grant
            grant, created = Grant.objects.update_or_create(
                **lookup_kwargs,
                defaults={
                    'title': title,
                    'agency': agency,
                    'description': grant_data.get('description', ''),
                    'funding_min': grant_data.get('funding_min'),
                    'funding_max': grant_data.get('funding_max'),
                    'closing_date': grant_data.get('closing_date'),
                    'application_url': application_url,
                    'source_url': grant_data.get('source_url', ''),
                    'status': grant_data.get('status', 'open'),
                    'icon_name': grant_data.get('icon_name', ''),
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'total': len(grants_data)
        }
    
    def _extract_acronym(self, agency_name):
        """Extract acronym from agency name"""
        # Simple extraction - can be improved
        words = agency_name.split()
        if len(words) >= 2:
            return ''.join([w[0].upper() for w in words[:3]])
        return agency_name[:3].upper()
    
    def _determine_status(self, closing_date):
        """Determine grant status based on closing date"""
        if not closing_date:
            return 'open'
        
        from django.utils import timezone
        today = timezone.now().date()
        
        if closing_date < today:
            return 'closed'
        elif closing_date <= today.replace(day=1) + timezone.timedelta(days=30):
            return 'open'
        else:
            return 'upcoming'


