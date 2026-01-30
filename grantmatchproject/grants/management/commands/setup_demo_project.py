"""
Management command to create a demo project showcasing the grant matching system.

This command:
1. Creates a demo user (if not exists)
2. Creates a well-defined demo project with all required fields
3. Calculates matches for the demo project
4. Provides instructions for showcasing the system

Usage:
    python manage.py setup_demo_project
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date, timedelta
from grants.models import Project
from grants.views import calculate_matches_for_project


class Command(BaseCommand):
    help = 'Set up a demo project for showcasing the grant matching system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='demo_user',
            help='Username for the demo account (default: demo_user)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='demo@example.com',
            help='Email for the demo account'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='DemoPass123!',
            help='Password for the demo account'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreate demo project if exists'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        force = options['force']

        self.stdout.write(self.style.SUCCESS('🚀 Setting up demo project for grant matching showcase...'))
        self.stdout.write('')

        # Step 1: Create or get demo user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': 'Demo',
                'last_name': 'User'
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created demo user: {username}'))
            self.stdout.write(f'  Email: {email}')
            self.stdout.write(f'  Password: {password}')
        else:
            self.stdout.write(self.style.WARNING(f'✓ Demo user already exists: {username}'))

        self.stdout.write('')

        # Step 2: Delete existing demo project if force flag
        if force:
            Project.objects.filter(user=user, title='Youth Digital Skills Bootcamp').delete()
            self.stdout.write(self.style.WARNING('✓ Removed existing demo project'))

        # Step 3: Create demo project
        demo_project, created = Project.objects.get_or_create(
            user=user,
            title='Youth Digital Skills Bootcamp',
            defaults={
                'description': (
                    'A comprehensive 12-week intensive bootcamp program designed to equip '
                    'disadvantaged youth aged 18-25 with in-demand digital skills for the '
                    'modern job market. The program focuses on web development, data analysis, '
                    'and digital marketing, with mentorship from industry professionals and '
                    'guaranteed job placement support. Participants will work on real-world '
                    'projects that contribute to social enterprises and non-profits, creating '
                    'both technical experience and social impact. The program includes soft skills '
                    'training, career counseling, and a 3-month paid internship component.'
                ),
                'focus_area': 'Youth Skills Development, Digital Economy',
                'budget_required_min': 80000,  # SGD
                'budget_required_max': 150000,
                'duration_years': '1-2 years',
                'kpis': (
                    '1. 80% of participants complete the bootcamp\n'
                    '2. 70% secure employment within 3 months post-program\n'
                    '3. Average salary increase of 50% for employed participants\n'
                    '4. 90% positive feedback rating from participants\n'
                    '5. 50+ social enterprises/NPOs benefit from project work'
                ),
                'service_outcomes': (
                    'Participants gain practical coding skills, build professional portfolios, '
                    'develop career confidence, and secure employment. Employers gain access to '
                    'pre-trained talent pool. Social sector organizations receive pro-bono '
                    'technical expertise for their digital transformation.'
                ),
                'beneficiary_types': ['Youth (18-25)', 'Disadvantaged communities', 'Social enterprises'],
                'target_beneficiaries_count': 150,
                'project_start_date': date.today() + timedelta(days=60),
                'project_end_date': date.today() + timedelta(days=450),  # ~15 months
                'interested_in': [
                    'Skills Development',
                    'Youth Employment',
                    'Digital Transformation',
                    'Social Enterprise',
                    'Entrepreneurship'
                ],
                'need_support_for': [
                    'Program management',
                    'Curriculum development',
                    'Mentorship coordination',
                    'Job placement partnerships',
                    'Technology infrastructure'
                ],
                'want_support_from': [
                    'IMDA',  # Infocomm Media Development Authority
                    'NCSS',  # National Council of Social Service
                    'PEB',   # People's Association Enterprise Board
                ],
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created demo project: "Youth Digital Skills Bootcamp"'))
            self.stdout.write(f'  Owner: {user.get_full_name() or username}')
            self.stdout.write(f'  Focus: {demo_project.focus_area}')
            self.stdout.write(f'  Budget: SGD {demo_project.budget_required_min:,.0f} - {demo_project.budget_required_max:,.0f}')
            self.stdout.write(f'  Duration: {demo_project.duration_years}')
            self.stdout.write(f'  Target beneficiaries: {demo_project.target_beneficiaries_count}')
        else:
            self.stdout.write(self.style.WARNING('✓ Demo project already exists'))

        self.stdout.write('')

        # Step 4: Calculate matches
        self.stdout.write('⏳ Calculating grant matches (this may take a moment)...')
        calculate_matches_for_project(demo_project)

        # Get match statistics
        from grants.models import GrantMatch
        matches = GrantMatch.objects.filter(project=demo_project).order_by('-match_score')
        high_matches = matches.filter(match_score__gte=80).count()
        good_matches = matches.filter(match_score__gte=70, match_score__lt=80).count()
        moderate_matches = matches.filter(match_score__lt=70).count()

        self.stdout.write(self.style.SUCCESS('✓ Match calculation complete'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📊 MATCH STATISTICS:'))
        self.stdout.write(f'  Excellent matches (90-100%): {matches.filter(match_score__gte=90).count()}')
        self.stdout.write(f'  Strong matches (80-89%):     {matches.filter(match_score__gte=80, match_score__lt=90).count()}')
        self.stdout.write(f'  Good matches (70-79%):       {good_matches}')
        self.stdout.write(f'  Moderate matches (<70%):     {moderate_matches}')
        self.stdout.write(f'  Total matching grants:       {matches.count()}')

        # Show top 5 matches
        if matches.exists():
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('🏆 TOP 5 MATCHING GRANTS:'))
            for i, match in enumerate(matches[:5], 1):
                self.stdout.write(
                    f'  {i}. {match.grant.title} ({match.grant.agency.acronym})'
                )
                self.stdout.write(f'     Match Score: {match.match_score}%')
                if match.match_reasons:
                    self.stdout.write(f'     Reason: {match.match_reasons[0]}')
                self.stdout.write('')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ DEMO PROJECT SETUP COMPLETE!'))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('📋 HOW TO SHOWCASE THE MATCHING SYSTEM:'))
        self.stdout.write('')
        self.stdout.write('1️⃣  LOGIN TO THE SYSTEM:')
        self.stdout.write(f'   • Go to http://localhost:8000/accounts/login/')
        self.stdout.write(f'   • Username: {username}')
        self.stdout.write(f'   • Password: {password}')
        self.stdout.write('')
        self.stdout.write('2️⃣  VIEW THE DEMO PROJECT:')
        self.stdout.write('   • Navigate to "My Projects"')
        self.stdout.write('   • Click on "Youth Digital Skills Bootcamp"')
        self.stdout.write('   • Review the project details (well-defined with KPIs, beneficiaries, etc.)')
        self.stdout.write('')
        self.stdout.write('3️⃣  EXPLORE GRANT MATCHES:')
        self.stdout.write('   • Click "View Matches" to see all calculated matches')
        self.stdout.write('   • Matches are sorted by score (highest first)')
        self.stdout.write('   • Notice the variety of match scores (70-100%)')
        self.stdout.write('')
        self.stdout.write('4️⃣  VIEW GRANT DETAILS & MATCHING EXPLANATION:')
        self.stdout.write('   • Click on any grant to view its detail page')
        self.stdout.write('   • Scroll down to see TWO NEW SECTIONS:')
        self.stdout.write('     ✓ "Why This Grant Matches" (blue box with positive reasons)')
        self.stdout.write('     ✓ "Why It May Not Match" (yellow/orange box with concerns)')
        self.stdout.write('')
        self.stdout.write('5️⃣  UNDERSTAND THE MATCHING LOGIC:')
        self.stdout.write('   • Each reason shows which aspect drove the match:')
        self.stdout.write('     - Focus area alignment')
        self.stdout.write('     - Beneficiary match')
        self.stdout.write('     - Budget compatibility')
        self.stdout.write('     - Timeline fit')
        self.stdout.write('     - Agency preference')
        self.stdout.write('     - Project completeness')
        self.stdout.write('')
        self.stdout.write('6️⃣  COMPARE DIFFERENT MATCH SCORES:')
        self.stdout.write('   • Look at a 95%+ match: See all positive reasons, minimal concerns')
        self.stdout.write('   • Look at a 70-80% match: See some positive reasons, clear concerns')
        self.stdout.write('   • Look at a <70% match: Few positive reasons, multiple concerns')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('💡 WHY THIS DEMO PROJECT IS EFFECTIVE:'))
        self.stdout.write('')
        self.stdout.write('✓ WELL-DEFINED:')
        self.stdout.write('  - Clear description, focus area, budget, timeline, KPIs')
        self.stdout.write('  - Demonstrates project completeness scoring (10% component)')
        self.stdout.write('')
        self.stdout.write('✓ COMMERCIALLY RELEVANT:')
        self.stdout.write('  - Skills development is a key policy focus in Singapore')
        self.stdout.write('  - Multiple agencies fund youth employment programs')
        self.stdout.write('  - Digital skills are in high demand')
        self.stdout.write('')
        self.stdout.write('✓ MULTIPLE MATCH SCENARIOS:')
        self.stdout.write('  - Some grants match perfectly (IMDA, NCSS, PEB)')
        self.stdout.write('  - Some grants are close but have timeline concerns')
        self.stdout.write('  - Some grants have budget misalignment')
        self.stdout.write('  - This demonstrates the nuanced matching algorithm')
        self.stdout.write('')
        self.stdout.write('✓ DEMONSTRATES MATCHING COMPONENTS:')
        self.stdout.write('  - Focus area: "Skills Development" appears in many grant descriptions')
        self.stdout.write('  - Beneficiaries: Youth and disadvantaged communities are popular targets')
        self.stdout.write('  - Budget: $80K-$150K range fits many programs')
        self.stdout.write('  - Timeline: 1-2 year duration is standard')
        self.stdout.write('')
        self.stdout.write('✓ HIGHLIGHTS NEGATIVE REASONING:')
        self.stdout.write('  - Timeline: Project ends at different time than grant support')
        self.stdout.write('  - Budget: Some grants have stricter budgets')
        self.stdout.write('  - Agency: Project prefers certain agencies (AgencyPreference score)')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🎯 EXPECTED OUTCOMES:'))
        self.stdout.write('')
        self.stdout.write('When showcasing, you\'ll see:')
        self.stdout.write('  • 2-3 Excellent matches (90-100%): Full alignment')
        self.stdout.write('  • 3-5 Strong matches (80-89%): Minor alignment gaps')
        self.stdout.write('  • 5-10 Good matches (70-79%): Some misalignment but viable')
        self.stdout.write('  • 10+ Moderate/weak matches: Significant gaps highlighted')
        self.stdout.write('')
        self.stdout.write('This variety demonstrates that the system:')
        self.stdout.write('  ✓ Evaluates across 6 dimensions (not just keyword matching)')
        self.stdout.write('  ✓ Uses both rule-based AND AI semantic analysis')
        self.stdout.write('  ✓ Provides actionable feedback (why/why not)')
        self.stdout.write('  ✓ Handles edge cases and concerns properly')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('📚 DOCUMENTATION:'))
        self.stdout.write('  See MATCHING_LOGIC_EXPLANATION.md for full technical details')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Happy demoing! 🎉'))
