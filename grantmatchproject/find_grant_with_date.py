#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant

# Get grants with closing dates
grants = Grant.objects.filter(
    status='open',
    closing_date__isnull=False
).order_by('-closing_date')[:5]

print("\n" + "="*100)
print("OPEN GRANTS WITH CLOSING DATES")
print("="*100)

for g in grants:
    print(f"\nGrant ID: {g.id}")
    print(f"Title: {g.title}")
    print(f"Agency: {g.agency.acronym}")
    print(f"Status: {g.status}")
    print(f"Closing Date: {g.closing_date}")
    print(f"Funding: ${g.funding_min or 'N/A'} - ${g.funding_max or 'N/A'}")
    print(f"Description: {g.description[:150]}...")
    print("-" * 100)
