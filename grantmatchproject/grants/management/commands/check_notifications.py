from django.core.management.base import BaseCommand
from grants.notifications_service import NotificationService


class Command(BaseCommand):
    help = 'Check for notification triggers and create notifications'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            help='Type of check to run: deadlines, grants, saved, upcoming, or all'
        )
    
    def handle(self, *args, **options):
        check_type = options['type']
        
        if check_type in ['deadlines', 'all']:
            self.stdout.write('Checking application deadlines...')
            NotificationService.check_application_deadlines()
            self.stdout.write(self.style.SUCCESS('✓ Deadline check complete'))
        
        if check_type in ['grants', 'all']:
            self.stdout.write('Checking for new matching grants...')
            NotificationService.check_new_matching_grants()
            self.stdout.write(self.style.SUCCESS('✓ New grants check complete'))
        
        if check_type in ['saved', 'all']:
            self.stdout.write('Checking saved grants that reopened...')
            NotificationService.check_saved_grants_reopened()
            self.stdout.write(self.style.SUCCESS('✓ Saved grants check complete'))
        
        if check_type in ['upcoming', 'all']:
            self.stdout.write('Checking upcoming grant deadlines...')
            NotificationService.check_upcoming_deadlines()
            self.stdout.write(self.style.SUCCESS('✓ Upcoming deadlines check complete'))
        
        if check_type == 'all':
            self.stdout.write(self.style.SUCCESS('\nAll notification checks completed successfully!'))
