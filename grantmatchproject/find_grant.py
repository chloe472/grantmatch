#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
sys.path.insert(0, '/Users/ednachong/Documents/grantmatch/grantmatchproject')
django.setup()

from grants.models import Grant

# Search for Young Changemakers grant
grants = Grant.objects.filter(title__icontains='young changemakers')
print(f"Found {grants.count()} grants matching 'young changemakers':")
for g in grants:
    print(f"  ID: {g.id}, Title: {g.title}, External ID: {g.external_id}, URL: {g.application_url}")

# Also search by the known URL pattern
grants2 = Grant.objects.filter(application_url__icontains='nycycm')
print(f"\nFound {grants2.count()} grants with 'nycycm' in URL:")
for g in grants2:
    print(f"  ID: {g.id}, Title: {g.title}, External ID: {g.external_id}")
