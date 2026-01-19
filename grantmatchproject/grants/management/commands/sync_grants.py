"""
Management command to sync grants from OurSG Grants Portal
Usage: python manage.py sync_grants [--fetch-logos]
"""
from django.core.management.base import BaseCommand
from grants.services import SGGrantsService
from grants.models import Grant, Agency


class Command(BaseCommand):
    help = 'Sync grants from OurSG Grants Portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing grants',
        )
        parser.add_argument(
            '--fetch-logos',
            action='store_true',
            help='Also fetch agency logos after syncing grants',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Fetching grants from OurSG Grants Portal...'))
        service = SGGrantsService()
        
        try:
            # Sync grants to database
            result = service.sync_grants_to_db()
            
            # Report results
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully synced {result["total"]} grants: '
                    f'{result["created"]} created, {result["updated"]} updated, {result["skipped"]} skipped'
                )
            )
            
            # Remove grants with empty external_id (old invalid data)
            old_invalid_grants = Grant.objects.filter(external_id__exact='')
            if old_invalid_grants.exists():
                count = old_invalid_grants.count()
                old_invalid_grants.delete()
                self.stdout.write(self.style.WARNING(f'Removed {count} grants with missing external IDs'))
            
            # Optionally fetch logos
            if options['fetch_logos']:
                self.stdout.write(self.style.SUCCESS('\nFetching agency logos...'))
                try:
                    from grants.logo_service import LogoFetchService
                    logo_service = LogoFetchService()
                    agencies = Agency.objects.all()
                    logo_service.fetch_all_agency_logos(list(agencies))
                    logo_service.update_agency_logo_urls(list(agencies))
                    self.stdout.write(self.style.SUCCESS('Logos fetched and updated!'))
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Could not fetch logos: {e}')
                    )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error syncing grants: {e}')
            )