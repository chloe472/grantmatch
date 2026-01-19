from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from grants.models import Notification, Application, Grant, Project, GrantMatch
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Generate notifications for users based on application status, deadlines, and grant matches'

    def handle(self, *args, **options):
        self.stdout.write('Generating notifications...')

        # 1. Application approved notifications
        self.generate_application_approved_notifications()

        # 2. Application submitted notifications
        self.generate_application_submitted_notifications()

        # 3. Application deadline reminders
        self.generate_deadline_reminders()

        # 4. New grant matches
        self.generate_new_grant_matches()

        # 5. Favorited grants now available
        self.generate_favorited_grants_available()

        self.stdout.write(self.style.SUCCESS('Notifications generated successfully'))

    def generate_application_approved_notifications(self):
        """Notify users when their applications are approved"""
        # Find applications that were recently approved (within last day)
        recent_approvals = Application.objects.filter(
            status='approved',
            updated_at__gte=timezone.now() - timedelta(days=1)
        ).select_related('user', 'grant')

        for application in recent_approvals:
            # Check if notification already exists
            existing = Notification.objects.filter(
                user=application.user,
                title__icontains='approved',
                message__icontains=str(application.grant.id),
                created_at__gte=timezone.now() - timedelta(days=1)
            ).exists()

            if not existing:
                Notification.objects.create(
                    user=application.user,
                    title='Application Approved!',
                    message=f'Your application for "{application.grant.title}" has been approved. Congratulations!',
                    link=f'/grants/{application.grant.id}/'
                )

    def generate_application_submitted_notifications(self):
        """Notify users when their applications are submitted"""
        # Find applications that were recently submitted
        recent_submissions = Application.objects.filter(
            status='submitted',
            submitted_at__gte=timezone.now() - timedelta(days=1)
        ).select_related('user', 'grant')

        for application in recent_submissions:
            # Check if notification already exists
            existing = Notification.objects.filter(
                user=application.user,
                title__icontains='submitted',
                message__icontains=str(application.grant.id),
                created_at__gte=timezone.now() - timedelta(days=1)
            ).exists()

            if not existing:
                Notification.objects.create(
                    user=application.user,
                    title='Application Submitted',
                    message=f'Your application for "{application.grant.title}" has been successfully submitted.',
                    link=f'/applications/{application.id}/proposal/'
                )

    def generate_deadline_reminders(self):
        """Generate deadline reminders for applications"""
        # Find applications that are in progress and approaching deadline
        applications_in_progress = Application.objects.filter(
            status='in_progress'
        ).select_related('grant', 'project', 'user')

        for application in applications_in_progress:
            if application.grant.closing_date:
                days_until_deadline = (application.grant.closing_date - timezone.now().date()).days

                # Check for 1-week reminder
                if days_until_deadline <= 7 and days_until_deadline > 0:
                    # Check if notification already exists for this deadline
                    existing = Notification.objects.filter(
                        user=application.user,
                        title__icontains='deadline',
                        message__icontains=str(application.grant.id),
                        created_at__gte=application.grant.closing_date - timedelta(days=8)
                    ).exists()

                    if not existing:
                        Notification.objects.create(
                            user=application.user,
                            title='Application Deadline Approaching',
                            message=f'Your application for "{application.grant.title}" is due in {days_until_deadline} day{"s" if days_until_deadline != 1 else ""}. Don\'t forget to submit!',
                            link=f'/applications/{application.id}/proposal/'
                        )

    def generate_new_grant_matches(self):
        """Generate notifications for new grants that match user's projects"""
        # Get all users with projects
        users_with_projects = User.objects.filter(projects__isnull=False).distinct()

        for user in users_with_projects:
            # Get user's projects
            user_projects = Project.objects.filter(user=user)

            # Find grants that are newly opened or reopened and match user's projects
            recent_grants = Grant.objects.filter(
                Q(status='open') &
                (Q(created_at__gte=timezone.now() - timedelta(days=7)) |  # New grants
                 Q(updated_at__gte=timezone.now() - timedelta(days=7)))   # Recently updated (potentially reopened)
            )

            for grant in recent_grants:
                # Check if this grant matches any of user's projects (score >= 70)
                for project in user_projects:
                    match_score = self.calculate_match_score(project, grant)
                    if match_score >= 70:
                        # Check if notification already exists
                        existing = Notification.objects.filter(
                            user=user,
                            title__icontains='New grant match',
                            message__icontains=str(grant.id),
                            created_at__gte=timezone.now() - timedelta(days=7)
                        ).exists()

                        if not existing:
                            Notification.objects.create(
                                user=user,
                                title='New Grant Match Found!',
                                message=f'A new grant "{grant.title}" matches your project "{project.title}" with {match_score}% compatibility.',
                                link=f'/grants/{grant.id}/'
                            )
                        break  # Only send one notification per grant per user

    def generate_favorited_grants_available(self):
        """Notify users when favorited grants become available"""
        # Get all saved/favorited grants
        saved_matches = GrantMatch.objects.filter(is_saved=True).select_related('grant', 'project__user')

        for match in saved_matches:
            grant = match.grant
            user = match.project.user

            # Check if grant was previously unavailable but is now available
            if grant.status == 'open':
                # Check if grant was recently opened (within last week)
                was_recently_opened = (
                    grant.created_at >= timezone.now() - timedelta(days=7) or
                    grant.updated_at >= timezone.now() - timedelta(days=7)
                )

                if was_recently_opened:
                    # Check if notification already exists
                    existing = Notification.objects.filter(
                        user=user,
                        title__icontains='now available',
                        message__icontains=str(grant.id),
                        created_at__gte=timezone.now() - timedelta(days=7)
                    ).exists()

                    if not existing:
                        Notification.objects.create(
                            user=user,
                            title='Saved Grant Now Available!',
                            message=f'The grant "{grant.title}" that you saved is now open for applications.',
                            link=f'/grants/{grant.id}/'
                        )

    def calculate_match_score(self, project, grant):
        """Simple match score calculation (fallback if Gemini not available)"""
        score = 0

        # Focus area matching
        if project.focus_area and project.focus_area.lower() in grant.title.lower():
            score += 20
        if project.focus_area and project.focus_area.lower() in grant.description.lower():
            score += 15

        # Budget matching
        if project.budget_required_min and grant.funding_min:
            if project.budget_required_min <= grant.funding_max:
                score += 15

        # Beneficiary matching
        if project.beneficiary_types:
            grant_text = (grant.title + grant.description + grant.eligibility_criteria).lower()
            for beneficiary in project.beneficiary_types:
                if beneficiary.lower() in grant_text:
                    score += 10
                    break

        return min(score, 100)