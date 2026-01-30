#!/usr/bin/env python
"""
Quick reference for the Hybrid Matching Implementation

This demonstrates the scoring breakdown for the new 60/40 hybrid approach.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Grant, Project
from grants.matching import (
    score_focus_and_objectives,
    score_beneficiary_alignment,
    score_budget_compatibility,
    score_timeline_compatibility,
    score_agency_preference,
    score_project_completeness,
)
from datetime import date

# Get a sample grant
grant = Grant.objects.first()
project = Project.objects.first()

if grant and project:
    print("\n" + "="*100)
    print("HYBRID MATCHING SCORING BREAKDOWN")
    print("="*100)
    
    print(f"\nProject: {project.title}")
    print(f"Grant: {grant.title}")
    
    # Calculate individual scores
    scores = {
        "Focus Area (30%)": score_focus_and_objectives(project, grant),
        "Beneficiary Alignment (25%)": score_beneficiary_alignment(project, grant),
        "Budget Compatibility (15%)": score_budget_compatibility(project, grant),
        "Timeline Compatibility (15%)": score_timeline_compatibility(project, grant),
        "Agency Preference (5%)": score_agency_preference(project, grant),
        "Project Completeness (10%)": score_project_completeness(project, grant),
    }
    
    weights = {
        "Focus Area (30%)": 0.30,
        "Beneficiary Alignment (25%)": 0.25,
        "Budget Compatibility (15%)": 0.15,
        "Timeline Compatibility (15%)": 0.15,
        "Agency Preference (5%)": 0.05,
        "Project Completeness (10%)": 0.10,
    }
    
    print(f"\n{'='*100}")
    print(f"RULE-BASED SCORING (60% of final score)")
    print(f"{'='*100}\n")
    
    rule_based_total = 0
    for component, score in scores.items():
        weight = weights[component]
        contribution = score * weight * 100
        rule_based_total += contribution
        print(f"{component:40} | Score: {score:.2f} | Contribution: {contribution:.1f} pts")
    
    print(f"\nRule-Based Total: {rule_based_total:.1f}/100")
    
    print(f"\n{'='*100}")
    print(f"HYBRID FORMULA")
    print(f"{'='*100}\n")
    
    print(f"Final Score = 0.6 × {rule_based_total:.1f} + 0.4 × Gemini_Score")
    print(f"\nExample scenarios:")
    print(f"  If Gemini = 80: {min(int(0.6 * rule_based_total + 0.4 * 80), 100)}%")
    print(f"  If Gemini = 50: {min(int(0.6 * rule_based_total + 0.4 * 50), 100)}%")
    print(f"  If Gemini = 20: {min(int(0.6 * rule_based_total + 0.4 * 20), 100)}%")
    
else:
    print("\nNo projects or grants in database yet.")
    print("Create a project and grant first to see this in action.")
    print("\nBut here's the formula:\n")
    print("Final Score (0-100) = 0.6 × Rule-Based Score + 0.4 × Gemini Semantic Score\n")
    print("Rule-Based Components:")
    print("  ├─ Focus Area & Objectives:      30%")
    print("  ├─ Beneficiary Alignment:        25%")
    print("  ├─ Budget Compatibility:         15%")
    print("  ├─ Timeline Compatibility:       15%")
    print("  ├─ Agency Preference:             5%")
    print("  └─ Project Completeness:         10%")
