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
            
            # Determine closing date text
            if grant_status == 'closed':
                closing_date_text = "Application Closed"
            else:
                closing_date_text = closing_date_str or "Open for Applications"
            
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
                'closing_date_text': closing_date_text,
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
        
        # Debug: Show what we got from API
        print(f"DEBUG: Grant from API - Title: {grant_detail.get('title')}")
        print(f"DEBUG: grant_amount_text from API: {grant_detail.get('grant_amount_text')}")
        print(f"DEBUG: funding_min from API: {grant_detail.get('funding_min')}")
        print(f"DEBUG: funding_max from API: {grant_detail.get('funding_max')}")
        
        # Initialize funding_info from grant_amount_text if available
        if grant_detail.get('grant_amount_text') and not grant_detail.get('funding_info'):
            grant_detail['funding_info'] = grant_detail.get('grant_amount_text')
            print(f"DEBUG: Initialized funding_info from grant_amount_text: {grant_detail['funding_info']}")
        
        # Fetch real content from the instruction page using Playwright
        instruction_url = grant_detail.get('application_url', '')
        page_content = None
        if instruction_url:
            try:
                print(f"DEBUG: Attempting to fetch from Playwright: {instruction_url}")
                page_content = self._fetch_instruction_page_with_playwright(instruction_url)
                if page_content:
                    print(f"DEBUG: Playwright returned page_content with funding_info: {page_content.get('funding_info')}")
                    grant_detail.update(page_content)
                else:
                    print(f"DEBUG: Playwright returned None")
            except Exception as e:
                print(f"Could not fetch detailed content with Playwright: {e}")
                # Fall back to basic formatting
        
        # If funding info is still not available, try scraping from /grants/new page
        if not grant_detail.get('funding_info') or (not grant_detail.get('funding_min') and not grant_detail.get('funding_max')):
            print(f"DEBUG: Attempting to scrape from /grants/new page")
            scraped_funding = self._scrape_funding_from_new_page(
                grant_title=grant_detail.get('title'),
                grant_value=grant_value
            )
            if scraped_funding:
                print(f"DEBUG: Scraped funding found: {scraped_funding}")
                grant_detail.update(scraped_funding)
            else:
                print(f"DEBUG: Scraping from /grants/new returned nothing")
        
        # ALWAYS ensure funding_info is set before returning
        if not grant_detail.get('funding_info'):
            print(f"DEBUG: No funding_info found, using fallback formatting")
            # Build funding info from available data
            if grant_detail.get('grant_amount_text'):
                grant_detail['funding_info'] = grant_detail.get('grant_amount_text')
                print(f"DEBUG: Using grant_amount_text as fallback: {grant_detail['funding_info']}")
            else:
                formatted_funding = self._format_funding(
                    grant_detail.get('funding_min'),
                    grant_detail.get('funding_max'),
                    ''
                )
                grant_detail['funding_info'] = formatted_funding
                print(f"DEBUG: Using formatted_funding as fallback: {formatted_funding}")
        
        # If we still don't have page content, use fallback formatting for other fields
        if not page_content:
            grant_detail['about_grant'] = grant_detail.get('description', '')
            grant_detail['who_can_apply'] = self._format_applicable_to(grant_detail) if grant_detail.get('applicable_to') else 'Please check the official grant page for eligibility criteria.'
            grant_detail['when_to_apply'] = self._format_closing_dates(grant_detail.get('closing_date_text', ''))
            grant_detail['how_to_apply'] = grant_detail.get('how_to_apply_html', 'Please visit the official OurSG Grants Portal for detailed application instructions.')
            grant_detail['required_documents'] = 'Please refer to the official grant page for required supporting documents.'
            grant_detail['document_links'] = [
                {
                    'name': 'View Required Documents on OurSG',
                    'url': instruction_url,
                    'size': 'External Link'
                }
            ]
        
        print(f"DEBUG: Returning grant_detail with funding_info: {grant_detail.get('funding_info')}")
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

    def _fetch_rendered_soup(self, instruction_url):
        """
        Render the instruction page with Playwright and return a BeautifulSoup object
        of the fully rendered HTML. Caller is responsible for handling None results.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._async_fetch_rendered_html(instruction_url))
            loop.close()
            if result:
                return BeautifulSoup(result, 'html.parser')
            return None
        except Exception as e:
            print(f"Error rendering page with Playwright: {e}")
            return None

    async def _async_fetch_rendered_html(self, instruction_url):
        """Async helper that returns rendered HTML string for a given URL."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto(instruction_url, wait_until="load", timeout=60000)
                await page.wait_for_timeout(3000)
                content = await page.content()
                return content
            finally:
                await context.close()
                await browser.close()
    
    def _extract_grant_sections(self, soup):
        """
        Extract grant sections from the rendered HTML.
        Also parses funding amounts from the funding_info section.
        Detects HTML tables for structured funding data.
        """
        # First, try to extract HTML tables with funding data
        table_data = self._extract_funding_table_from_html(soup)
        
        # Get all text lines that are meaningful
        all_text = soup.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip() and len(line.strip()) > 10]
        
        # Join to get full text
        full_text = '\n'.join(lines)

        # Normalize heading-like phrases so they appear on their own lines.
        # Some OurSG pages place multiple headings in a single paragraph (e.g.
        # "When can I apply? How much funding can you receive?") which breaks
        # the section extraction. Insert newlines around known section markers
        # so `_extract_section_text` can reliably split sections.
        heading_markers = [
            'about this grant', 'about the grant', 'the aim', 'about',
            'who can apply', 'who is eligible', 'eligibility',
            'when to apply', 'when can i apply', 'application is open', 'application timeline',
            'how much funding', 'how much funding can you receive', 'funding amount', 'grant amount', r'up to s\$',
            'how to apply', 'application process', 'completing the grant', r'how to apply\?',
            'documents required', 'required documents', 'supporting documents', 'documents required for application'
        ]

        for marker in heading_markers:
            try:
                # Case-insensitive: surround the matched marker with newlines
                full_text = re.sub(r'(?i)(' + re.escape(marker) + r')', lambda m: '\n' + m.group(0).strip() + '\n', full_text)
            except Exception:
                # If the regex fails for any marker, continue without breaking extraction
                continue
        
        # Extract funding info text - specifically look for lines with "$" in the funding section
        funding_text = self._extract_funding_section(full_text) if not table_data else None
        
        # Parse funding amounts from the extracted text
        funding_min, funding_max = self._parse_funding(funding_text) if funding_text else (None, None)
        
        # Use table data if found, otherwise use text
        grant_amount_text = table_data if table_data else (funding_text if funding_text else None)
        
        extracted = {
            'about_grant': self._extract_section_text(full_text, ['about this grant', 'the aim']),
            'who_can_apply': self._extract_section_text(full_text, ['who can apply', 'eligibility', 'who is eligible']),
            'when_to_apply': self._extract_section_text(full_text, ['when to apply', 'when can i apply', 'application is open', 'application timeline']),
            'funding_info': grant_amount_text,
            'grant_amount_text': grant_amount_text,
            'how_to_apply': self._extract_section_text(full_text, ['how to apply', 'completing the grant', 'application process']),
            'required_documents': self._extract_section_text(full_text, ['documents required', 'required documents', 'supporting documents']),
            'document_links': self._extract_document_links(soup),
            'funding_min': funding_min,
            'funding_max': funding_max
        }
        # Post-process extracted sections to remove any embedded other-section headings
        # that may have been included when headings were inline in the source.
        try:
            # Build reverse map of marker -> section key
            marker_map = {}
            mapping = {
                'about_grant': ['about this grant', 'about the grant', 'the aim', 'about'],
                'who_can_apply': ['who can apply', 'eligibility', 'who is eligible'],
                'when_to_apply': ['when to apply', 'when can i apply', 'application is open', 'application timeline'],
                'funding_info': ['how much funding', 'funding amount', 'grant amount', 'up to s$','funding'],
                'how_to_apply': ['how to apply', 'application process', 'completing the grant', 'how to apply?'],
                'required_documents': ['documents required', 'required documents', 'supporting documents']
            }
            for k, markers in mapping.items():
                for m in markers:
                    marker_map[m.lower()] = k

            # For each extracted section, if it contains a marker that belongs to a
            # different section, truncate the content at that marker.
            for key, value in list(extracted.items()):
                if not isinstance(value, str) or not value:
                    continue
                lower_val = value.lower()
                for marker, owner_key in marker_map.items():
                    if owner_key == key:
                        continue
                    idx = lower_val.find(marker)
                    if idx != -1:
                        # Truncate at the start of the found marker
                        new_text = value[:idx].strip()
                        # Only replace if truncation yields meaningful text
                        if new_text and len(new_text) > 10:
                            extracted[key] = new_text
                        else:
                            # If truncation would leave too little, remove the marker itself
                            extracted[key] = value[idx + len(marker):].strip()
                        break
            
        except Exception:
            pass

        # Strip any leftover section title fragments (including question marks)
        # from the start of each section and remove repeated inline headings.
        try:
            section_title_variants = {
                'about_grant': ['about this grant', 'about the grant', 'the aim', 'about this grant:'],
                'who_can_apply': ['who can apply', 'who can apply?', 'who is eligible', 'eligibility'],
                'when_to_apply': ['when to apply', 'when can i apply', 'when can i apply?', 'application timeline'],
                'funding_info': ['how much funding can you receive', 'how much funding can you receive?', 'how much funding', 'funding amount', 'how much funding can you receive?', 'can you receive', 'can you receive?'],
                'how_to_apply': ['how to apply', 'how to apply?', 'application process', 'completing the grant'],
                'required_documents': ['documents required', 'required documents', 'documents required for application']
            }

            for key, text in list(extracted.items()):
                if not isinstance(text, str) or not text:
                    continue
                cleaned = text
                # Remove any section title variants anywhere in the text
                for variant in section_title_variants.get(key, []):
                    try:
                        # remove variant with optional surrounding punctuation and whitespace
                        cleaned = re.sub(r'(?i)\s*[:\-–—]?\s*' + re.escape(variant) + r'\s*[:\-–—]?\s*', ' ', cleaned)
                    except Exception:
                        continue

                # Also remove other section headings that may have leaked in
                for other_key, variants in section_title_variants.items():
                    if other_key == key:
                        continue
                    for variant in variants:
                        try:
                            cleaned = re.sub(r'(?i)\s*[:\-–—]?\s*' + re.escape(variant) + r'\s*[:\-–—]?\s*', ' ', cleaned)
                        except Exception:
                            continue

                # Trim and normalize whitespace, remove leading punctuation
                cleaned = re.sub(r'^[\s\W]+', '', cleaned)
                cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
                extracted[key] = cleaned
        except Exception:
            pass

        return extracted
    
        def _extract_grant_sections(self, soup):
            """
            Extract grant sections from the rendered HTML using heading-aware parsing.
            This method finds section headings (h1-h4 or strong tags that look like headings)
            and collects following content up until the next heading. It returns a dict
            with keys matching the UI sections.
            """
            from bs4 import Tag

            # Mapping of target keys to lists of keywords that identify the section heading
            mapping = {
                'about_grant': ['about this grant', 'about the grant', 'the aim', 'about'],
                'who_can_apply': ['who can apply', 'eligibility', 'who is eligible'],
                'when_to_apply': ['when to apply', 'when can i apply', 'application is open', 'application timeline'],
                'funding_info': ['how much funding', 'funding amount', 'grant amount', 'up to s$','funding'],
                'how_to_apply': ['how to apply', 'application process', 'completing the grant', 'how to apply?'],
                'required_documents': ['documents required', 'required documents', 'supporting documents']
            }

            # Initialize results with empty strings
            results = {k: '' for k in mapping.keys()}

            # Prefer explicit heading tags - collect all potential heading elements
            heading_tags = soup.find_all(['h1', 'h2', 'h3', 'h4'])

            # Also consider bold/strong elements that may be used as headings
            strong_tags = [t for t in soup.find_all('strong') if t.get_text(strip=True) and len(t.get_text(strip=True)) < 120]

            candidates = heading_tags + strong_tags

            # If no candidates found, fall back to searching top-level paragraphs
            if not candidates:
                candidates = soup.find_all(['p', 'div'])[:]

            # Walk through candidates and match headings to mapping
            for el in candidates:
                heading_text = el.get_text(' ', strip=True).lower()
                if not heading_text:
                    continue

                matched_key = None
                for key, keywords in mapping.items():
                    if any(kw in heading_text for kw in keywords):
                        matched_key = key
                        break

                if not matched_key:
                    continue

                # Collect following sibling content until next heading-like element
                pieces = []
                node = el.next_sibling
                while node:
                    # Skip navigable strings that are just whitespace
                    if isinstance(node, Tag):
                        # Stop if node is a heading tag or another strong that looks like a header
                        if node.name in ['h1', 'h2', 'h3', 'h4']:
                            break
                        node_text = node.get_text(' ', strip=True)
                        if node_text and len(node_text) > 3:
                            pieces.append(node_text)
                    else:
                        # string
                        t = str(node).strip()
                        if t and len(t) > 3:
                            pieces.append(t)
                    node = node.next_sibling

                # If nothing captured via siblings, attempt to capture the following elements in DOM tree
                if not pieces:
                    for sib in el.find_next_siblings():
                        if isinstance(sib, Tag) and sib.name in ['h1', 'h2', 'h3', 'h4']:
                            break
                        text = sib.get_text(' ', strip=True) if isinstance(sib, Tag) else str(sib).strip()
                        if text and len(text) > 3:
                            pieces.append(text)

                # Join pieces and clean repeated heading-like prefixes
                section_text = ' '.join(pieces).strip()
                # Remove repeated heading if accidentally included
                for kw in mapping[matched_key]:
                    if section_text.lower().startswith(kw):
                        section_text = section_text[len(kw):].strip(' :–-\n')

                results[matched_key] = section_text[:4000]

            # As a fallback, use text-search extraction for missing sections
            full_text = soup.get_text('\n', strip=True)
            if not results['when_to_apply']:
                results['when_to_apply'] = self._extract_section_text(full_text, ['when to apply', 'when can i apply', 'application is open'])
            if not results['funding_info']:
                results['funding_info'] = self._extract_section_text(full_text, ['how much funding', 'funding amount', 'grant amount', 'up to s$'])
            if not results['how_to_apply']:
                results['how_to_apply'] = self._extract_section_text(full_text, ['how to apply', 'application process'])
            if not results['about_grant']:
                results['about_grant'] = self._extract_section_text(full_text, ['about this grant', 'the aim'])
            if not results['who_can_apply']:
                results['who_can_apply'] = self._extract_section_text(full_text, ['who can apply', 'eligibility'])
            if not results['required_documents']:
                results['required_documents'] = self._extract_section_text(full_text, ['documents required', 'required documents'])

            # Parse funding amounts from funding_info
            funding_min, funding_max = self._parse_funding(results.get('funding_info', '')) if results.get('funding_info') else (None, None)

            extracted = {
                'about_grant': results.get('about_grant', ''),
                'who_can_apply': results.get('who_can_apply', ''),
                'when_to_apply': results.get('when_to_apply', ''),
                'funding_info': results.get('funding_info', ''),
                'how_to_apply': results.get('how_to_apply', ''),
                'required_documents': results.get('required_documents', ''),
                'document_links': self._extract_document_links(soup),
                'funding_min': funding_min,
                'funding_max': funding_max
            }

            return extracted
    
    def _extract_funding_table_from_html(self, soup):
        """
        Extract funding information from HTML tables
        Returns dict with table structure if found, None otherwise
        """
        # Find all tables in the page
        tables = soup.find_all('table')
        
        for table in tables:
            # Get all rows
            rows = table.find_all('tr')
            
            if len(rows) < 2:
                continue
            
            # Parse table rows
            parsed_rows = []
            has_dollar_sign = False
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                
                # Extract text from each cell
                cell_texts = []
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    cell_texts.append(cell_text)
                    if '$' in cell_text:
                        has_dollar_sign = True
                
                if cell_texts:
                    parsed_rows.append(cell_texts)
            
            # If this table has $ signs and reasonable structure, return it
            if has_dollar_sign and len(parsed_rows) >= 2 and len(parsed_rows[0]) >= 2:
                print(f"DEBUG: Found funding table with {len(parsed_rows)} rows and {len(parsed_rows[0])} columns")
                return {
                    'is_table': True,
                    'rows': parsed_rows
                }
        
        return None

    def _extract_funding_section(self, full_text):
        """
        Extract funding information from plain text (when not in table format)
        Returns single funding sentence or phrase, not structured as table
        """
        # Split into lines
        lines = full_text.split('\n')
        
        funding_lines = []
        in_funding_context = False
        funding_context_lines = 0
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            
            # Skip very short lines and JavaScript
            if not clean_line or len(clean_line) < 5 or 'javascript' in clean_line.lower():
                continue
            
            # Check if line contains funding-related keywords
            line_lower = clean_line.lower()
            is_context_keyword = any(keyword in line_lower for keyword in [
                'capped', 'up to', 'maximum', 'minimum', 'receive'
            ])
            
            # Collect lines with $ in funding context
            if '$' in clean_line:
                print(f"DEBUG: Found $ in line: {clean_line}")
                
                funding_text = self._extract_funding_text(clean_line)
                
                if funding_text and funding_text not in funding_lines:
                    print(f"DEBUG: Adding funding line: {funding_text}")
                    funding_lines.append(funding_text)
        
        # Return as plain text (tables are handled separately)
        if funding_lines:
            result = '\n'.join(funding_lines)
            print(f"DEBUG: Extracted funding as plain text: {result}")
            return result
        
        print(f"DEBUG: No $ symbol found in page")
        return None
    
    def _parse_funding_table(self, funding_lines):
        """
        Parse funding lines into table structure if they follow a table pattern
        Returns dict with table headers and rows, or None if not a table
        """
        if len(funding_lines) < 3:
            return None
    
    def _extract_funding_text(self, line):
        """
        Extract meaningful funding text from a line containing $
        Returns just the relevant funding information
        """
        # Return the line as-is (likely already clean text from extracted content)
        return line.strip() if line else None
    
    def _extract_section_text(self, full_text, keywords):
        """
        Extract text content for a specific section using keywords.
        Stops at the next section heading and removes duplicate header lines.
        """
        # All possible section headings to detect section boundaries
        section_headings = [
            'who can apply', 'when to apply', 'when can i apply',
            'how much funding', 'how to apply', 'documents required', 
            'about this grant', 'about the grant', 'apply as', 'eligibility',
            'application timeline', 'funding amount', 'grant amount',
            'application process', 'required documents'
        ]
        
        for keyword in keywords:
            idx = full_text.lower().find(keyword.lower())
            if idx != -1:
                # Get content from this keyword onwards (800 chars to find next section)
                section_start = idx
                section_end = min(len(full_text), idx + 800)
                section_text = full_text[section_start:section_end]
                
                # Split into lines
                lines = section_text.split('\n')
                
                # Build result, stopping at next section heading
                result_lines = []
                skipped_header = False
                
                for line in lines:
                    clean_line = line.strip()
                    
                    # Skip empty lines and very short lines
                    if not clean_line or len(clean_line) < 5 or 'javascript' in clean_line.lower():
                        continue
                    
                    line_lower = clean_line.lower()
                    
                    # Skip the first line if it's just the section header
                    if not skipped_header:
                        # Check if line is primarily the keyword (section header)
                        is_keyword = any(kw.lower() in line_lower for kw in keywords)
                        
                        # Skip lines that are short and contain the keyword (likely headers)
                        if is_keyword and len(clean_line) < 100:
                            skipped_header = True
                            continue
                        elif is_keyword:
                            skipped_header = True
                    
                    # Check if this is a different section heading
                    is_different_section = False
                    for heading in section_headings:
                        if heading.lower() in line_lower:
                            # Make sure it's not our current section
                            if not any(kw.lower() in heading.lower() for kw in keywords):
                                is_different_section = True
                                break
                    
                    # Stop at next section if we have content
                    if is_different_section and len(result_lines) > 1:
                        break
                    
                    result_lines.append(clean_line)
                
                # Return the result (limit to 10 lines to prevent too much content)
                if result_lines:
                    return '\n'.join(result_lines[:10])
        
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

    def _classify_paragraphs(self, soup):
        """
        Fallback paragraph classifier. Splits rendered text into paragraphs
        (preserving paragraph breaks) and assigns each paragraph to exactly
        one section based on prioritized keyword rules.
        Returns dict with keys: about, who, when, funding
        """
        text = soup.get_text('\n\n', strip=True)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        funding_kw = ['$', 's$', 'sgd', 'up to', '%', 'subsidy', 'co-fund', 'reimburse', 'allowable cost']
        when_kw = ['deadline', 'closing date', 'closes', 'open for', 'apply by', 'deadline:', 'closing:']
        who_kw = ['eligible', 'open to', 'must be', 'singapore citizens', 'pr', 'ncss-members', 'msf-funded']

        # month names and simple date patterns to help detect when-to-apply
        months = r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b'
        date_pattern = re.compile(r'(\d{1,2}\s+' + months + r')|\d{4}-\d{2}-\d{2}', re.I)

        sections = {'about': [], 'who': [], 'when': [], 'funding': []}

        for para in paragraphs:
            lowered = para.lower()

            # Funding (highest priority)
            if any(kw in lowered for kw in funding_kw):
                sections['funding'].append(para)
                continue

            # When to apply - check date patterns or when keywords
            if date_pattern.search(para) or any(kw in lowered for kw in when_kw):
                sections['when'].append(para)
                continue

            # Who can apply
            if any(kw in lowered for kw in who_kw):
                sections['who'].append(para)
                continue

            # Else -> About
            sections['about'].append(para)

        # Ensure deduplication: a paragraph appears in only one section by design
        # Join paragraphs preserving blank-line paragraph breaks
        return {
            'about': '\n\n'.join(sections['about']).strip(),
            'who': '\n\n'.join(sections['who']).strip(),
            'when': '\n\n'.join(sections['when']).strip(),
            'funding': '\n\n'.join(sections['funding']).strip()
        }
    
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
        """
        Format funding information - handles plain text, tables, and single amounts
        """
        if not grant_amount_text:
            grant_amount_text = ""
        
        # If grant_amount_text is a dict (table structure), return as-is for template to handle
        if isinstance(grant_amount_text, dict) and grant_amount_text.get('is_table'):
            print(f"DEBUG: Returning table structure: {grant_amount_text}")
            return grant_amount_text
        
        # If we already have meaningful grant_amount_text (string), use it as-is
        if grant_amount_text and isinstance(grant_amount_text, str):
            if any(keyword in grant_amount_text.lower() for keyword in ['capped', 'up to', 'maximum', 'minimum', 'are eligible', 'per', 'track', 'talent']) or '$' in grant_amount_text:
                print(f"DEBUG: Using grant_amount_text directly: {grant_amount_text}")
                # If it's multi-line, format with proper spacing for display
                if '\n' in grant_amount_text:
                    lines = grant_amount_text.split('\n')
                    formatted_lines = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            formatted_lines.append(line)
                    return '\n'.join(formatted_lines)
                return grant_amount_text
        
        # If we have funding_min and funding_max but no text description
        if funding_min and funding_max:
            result = f"Up to SGD ${funding_max:,.0f}"
            print(f"DEBUG: Formatted funding from min/max: {result}")
            return result
        elif funding_max:
            result = f"Up to SGD ${funding_max:,.0f}"
            print(f"DEBUG: Formatted funding (max only): {result}")
            return result
        elif funding_min:
            result = f"Minimum SGD ${funding_min:,.0f}"
            print(f"DEBUG: Formatted funding (min only): {result}")
            return result
        elif grant_amount_text:
            return grant_amount_text
        else:
            return "Funding details not available. Please check the OurSG Grants Portal for more information."
    
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
        print(f"DEBUG: _parse_funding input: {funding_str}")
        
        # Check for "Up to" format or "capped at"
        if 'up to' in funding_str.lower() or 'capped' in funding_str.lower():
            # Extract the number
            numbers = re.findall(r'[\d,]+(?:\.\d+)?', funding_str)
            if numbers:
                try:
                    val = Decimal(numbers[0].replace(',', ''))
                    # Keep original value if less than 1000, otherwise convert to thousands
                    if val >= 1000:
                        val = val / 1000
                    print(f"DEBUG: _parse_funding extracted max: {val}")
                    return None, val
                except Exception as e:
                    print(f"DEBUG: _parse_funding error: {e}")
                    pass
        
        # Check for range format (e.g., "$50K - $100K" or "$50,000 - $100,000")
        if '-' in funding_str or ' to ' in funding_str.lower():
            numbers = re.findall(r'[\d,]+(?:\.\d+)?', funding_str)
            if len(numbers) >= 2:
                try:
                    min_val = Decimal(numbers[0].replace(',', ''))
                    max_val = Decimal(numbers[1].replace(',', ''))
                    # Convert to thousands if needed
                    if min_val >= 1000:
                        min_val = min_val / 1000
                    if max_val >= 1000:
                        max_val = max_val / 1000
                    print(f"DEBUG: _parse_funding extracted range: {min_val} - {max_val}")
                    return min_val, max_val
                except Exception as e:
                    print(f"DEBUG: _parse_funding error: {e}")
                    pass
            elif len(numbers) == 1:
                try:
                    val = Decimal(numbers[0].replace(',', ''))
                    if val >= 1000:
                        val = val / 1000
                    print(f"DEBUG: _parse_funding extracted single: {val}")
                    return val, val
                except:
                    pass
        
        # Try to extract any number (most lenient approach)
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', funding_str)
        if numbers:
            try:
                val = Decimal(numbers[0].replace(',', ''))
                if val >= 1000:
                    val = val / 1000
                print(f"DEBUG: _parse_funding extracted any: {val}")
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

    def sync_grant_by_id(self, grant_id=None, external_id=None):
        """
        Sync a single Grant instance by its DB id or external_id using live OurSG content.
        This will fetch live sections (about, who, when, funding) and persist them
        into existing Grant model fields without changing schema. Existing values
        are preserved if extraction fails.
        """
        from django.db import transaction

        # Locate the Grant instance
        grant = None
        try:
            if grant_id:
                grant = Grant.objects.get(id=grant_id)
            elif external_id:
                grant = Grant.objects.get(external_id=external_id)
            else:
                raise ValueError('grant_id or external_id required')
        except Grant.DoesNotExist:
            print(f"Grant not found for id={grant_id} external_id={external_id}")
            return {'updated': 0, 'error': 'not_found'}

        # Fetch and classify live instruction page content
        instruction_url = grant.application_url or grant.source_url
        if not instruction_url:
            print(f"No instruction URL for grant {grant.id}; skipping.")
            return {'updated': 0, 'skipped': 1}

        try:
            soup = self._fetch_rendered_soup(instruction_url)
        except Exception as e:
            print(f"Error rendering instruction page for grant {grant.id}: {e}")
            return {'updated': 0, 'skipped': 1}

        if not soup:
            print(f"Rendered content empty for grant {grant.id}; skipping.")
            return {'updated': 0, 'skipped': 1}

        # Detect clear section headings: count how many of the target headings exist
        heading_keywords = [
            'about this grant', 'who can apply', 'when can i apply', 'how much funding',
            'who is eligible', 'when to apply', 'funding amount', 'how much funding can you receive'
        ]
        found = 0
        for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'b']):
            text = h.get_text(' ', strip=True).lower()
            if any(kw in text for kw in heading_keywords):
                found += 1

        # If clear headings exist (3 or more), prefer heading-aware extraction
        if found >= 3:
            try:
                extracted = self._extract_grant_sections(soup)
                about = extracted.get('about_grant') or ''
                who = extracted.get('who_can_apply') or ''
                when = extracted.get('when_to_apply') or ''
                funding_info = extracted.get('funding_info') or extracted.get('grant_amount_text') or ''
                funding_min = extracted.get('funding_min')
                funding_max = extracted.get('funding_max')
                print(f"DEBUG: Heading-aware extraction used for grant {grant.id}; headings_found={found}")
            except Exception as e:
                print(f"Error during heading-aware extraction for grant {grant.id}: {e}")
                return {'updated': 0, 'skipped': 1}
        else:
            # Fallback: paragraph-based classification using rules
            try:
                classified = self._classify_paragraphs(soup)
                about = classified.get('about') or ''
                who = classified.get('who') or ''
                when = classified.get('when') or ''
                funding_info = classified.get('funding') or ''
                # parse funding amounts from funding_info
                funding_min, funding_max = self._parse_funding(funding_info) if funding_info else (None, None)
                print(f"DEBUG: Paragraph-classification extraction used for grant {grant.id}; paragraphs_classified")
            except Exception as e:
                print(f"Error during paragraph-classification for grant {grant.id}: {e}")
                return {'updated': 0, 'skipped': 1}

        # Only write fields if we have meaningful extracted content
        updated = 0
        try:
            with transaction.atomic():
                changed = False

                # Update description (about). Preserve existing if empty extraction.
                if about and len(about) > 20 and about != grant.description:
                    grant.description = about
                    changed = True

                # Update eligibility_criteria
                if who and len(who) > 10 and who != grant.eligibility_criteria:
                    grant.eligibility_criteria = who
                    changed = True

                # Append or update 'when_to_apply' into description if present
                if when and len(when) > 10:
                    # Only add if not already contained
                    if when not in grant.description:
                        grant.description = (grant.description or '') + '\n\nWhen to apply:\n' + when
                        changed = True

                # Update funding_min/max and include funding_info text if present
                if funding_min is not None and funding_min != grant.funding_min:
                    grant.funding_min = funding_min
                    changed = True
                if funding_max is not None and funding_max != grant.funding_max:
                    grant.funding_max = funding_max
                    changed = True

                # If we have a funding_info textual description and it's meaningful,
                # append to description if not present.
                if funding_info and len(str(funding_info)) > 10:
                    fi_text = str(funding_info).strip()
                    if fi_text not in grant.description:
                        grant.description = (grant.description or '') + '\n\nFunding:\n' + fi_text
                        changed = True

                # Update source/application urls if present
                if fetched.get('document_links'):
                    # Prefer instruction page as source_url
                    if grant.source_url != grant.application_url and grant.application_url:
                        grant.source_url = grant.application_url
                        changed = True

                if changed:
                    grant.save()
                    updated = 1

        except Exception as e:
            print(f"Error saving grant {grant.id}: {e}")
            return {'updated': 0, 'error': str(e)}

        return {'updated': updated}
    
    def _extract_acronym(self, agency_name):
        """Extract acronym from agency name"""
        # Simple extraction - can be improved
        words = agency_name.split()
        if len(words) >= 2:
            return ''.join([w[0].upper() for w in words[:3]])
        return agency_name[:3].upper()
    
    def _scrape_funding_from_new_page(self, grant_title=None, grant_value=None):
        """
        Scrape funding information for a specific grant from the /grants/new page
        Extracts any lines containing "$" as funding information
        """
        try:
            url = f"{self.BASE_URL}/grants/new"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            # Split text into lines for easier processing
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            
            # Look for grant by title, then extract any line with "$" near it
            for i, line in enumerate(lines):
                # Check if this line contains the grant title
                if grant_title and grant_title.lower() in line.lower():
                    print(f"DEBUG: Found grant title at line {i}: {line}")
                    
                    # Look in the next 10 lines for any line containing "$"
                    for j in range(i + 1, min(i + 10, len(lines))):
                        next_line = lines[j]
                        
                        # If this line contains "$", it's funding information
                        if '$' in next_line:
                            print(f"DEBUG: Found $ in line {j}: {next_line}")
                            funding_text = next_line
                            funding_min, funding_max = self._parse_funding(funding_text)
                            if funding_min or funding_max:
                                return {
                                    'funding_info': funding_text,
                                    'grant_amount_text': funding_text,
                                    'funding_min': funding_min,
                                    'funding_max': funding_max
                                }
                        
                        # Stop if we hit another grant or section
                        if j > i + 2 and any(heading in next_line.lower() for heading in ['open for applications', 'applications closed', 'view details']):
                            print(f"DEBUG: Hit section boundary at line {j}, stopping")
                            break
            
            print(f"DEBUG: No funding found for grant: {grant_title}")
            return None
            
        except Exception as e:
            print(f"Error scraping funding from /grants/new: {e}")
            return None
    
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


