from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from grants.models import Grant
from grants.notifications_service import NotificationService


class Command(BaseCommand):
    help = 'Create a test notification for a specific grant'
    
    def add_arguments(self, parser):
        parser.add_argument('grant_title', type=str, help='Title of the grant')
        parser.add_argument('--user', type=str, default='tomato', help='Username to create notification for')
    
    def handle(self, *args, **options):
        grant_title = options['grant_title']
        username = options['user']
        
        try:
            user = User.objects.get(username=username)
            grant = Grant.objects.get(title__icontains=grant_title)
            
            NotificationService.notify_upcoming_deadline(user, grant)
            self.stdout.write(self.style.SUCCESS(
                f'✓ Notification created for {user.username} about {grant.title}'
            ))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
        except Grant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Grant with title containing "{grant_title}" not found'))
