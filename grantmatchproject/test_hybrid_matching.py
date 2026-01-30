#!/usr/bin/env python
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant, Project, Agency
from django.contrib.auth.models import User
from grants.matching import compute_match_score

# Get target grant: Professional Capability Grant (ID 45) - NCSS
grant = Grant.objects.get(id=45)

# Create a test user
test_user, _ = User.objects.get_or_create(
    username='hybrid_test_user',
    defaults={'email': 'hybrid@test.com'}
)

# Create project aligned with Professional Capability Grant (Social Service focus)
project = Project.objects.create(
    user=test_user,
    title='Social Service Professional Development and Talent Attraction Program',
    description='A comprehensive professional capability development program designed to attract and retain talented professionals in the social service sector. Focuses on mid-career conversion for individuals transitioning into social service, with structured training, mentorship, and competency development in clinical and non-clinical areas of social service delivery.',
    focus_area='Professional Capability, Talent Development, Social Service, Social Enterprise',
    budget_required_min=30000,
    budget_required_max=100000,
    duration_years='1-2 years',
    beneficiary_types=['social service professionals', 'mid-career changers', 'service providers'],
    target_beneficiaries_count=150,
    project_start_date=date(2026, 1, 15),  # Before closing date of 2026-02-02
    project_end_date=date(2027, 1, 15),
    interested_in=['professional development', 'social service', 'training', 'talent attraction', 'capability building'],
    need_support_for=['training funding', 'course support', 'professional development', 'competency building'],
    want_support_from=['NCSS'],  # National Council of Social Service
    kpis='- 150 professionals trained\n- 80% completion rate\n- 90% job retention in social service\n- Improved service delivery outcomes',
    service_outcomes='Increased professional capacity in social service sector, improved talent retention, enhanced service delivery quality, strengthened organizational capabilities'
)

print("\n" + "="*100)
print("HYBRID MATCHING TEST (60% Rules + 40% Gemini Semantic)")
print("="*100)

print(f"\nProject: {project.title}")
print(f"Grant: {grant.title}")

print(f"\nComputing hybrid match score...")
score, reasons = compute_match_score(project, grant)

print(f"\n{'='*100}")
print(f"FINAL MATCH SCORE: {score}%")
print(f"{'='*100}")

print("\nMatch Reasons:")
for i, reason in enumerate(reasons, 1):
    print(f"  {i}. {reason}")

print(f"\n{'='*100}")
print(f"SCORE EVALUATION:")
print(f"{'='*100}")
print(f"Expected: ~80-90% (rule-based ~90% + semantic boost)")
print(f"Actual: {score}%")

if score >= 80:
    status = "EXCELLENT (80-100%)"
elif score >= 70:
    status = "GOOD (70-79%)"
elif score >= 50:
    status = "FAIR (50-69%)"
else:
    status = "LOW (<50%)"
    
print(f"Status: {status}")

print(f"\n\nNote: Actual score depends on Gemini semantic evaluation (requires API key)")
print(f"Rule-based portion should be ~90%, semantic can adjust final score.")

# Clean up - optional (comment out to keep test data)
# project.delete()
# print(f"\nTest project cleaned up.")
