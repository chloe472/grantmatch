from django.core.management.base import BaseCommand
from django.utils import timezone
from grants.models import Notification, Application, Grant, Project
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create sample notifications for testing'

    def handle(self, *args, **options):
        # Get first user
        try:
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('No users found. Create a user first.'))
                return

            # Create sample notifications
            notifications_data = [
                {
                    'title': 'Application Submitted',
                    'message': 'Your application for "Community Health Initiative Grant" has been successfully submitted.',
                    'link': '/applications/'
                },
                {
                    'title': 'Application Approved!',
                    'message': 'Congratulations! Your application for "Youth Development Program Grant" has been approved.',
                    'link': '/applications/'
                },
                {
                    'title': 'Application Deadline Approaching',
                    'message': 'Your application for "Environmental Conservation Grant" is due in 5 days. Don\'t forget to submit!',
                    'link': '/applications/'
                },
                {
                    'title': 'New Grant Match Found!',
                    'message': 'A new grant "Digital Inclusion Initiative" matches your project "Tech Access Program" with 85% compatibility.',
                    'link': '/grants/'
                },
                {
                    'title': 'Saved Grant Now Available!',
                    'message': 'The grant "Community Arts Funding" that you saved is now open for applications.',
                    'link': '/grants/'
                }
            ]

            for data in notifications_data:
                Notification.objects.create(
                    user=user,
                    title=data['title'],
                    message=data['message'],
                    link=data['link'],
                    is_read=False
                )

            self.stdout.write(self.style.SUCCESS(f'Created {len(notifications_data)} sample notifications'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating notifications: {e}'))