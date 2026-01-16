"""
Service for integrating with OurSG Grants Portal
https://oursggrants.gov.sg/
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from decimal import Decimal
import re
from .models import Grant, Agency


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
        Can search by grant_value (e.g., 'ssgacg') or external_id
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
        
        # Try to fetch additional details from the instruction page
        if grant_detail.get('application_url'):
            try:
                additional_details = self._fetch_grant_instruction_page(grant_detail['application_url'])
                grant_detail.update(additional_details)
            except Exception as e:
                print(f"Could not fetch additional details: {e}")
        
        return grant_detail
    
    def _fetch_grant_instruction_page(self, instruction_url):
        """
        Fetch detailed grant information from the instruction page
        Extracts: About, Who can apply, When to apply, Funding, How to apply
        """
        try:
            response = self.session.get(instruction_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            additional_data = {}
            
            # Find the main content area
            main_content = soup.find('div', class_=re.compile(r'content|main|instruction', re.I))
            if not main_content:
                # Try to find any div with the instruction text
                main_content = soup.find('div', string=re.compile(r'About this grant|INSTRUCTIONS', re.I))
                if main_content:
                    main_content = main_content.find_parent('div')
            
            if not main_content:
                main_content = soup
            
            # Extract "About this grant" section
            about_section = self._extract_section_by_heading(main_content, ['About this grant', 'About'])
            if about_section:
                additional_data['about_grant'] = about_section
                # Also update description if not already set
                if 'description' not in additional_data:
                    additional_data['description'] = about_section[:500]
            
            # Extract "Who Can Apply?" section
            who_can_apply = self._extract_section_by_heading(main_content, ['Who Can Apply', 'Who can apply', 'Eligibility'])
            if who_can_apply:
                additional_data['eligibility_criteria'] = who_can_apply
                additional_data['who_can_apply'] = who_can_apply
            
            # Extract "When to Apply?" section
            when_to_apply = self._extract_section_by_heading(main_content, ['When to Apply', 'When to apply', 'Application Timeline'])
            if when_to_apply:
                additional_data['when_to_apply'] = when_to_apply
            
            # Extract "How much funding can you receive?" section
            funding_info = self._extract_section_by_heading(main_content, ['How much funding', 'Funding', 'How much'])
            if funding_info:
                additional_data['funding_details'] = funding_info
                additional_data['funding_info'] = funding_info
            
            # Extract "How to apply?" section
            how_to_apply = self._extract_section_by_heading(main_content, ['How to apply', 'How to Apply', 'Application Process'])
            if how_to_apply:
                additional_data['how_to_apply'] = how_to_apply
            
            # Extract documents required
            documents_section = self._extract_section_by_heading(main_content, ['Documents Required', 'Required Documents', 'DOCUMENTS REQUIRED'])
            if documents_section:
                additional_data['required_documents'] = documents_section
            
            return additional_data
        except Exception as e:
            print(f"Error fetching instruction page: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _fetch_via_scraping(self):
        """
        Scrape grants from OurSG Grants Portal website
        Note: This should be used responsibly and in compliance with terms of service
        """
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 is required for web scraping. Install it with: pip install beautifulsoup4")
        
        grants_data = []
        
        try:
            # Fetch the main grants listing page
            response = self.session.get(f"{self.BASE_URL}/grants")
            response.raise_for_status()
            
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
                    
        except Exception as e:
            print(f"Error fetching grants: {e}")
        
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
        
        for grant_data in grants_data:
            # Get or create agency - use agency_code if available, otherwise extract acronym
            agency_code = grant_data.get('agency_code', '').upper()
            agency_name = grant_data.get('agency_name', 'Unknown')
            
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
            
            # Use external_id as primary identifier, fallback to title+agency
            external_id = grant_data.get('external_id', '')
            lookup_kwargs = {}
            if external_id:
                lookup_kwargs['external_id'] = external_id
            else:
                # Fallback: use title and agency
                lookup_kwargs['title'] = grant_data.get('title', '')
                lookup_kwargs['agency'] = agency
            
            # Get or create grant
            grant, created = Grant.objects.update_or_create(
                **lookup_kwargs,
                defaults={
                    'title': grant_data.get('title', ''),
                    'agency': agency,
                    'description': grant_data.get('description', ''),
                    'funding_min': grant_data.get('funding_min'),
                    'funding_max': grant_data.get('funding_max'),
                    'closing_date': grant_data.get('closing_date'),
                    'application_url': grant_data.get('application_url', ''),
                    'source_url': grant_data.get('source_url', ''),
                    'status': grant_data.get('status', 'open'),
                    'icon_name': grant_data.get('icon_name', ''),
                    'external_id': external_id,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
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


# Sample data for development/testing when API/scraping is not available
SAMPLE_GRANTS_DATA = [
    {
        'title': 'Community Care Innovation Fund',
        'agency_name': 'Agency for Integrated Care',
        'acronym': 'AIC',
        'description': 'Supports innovative community care programs for seniors, including dementia care initiatives.',
        'funding_min': 80,
        'funding_max': 150,
        'closing_date': '2025-03-15',
        'duration_years': '2-3 years',
        'status': 'open',
        'icon_name': 'hospital',
    },
    {
        'title': 'Silver Generation Fund',
        'agency_name': 'Ministry of Social and Family Development',
        'acronym': 'MSF',
        'description': 'Funding for active aging initiatives and programs that support senior well-being.',
        'funding_min': 50,
        'funding_max': 100,
        'closing_date': '2025-04-30',
        'duration_years': '1-2 years',
        'status': 'open',
        'icon_name': 'building',
    },
    {
        'title': 'Mental Wellness Support Grant',
        'agency_name': 'Health Promotion Board',
        'acronym': 'HPB',
        'description': 'Grants for mental health services and preventive care programs.',
        'funding_min': 60,
        'funding_max': 120,
        'closing_date': '2025-05-20',
        'duration_years': '2 years',
        'status': 'open',
        'icon_name': 'heart',
    },
    {
        'title': 'Technology for Seniors Grant',
        'agency_name': 'Infocomm Media Development Authority',
        'acronym': 'IMDA',
        'description': 'Funding for technology solutions that improve the lives of seniors.',
        'funding_min': 40,
        'funding_max': 80,
        'closing_date': '2025-03-31',
        'duration_years': '1-2 years',
        'status': 'open',
        'icon_name': 'tech',
    },
]
