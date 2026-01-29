#!/usr/bin/env python3
"""
Standalone script to sync Young Changemakers grant.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
sys.path.insert(0, '/Users/ednachong/Documents/grantmatch/grantmatchproject')

# Setup Django minimal to avoid hanging
import django.conf
if not django.conf.settings.configured:
    django.setup()

from grants.models import Grant
from grants.services import SGGrantsService

# Search for the grant
print("Searching for Young Changemakers grant...")
try:
    # Try by external_id first (likely 'nycycm' or similar)
    grant = Grant.objects.filter(external_id__icontains='ycm').first() or \
            Grant.objects.filter(title__icontains='young').first()
    
    if grant:
        print(f"Found grant: ID={grant.id}, Title={grant.title}, External ID={grant.external_id}")
        print(f"URL: {grant.application_url}")
        
        # Sync the grant
        print("\nSyncing grant...")
        service = SGGrantsService()
        result = service.sync_grant_by_id(grant_id=grant.id)
        print(f"Sync result: {result}")
        
        # Re-fetch and display updated fields
        grant.refresh_from_db()
        print(f"\nUpdated fields:")
        print(f"  about_text: {len(grant.about_text)} chars")
        print(f"  who_can_apply_text: {len(grant.who_can_apply_text)} chars")
        print(f"  when_to_apply_text: {len(grant.when_to_apply_text)} chars")
        print(f"  funding_text: {len(grant.funding_text)} chars")
    else:
        print("Grant not found!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
