"""
Management command to sync grants from OurSG Grants Portal
Usage: python manage.py sync_grants [--sample]
"""
from django.core.management.base import BaseCommand
from grants.services import SGGrantsService, SAMPLE_GRANTS_DATA
from grants.models import Grant, Agency
from datetime import datetime


class Command(BaseCommand):
    help = 'Sync grants from OurSG Grants Portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample',
            action='store_true',
            help='Use sample data instead of fetching from portal',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing grants',
        )

    def handle(self, *args, **options):
        use_sample = options['sample']
        
        if use_sample:
            self.stdout.write(self.style.SUCCESS('Using sample grants data...'))
            self._load_sample_data()
        else:
            self.stdout.write(self.style.SUCCESS('Fetching grants from OurSG Grants Portal...'))
            service = SGGrantsService()
            
            try:
                result = service.sync_grants_to_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully synced {result["total"]} grants '
                        f'({result["created"]} created, {result["updated"]} updated)'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error syncing grants: {e}')
                )
                self.stdout.write(
                    self.style.WARNING('Tip: Use --sample flag to load sample data for development')
                )
    
    def _load_sample_data(self):
        """Load sample grants data for development"""
        created_count = 0
        updated_count = 0
        
        for grant_data in SAMPLE_GRANTS_DATA:
            # Get or create agency
            agency, _ = Agency.objects.get_or_create(
                acronym=grant_data['acronym'],
                defaults={
                    'name': grant_data['agency_name'],
                }
            )
            
            # Parse closing date
            closing_date = None
            if grant_data.get('closing_date'):
                try:
                    closing_date = datetime.strptime(grant_data['closing_date'], '%Y-%m-%d').date()
                except:
                    pass
            
            # Get or create grant
            grant, created = Grant.objects.update_or_create(
                title=grant_data['title'],
                agency=agency,
                defaults={
                    'description': grant_data['description'],
                    'funding_min': grant_data.get('funding_min'),
                    'funding_max': grant_data.get('funding_max'),
                    'closing_date': closing_date,
                    'duration_years': grant_data.get('duration_years', ''),
                    'status': grant_data.get('status', 'open'),
                    'icon_name': grant_data.get('icon_name', ''),
                    'match_score': 85,  # Sample match score
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Loaded {len(SAMPLE_GRANTS_DATA)} sample grants '
                f'({created_count} created, {updated_count} updated)'
            )
        )
