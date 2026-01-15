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
        Attempt to fetch grants via API
        Note: This is a placeholder - actual API endpoint needs to be determined
        """
        # Placeholder for API integration
        # If API becomes available, implement here
        raise NotImplementedError("API endpoint not yet available")
    
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
        
        # Common date formats
        date_formats = [
            '%d %b %Y',
            '%d %B %Y',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _parse_funding(self, funding_str):
        """Parse funding amount string to min/max values"""
        if not funding_str:
            return None, None
        
        # Extract numbers (handle formats like "$50K - $100K", "$50,000 - $100,000", etc.)
        numbers = re.findall(r'[\d,]+', funding_str.replace(',', ''))
        
        if len(numbers) >= 2:
            try:
                min_val = Decimal(numbers[0]) / 1000  # Convert to thousands
                max_val = Decimal(numbers[1]) / 1000
                return min_val, max_val
            except:
                pass
        elif len(numbers) == 1:
            try:
                val = Decimal(numbers[0]) / 1000
                return val, val
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
            # Get or create agency
            agency, _ = Agency.objects.get_or_create(
                name=grant_data.get('agency_name', 'Unknown'),
                defaults={
                    'acronym': self._extract_acronym(grant_data.get('agency_name', 'Unknown')),
                }
            )
            
            # Get or create grant
            grant, created = Grant.objects.update_or_create(
                external_id=grant_data.get('external_id', ''),
                source_url=grant_data.get('source_url', ''),
                defaults={
                    'title': grant_data.get('title', ''),
                    'agency': agency,
                    'description': grant_data.get('description', ''),
                    'funding_min': grant_data.get('funding_min'),
                    'funding_max': grant_data.get('funding_max'),
                    'closing_date': grant_data.get('closing_date'),
                    'application_url': grant_data.get('application_url', ''),
                    'source_url': grant_data.get('source_url', ''),
                    'status': self._determine_status(grant_data.get('closing_date')),
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
