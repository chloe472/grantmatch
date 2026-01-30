#!/usr/bin/env python
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant

# Get target grant: Communities of Care Grant (ID 11)
grant = Grant.objects.get(id=11)

print(f"\nGrant ID: {grant.id}")
print(f"Title: {grant.title}")
print(f"Status: {grant.status}")
print(f"Closing Date: {grant.closing_date}")
print(f"Opening Date: {grant.opening_date}")
print(f"Description: {grant.description[:200]}...")
print(f"Eligibility: {grant.eligibility_criteria[:200] if grant.eligibility_criteria else 'None'}...")
print(f"Funding Min: {grant.funding_min}")
print(f"Funding Max: {grant.funding_max}")
