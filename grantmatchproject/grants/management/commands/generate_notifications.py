"""
Management command to generate notifications for users
Usage: python manage.py generate_notifications
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from grants.models import Notification, Application, Grant, Project, GrantMatch
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Generate notifications for users based on application status, deadlines, and new grants'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Generating notifications...'))

        # 1. Application approved notifications
        self.generate_application_approved_notifications()

        # 2. Application submitted notifications
        self.generate_application_submitted_notifications()

        # 3. Application in progress reminders
        self.generate_application_reminders()

        # 4. New grants published that match projects
        self.generate_new_grant_matches()

        # 5. Favorited unavailable grants that become available
        self.generate_favorited_grant_available_notifications()

        self.stdout.write(self.style.SUCCESS('Notifications generated successfully!'))

    def generate_application_approved_notifications(self):
        """Notify users when their applications are approved"""
        approved_apps = Application.objects.filter(
            status='approved',
            user__notifications__title__icontains='approved'
        ).exclude(
            user__notifications__message__icontains='approved'
        )

        for app in approved_apps:
            # Check if notification already exists
            existing = Notification.objects.filter(
                user=app.user,
                title__icontains='Application Approved',
                message__icontains=f'{app.grant.title}'
            ).exists()

            if not existing:
                Notification.objects.create(
                    user=app.user,
                    title='Application Approved',
                    message=f'Congratulations! Your application for "{app.grant.title}" has been approved.',
                    link=f'/grants/{app.grant.id}/'
                )

    def generate_application_submitted_notifications(self):
        """Notify users when their applications are submitted"""
        submitted_apps = Application.objects.filter(
            status='submitted'
        ).exclude(
            user__notifications__title__icontains='submitted'
        )

        for app in submitted_apps:
            # Check if notification already exists
            existing = Notification.objects.filter(
                user=app.user,
                title__icontains='Application Submitted',
                message__icontains=f'{app.grant.title}'
            ).exists()

            if not existing:
                Notification.objects.create(
                    user=app.user,
                    title='Application Submitted',
                    message=f'Your application for "{app.grant.title}" has been submitted successfully.',
                    link=f'/grants/{app.grant.id}/'
                )

    def generate_application_reminders(self):
        """Generate reminders for applications approaching deadline"""
        today = timezone.now().date()

        # Applications with deadline in 7 days
        upcoming_deadlines = Application.objects.filter(
            status='in_progress',
            grant__closing_date__gte=today,
            grant__closing_date__lte=today + timedelta(days=7)
        )

        for app in upcoming_deadlines:
            # Check project start date buffer requirement
            buffer_weeks = 4  # Default 4 weeks buffer
            project_start = app.project.project_start_date

            if project_start:
                # Calculate if there's enough buffer
                days_until_start = (project_start - today).days
                weeks_until_start = days_until_start / 7

                if weeks_until_start < buffer_weeks:
                    # Not enough buffer, adjust reminder
                    continue

            # Check if notification already exists for this deadline
            existing = Notification.objects.filter(
                user=app.user,
                title__icontains='Deadline Reminder',
                message__icontains=f'{app.grant.title}',
                created_at__date=today
            ).exists()

            if not existing:
                days_left = (app.grant.closing_date - today).days
                Notification.objects.create(
                    user=app.user,
                    title='Application Deadline Reminder',
                    message=f'Your application for "{app.grant.title}" is due in {days_left} days. Please complete and submit it soon.',
                    link=f'/applications/{app.id}/proposal/'
                )

    def generate_new_grant_matches(self):
        """Notify users of new grants that match their projects well"""
        # Get grants created in the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        new_grants = Grant.objects.filter(
            created_at__gte=yesterday,
            status='open'
        )

        # Also check for grants that were closed and reopened recently
        recently_reopened = Grant.objects.filter(
            updated_at__gte=yesterday,
            status='open'
        ).exclude(created_at__gte=yesterday)

        all_new_grants = list(new_grants) + list(recently_reopened)

        for grant in all_new_grants:
            # Find projects that would match this grant well (score > 70)
            matching_matches = GrantMatch.objects.filter(
                grant=grant,
                match_score__gte=70
            ).select_related('project')

            for match in matching_matches:
                project = match.project
                # Check if notification already exists
                existing = Notification.objects.filter(
                    user=project.user,
                    title__icontains='New Grant Match',
                    message__icontains=f'{grant.title}',
                    created_at__gte=yesterday
                ).exists()

                if not existing:
                    Notification.objects.create(
                        user=project.user,
                        title='New Grant Opportunity',
                        message=f'A new grant "{grant.title}" matches your project "{project.title}" with a {match.match_score}% compatibility score.',
                        link=f'/grants/{grant.id}/'
                    )

    def generate_favorited_grant_available_notifications(self):
        """Notify users when favorited unavailable grants become available"""
        # Find grants that were previously closed but are now open
        recently_opened = Grant.objects.filter(
            status='open',
            updated_at__gte=timezone.now() - timedelta(days=1)
        )

        for grant in recently_opened:
            # Find users who saved this grant when it was closed
            saved_matches = GrantMatch.objects.filter(
                grant=grant,
                is_saved=True,
                project__user__isnull=False
            )

            for match in saved_matches:
                # Check if this grant was previously unavailable (we'll assume if it was updated recently and is now open)
                # In a real implementation, you'd track status changes in a separate table

                existing = Notification.objects.filter(
                    user=match.project.user,
                    title__icontains='Grant Now Available',
                    message__icontains=f'{grant.title}',
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).exists()

                if not existing:
                    Notification.objects.create(
                        user=match.project.user,
                        title='Saved Grant Now Available',
                        message=f'Great news! The grant "{grant.title}" that you saved is now open for applications.',
                        link=f'/grants/{grant.id}/'
                    )