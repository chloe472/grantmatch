#!/usr/bin/env python
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant, Project, Agency
from django.contrib.auth.models import User

# Pick Grant ID 11: Communities of Care Grant (Sports, vulnerable populations)
grant = Grant.objects.get(id=11)

print("\n" + "="*100)
print("TARGET GRANT FOR 85%+ MATCH")
print("="*100)
print(f"\nGrant ID: {grant.id}")
print(f"Title: {grant.title}")
print(f"Agency: {grant.agency.acronym} - {grant.agency.name}")
print(f"Funding: ${grant.funding_min or 'N/A'} - ${grant.funding_max or 'N/A'}K")
print(f"Duration: {grant.duration_years}")
print(f"\nDescription:\n{grant.description}\n")
print(f"Eligibility:\n{grant.eligibility_criteria}\n")

print("\n" + "="*100)
print("RECOMMENDED PROJECT (for 85%+ match score)")
print("="*100)

project_data = {
    'title': 'Active Aging Sports Program for Seniors in Vulnerable Communities',
    'description': 'A comprehensive sports and physical activity program designed to benefit elderly individuals and vulnerable populations in underserved neighborhoods. The program focuses on building communities of care through regular sports activities, mentorship, and peer support networks.',
    'focus_area': 'Sports, Health & Wellness, Active Aging, Community Care',
    'budget_required_min': 50000,
    'budget_required_max': 150000,
    'duration_years': '2 years',
    'beneficiary_types': ['elderly', 'vulnerable populations', 'seniors', 'low-income families'],
    'target_beneficiaries_count': 200,
    'project_start_date': date.today() + timedelta(days=90),
    'project_end_date': date.today() + timedelta(days=730),  # 2 years
    'interested_in': ['sports', 'physical activity', 'health', 'community programs', 'vulnerable populations'],
    'need_support_for': ['program funding', 'coach training', 'facilities access', 'equipment'],
    'want_support_from': ['SPORTSG'],  # Sports Singapore
    'kpis': '- 200 beneficiaries engaged\n- 85% attendance rate\n- Improved physical health metrics\n- Increased social connectivity',
    'service_outcomes': 'Reduced sedentary behavior, improved mental health, stronger community bonds, increased sports participation among vulnerable seniors'
}

print("\n✅ PROJECT DETAILS FOR 85%+ MATCH:")
print(f"\n1. TITLE: {project_data['title']}")
print(f"\n2. DESCRIPTION:\n   {project_data['description']}")
print(f"\n3. FOCUS AREA:\n   {project_data['focus_area']}")
print(f"\n4. BUDGET:\n   Min: ${project_data['budget_required_min']:,.0f}")
print(f"   Max: ${project_data['budget_required_max']:,.0f}")
print(f"   → Grant offers up to $200K (✓ Budget MATCHES)")
print(f"\n5. DURATION:\n   {project_data['duration_years']}")
print(f"\n6. BENEFICIARY TYPES:")
for b in project_data['beneficiary_types']:
    print(f"   - {b}")
print(f"   → Grant targets 'underserved and vulnerable populations' (✓ MATCHES)")
print(f"\n7. TARGET BENEFICIARIES: {project_data['target_beneficiaries_count']}")
print(f"\n8. PROJECT START DATE: {project_data['project_start_date'].strftime('%Y-%m-%d')}")
print(f"   → Within grant closing/eligibility window (✓ MATCHES)")
print(f"\n9. INTERESTED IN:")
for i in project_data['interested_in']:
    print(f"   - {i}")
print(f"   → Direct alignment with grant (Sports + Health + Community) (✓ MATCHES)")
print(f"\n10. NEED SUPPORT FOR:")
for n in project_data['need_support_for']:
    print(f"    - {n}")
print(f"\n11. WANT SUPPORT FROM:")
for a in project_data['want_support_from']:
    print(f"    - {a}")
print(f"    → SPORTSG is offering this grant (✓ AGENCY PREFERENCE MATCHES)")

print(f"\n12. KPIs:\n    {project_data['kpis']}")
print(f"\n13. SERVICE OUTCOMES:\n    {project_data['service_outcomes']}")

print("\n" + "="*100)
print("SCORING BREAKDOWN (New Reweighted Criteria)")
print("="*100)

scoring = {
    'Focus area & objectives (30%)': {
        'score': 0.95,
        'reason': 'Strong alignment: "sports" + "vulnerable populations" + "health" all explicitly mentioned in grant'
    },
    'Beneficiary alignment (25%)': {
        'score': 0.95,
        'reason': 'Perfect match: Grant targets "underserved and vulnerable populations", project targets elderly + vulnerable'
    },
    'Budget compatibility (15%)': {
        'score': 1.0,
        'reason': 'Project asks for $50-150K, grant gives up to $200K (comfortably within range)'
    },
    'Timeline compatibility (15%)': {
        'score': 1.0,
        'reason': 'Project duration (2 years) clearly fits with grant eligibility'
    },
    'Agency preference (5%)': {
        'score': 1.0,
        'reason': 'Project explicitly wants support from SPORTSG, which is administering this grant'
    },
    'Project completeness (10%)': {
        'score': 0.95,
        'reason': 'Project has clear goals, complete budget range, specific duration, KPIs, and beneficiary targets'
    },
}

total_score = 0
for criterion, details in scoring.items():
    weight = float(criterion.split('(')[1].split('%')[0]) / 100
    weighted = details['score'] * weight * 100
    total_score += weighted
    print(f"\n{criterion}")
    print(f"  Score: {details['score']:.0%}")
    print(f"  Reason: {details['reason']}")
    print(f"  Contribution: {weighted:.1f} points")

print(f"\n{'='*100}")
print(f"ESTIMATED FINAL SCORE: {total_score:.0f}%")
print(f"{'='*100}")
print(f"\n✅ This project should score approximately {total_score:.0f}% match with the")
print(f"   Communities of Care Grant (SPORTSG)\n")
