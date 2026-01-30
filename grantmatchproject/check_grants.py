#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant

# Get ALL grants
grants = Grant.objects.all().order_by('-closing_date')[:10]

print("\n" + "="*100)
print("ALL GRANTS IN SYSTEM (Top 10 by closing date)")
print("="*100)

for g in grants:
    print(f"\nGrant ID: {g.id}")
    print(f"Title: {g.title}")
    print(f"Agency: {g.agency.acronym}")
    print(f"Status: {g.status}")
    print(f"Funding: ${g.funding_min or 'N/A'} - ${g.funding_max or 'N/A'}")
    print(f"Closing Date: {g.closing_date}")
    print(f"Duration: {g.duration_years}")
    print(f"Description (first 200 chars): {g.description[:200]}...")
    print("-" * 100)
