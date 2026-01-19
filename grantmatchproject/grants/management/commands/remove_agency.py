from django.core.management.base import BaseCommand
from grants.models import Agency, Grant
from django.db.models import Q


class Command(BaseCommand):
    help = 'Remove an agency and optionally its grants from the database'

    def add_arguments(self, parser):
        parser.add_argument('acronym', type=str, help='Agency acronym to remove (e.g., TB)')
        parser.add_argument(
            '--remove-grants',
            action='store_true',
            help='Also remove all grants associated with this agency',
        )

    def handle(self, *args, **options):
        acronym = options['acronym'].upper()
        remove_grants = options['remove_grants']

        try:
            agency = Agency.objects.get(acronym=acronym)
            
            # Get associated grants count
            grants_count = Grant.objects.filter(agency=agency).count()
            
            if grants_count > 0 and not remove_grants:
                self.stdout.write(
                    self.style.WARNING(
                        f'\nWarning: Agency "{acronym}" has {grants_count} associated grants.\n'
                        'Use --remove-grants flag to remove them as well.'
                    )
                )
                return
            
            # Remove grants if requested
            if remove_grants and grants_count > 0:
                Grant.objects.filter(agency=agency).delete()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Removed {grants_count} grants associated with {acronym}')
                )
            
            # Remove the agency
            agency.delete()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Successfully removed agency "{acronym}"')
            )
            
        except Agency.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'✗ Agency "{acronym}" not found in database')
            )
