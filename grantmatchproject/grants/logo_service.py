"""
Service for fetching agency logos from Our SG Grants Portal and agency websites
"""
import requests
from bs4 import BeautifulSoup
import os
from pathlib import Path
from django.conf import settings
from urllib.parse import urljoin, urlparse
import re


class LogoFetchService:
    """Service to fetch agency logos from various sources"""
    
    BASE_URL = "https://oursggrants.gov.sg"
    
    # Agency website mappings
    AGENCY_WEBSITES = {
        'AIC': 'https://www.aic.sg',
        'MSF': 'https://www.msf.gov.sg',
        'HPB': 'https://www.hpb.gov.sg',
        'NCSS': 'https://www.ncss.gov.sg',
        'IMDA': 'https://www.imda.gov.sg',
        'NYC': 'https://www.nyc.gov.sg',
        'CDC': 'https://www.cdc.gov.sg',
        'NAC': 'https://www.nac.gov.sg',
        'CSA': 'https://www.csa.gov.sg',
        'NHB': 'https://www.nhb.gov.sg',
        'MSO': 'https://www.mso.gov.sg',
        'MCCY': 'https://www.mccy.gov.sg',
        'HDB': 'https://www.hdb.gov.sg',
        'SportsG': 'https://www.sportsingapore.gov.sg',
        'NEA': 'https://www.nea.gov.sg',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Get static directory path
        self.static_dir = Path(settings.BASE_DIR) / 'static' / 'agency-logos'
        self.static_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_logo_from_portal(self, agency_acronym: str) -> str:
        """
        Fetch logo from Our SG Grants Portal
        
        Args:
            agency_acronym: Agency acronym (e.g., 'AIC', 'MSF')
            
        Returns:
            URL or path to the logo, or None if not found
        """
        try:
            # Try to find logo in the portal's HTML
            portal_url = f"{self.BASE_URL}"
            response = self.session.get(portal_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for agency logos in various possible locations
            # Common patterns: img tags with agency name, data attributes, etc.
            logo_selectors = [
                f'img[alt*="{agency_acronym}"]',
                f'img[src*="{agency_acronym.lower()}"]',
                f'img[class*="agency"]',
                f'img[class*="logo"]',
            ]
            
            for selector in logo_selectors:
                try:
                    img = soup.select_one(selector)
                    if img and img.get('src'):
                        logo_url = urljoin(portal_url, img['src'])
                        # Download and save
                        return self._download_and_save_logo(logo_url, agency_acronym)
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error fetching logo from portal for {agency_acronym}: {e}")
            return None
    
    def fetch_logo_from_agency_website(self, agency_acronym: str) -> str:
        """
        Fetch logo from agency's official website
        
        Args:
            agency_acronym: Agency acronym (e.g., 'AIC', 'MSF')
            
        Returns:
            Path to saved logo file, or None if not found
        """
        if agency_acronym not in self.AGENCY_WEBSITES:
            return None
        
        try:
            website_url = self.AGENCY_WEBSITES[agency_acronym]
            response = self.session.get(website_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for logo in common locations
            logo_selectors = [
                'img[class*="logo"]',
                'img[id*="logo"]',
                'img[alt*="logo"]',
                'header img',
                '.logo img',
                '#logo img',
            ]
            
            for selector in logo_selectors:
                try:
                    img = soup.select_one(selector)
                    if img and img.get('src'):
                        logo_url = urljoin(website_url, img['src'])
                        # Download and save
                        return self._download_and_save_logo(logo_url, agency_acronym)
                except:
                    continue
            
            # Try to find in meta tags or structured data
            meta_logo = soup.find('meta', property='og:image')
            if meta_logo and meta_logo.get('content'):
                logo_url = urljoin(website_url, meta_logo['content'])
                return self._download_and_save_logo(logo_url, agency_acronym)
            
            return None
            
        except Exception as e:
            print(f"Error fetching logo from {agency_acronym} website: {e}")
            return None
    
    def _download_and_save_logo(self, logo_url: str, agency_acronym: str) -> str:
        """
        Download logo from URL and save to static directory
        
        Args:
            logo_url: URL of the logo image
            agency_acronym: Agency acronym for filename
            
        Returns:
            Relative path to saved logo (e.g., '/static/agency-logos/aic.png')
        """
        try:
            response = self.session.get(logo_url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Determine file extension from URL or content type
            content_type = response.headers.get('content-type', '')
            if 'png' in content_type or logo_url.lower().endswith('.png'):
                ext = 'png'
            elif 'jpg' in content_type or 'jpeg' in content_type or logo_url.lower().endswith(('.jpg', '.jpeg')):
                ext = 'jpg'
            elif 'svg' in content_type or logo_url.lower().endswith('.svg'):
                ext = 'svg'
            else:
                # Try to get from URL
                parsed = urlparse(logo_url)
                ext = os.path.splitext(parsed.path)[1][1:] or 'png'
            
            # Save to static directory
            filename = f"{agency_acronym.lower()}.{ext}"
            filepath = self.static_dir / filename
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded logo for {agency_acronym} to {filepath}")
            
            # Return relative path for use in templates
            return f"/static/agency-logos/{filename}"
            
        except Exception as e:
            print(f"Error downloading logo from {logo_url}: {e}")
            return None
    
    def fetch_all_agency_logos(self, agencies: list) -> dict:
        """
        Fetch logos for multiple agencies
        
        Args:
            agencies: List of agency acronyms or Agency objects
            
        Returns:
            Dictionary mapping agency acronym to logo path/URL
        """
        results = {}
        
        for agency in agencies:
            if hasattr(agency, 'acronym'):
                acronym = agency.acronym
            else:
                acronym = agency
            
            print(f"Fetching logo for {acronym}...")
            
            # Try portal first
            logo_path = self.fetch_logo_from_portal(acronym)
            
            # If not found, try agency website
            if not logo_path:
                logo_path = self.fetch_logo_from_agency_website(acronym)
            
            if logo_path:
                results[acronym] = logo_path
                print(f"✓ Found logo for {acronym}: {logo_path}")
            else:
                print(f"✗ Could not find logo for {acronym}")
        
        return results
    
    def update_agency_logo_urls(self, agencies: list):
        """
        Update Agency model logo_url fields with fetched logos
        
        Args:
            agencies: List of Agency model instances
        """
        from .models import Agency
        
        fetched_logos = self.fetch_all_agency_logos(agencies)
        
        for agency in agencies:
            if agency.acronym in fetched_logos:
                logo_path = fetched_logos[agency.acronym]
                # If it's a static path, convert to full URL or keep as static path
                if logo_path.startswith('/static/'):
                    # Store as static path (will be resolved by Django's static files)
                    agency.logo_url = logo_path
                else:
                    agency.logo_url = logo_path
                agency.save()
                print(f"Updated {agency.acronym} logo_url to: {logo_path}")
