"""
Management command to fetch agency logos from Our SG Grants Portal and agency websites
Usage: python manage.py fetch_logos [--update-db]
"""
from django.core.management.base import BaseCommand
from grants.logo_service import LogoFetchService
from grants.models import Agency


class Command(BaseCommand):
    help = 'Fetch agency logos from Our SG Grants Portal and agency websites'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-db',
            action='store_true',
            help='Update Agency model logo_url fields with fetched logos',
        )
        parser.add_argument(
            '--agency',
            type=str,
            help='Fetch logo for specific agency acronym (e.g., AIC, MSF)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Fetching agency logos...'))
        
        logo_service = LogoFetchService()
        
        # Get agencies to fetch logos for
        if options['agency']:
            agencies = Agency.objects.filter(acronym=options['agency'].upper())
            if not agencies.exists():
                self.stdout.write(
                    self.style.ERROR(f'Agency "{options["agency"]}" not found in database')
                )
                return
        else:
            # Fetch for all agencies
            agencies = Agency.objects.all()
        
        if not agencies.exists():
            self.stdout.write(
                self.style.WARNING('No agencies found in database. Run sync_grants first.')
            )
            return
        
        # Fetch logos
        fetched_logos = logo_service.fetch_all_agency_logos(list(agencies))
        
        # Report results
        self.stdout.write(self.style.SUCCESS(f'\nFetched {len(fetched_logos)} logos:'))
        for acronym, logo_path in fetched_logos.items():
            self.stdout.write(f'  {acronym}: {logo_path}')
        
        # Update database if requested
        if options['update_db']:
            self.stdout.write(self.style.SUCCESS('\nUpdating Agency logo_url fields...'))
            logo_service.update_agency_logo_urls(list(agencies))
            self.stdout.write(self.style.SUCCESS('Database updated!'))
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\nTip: Use --update-db to automatically update Agency model logo_url fields'
                )
            )
