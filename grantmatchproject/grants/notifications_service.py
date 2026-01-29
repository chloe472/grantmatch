from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from .models import Notification, Application, Grant, GrantMatch, Project
from django.contrib.auth.models import User


class NotificationService:
    """Service for creating and managing notifications"""
    
    @staticmethod
    def create_notification(user, title, message, link=''):
        """Create a notification for a user"""
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            link=link
        )
        return notification
    
    @staticmethod
    def notify_application_submitted(application):
        """Notify user when application is submitted"""
        return NotificationService.create_notification(
            user=application.user,
            title='Application Submitted',
            message=f'Your application for {application.grant.title} has been submitted.',
            link=f'/grants/applications/{application.id}/proposal/'
        )
    
    @staticmethod
    def notify_application_approved(application):
        """Notify user when application is approved"""
        return NotificationService.create_notification(
            user=application.user,
            title='Application Approved',
            message=f'Great news! Your application for {application.grant.title} has been approved.',
            link=f'/grants/applications/{application.id}/proposal/'
        )
    
    @staticmethod
    def notify_application_rejected(application):
        """Notify user when application is rejected"""
        return NotificationService.create_notification(
            user=application.user,
            title='Application Status Update',
            message=f'Your application for {application.grant.title} has been rejected.',
            link=f'/grants/applications/{application.id}/proposal/'
        )
    
    @staticmethod
    def notify_deadline_reminder(application):
        """Notify user 1 week before application deadline"""
        return NotificationService.create_notification(
            user=application.user,
            title='Application Deadline Approaching',
            message=f'Your application for {application.grant.title} is due in 7 days.',
            link=f'/grants/applications/{application.id}/proposal/'
        )
    
    @staticmethod
    def notify_new_matching_grant(user, grant, project, match_score):
        """Notify user about new grant that matches their project"""
        return NotificationService.create_notification(
            user=user,
            title='New High Match Grant Available',
            message=f'{grant.title} ({match_score}% match) from {grant.agency.acronym} is now available for your project "{project.title}".',
            link=f'/grants/{grant.id}/'
        )
    
    @staticmethod
    def notify_saved_grant_reopened(user, grant):
        """Notify user when a saved/favorited grant becomes available again"""
        return NotificationService.create_notification(
            user=user,
            title='Saved Grant Now Open',
            message=f'{grant.title} from {grant.agency.acronym} has reopened!',
            link=f'/grants/{grant.id}/'
        )
    
    @staticmethod
    def notify_upcoming_deadline(user, grant):
        """Notify user about upcoming grant deadline"""
        days_left = grant.days_until_deadline if grant.days_until_deadline else 0
        return NotificationService.create_notification(
            user=user,
            title='Application Deadline Approaching',
            message=f'{grant.title} from {grant.agency.acronym} closes in {days_left} days.',
            link=f'/grants/{grant.id}/'
        )
    
    @staticmethod
    def check_application_deadlines():
        """Check for applications due in 7 days and send reminders"""
        # Get applications due in 7 days that haven't been submitted
        seven_days_later = timezone.now().date() + timedelta(days=7)
        
        applications = Application.objects.filter(
            status__in=['in_progress', 'submitted'],
            grant__closing_date=seven_days_later
        ).select_related('user', 'grant')
        
        for app in applications:
            # Check if reminder already exists
            existing = Notification.objects.filter(
                user=app.user,
                title='Application Deadline Approaching',
                created_at__date=timezone.now().date()
            ).exists()
            
            if not existing:
                NotificationService.notify_deadline_reminder(app)
    
    @staticmethod
    def check_saved_grants_reopened():
        """Check if any saved/favorited grants have reopened"""
        # Get all grants that were closed and are now open
        reopened_grants = Grant.objects.filter(
            status='open',
            updated_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        for grant in reopened_grants:
            # Check if any users have saved this grant
            saved_matches = GrantMatch.objects.filter(
                grant=grant,
                is_saved=True
            ).select_related('project__user')
            
            for match in saved_matches:
                # Check if notification already exists
                existing = Notification.objects.filter(
                    user=match.project.user,
                    title='Saved Grant Now Open',
                    created_at__date=timezone.now().date()
                ).filter(message__contains=grant.title).exists()
                
                if not existing:
                    NotificationService.notify_saved_grant_reopened(match.project.user, grant)
    
    @staticmethod
    def check_new_matching_grants():
        """Check for new grants that match existing projects"""
        # Get grants added in the last 24 hours
        new_grants = Grant.objects.filter(
            status='open',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).select_related('agency')
        
        # For each new grant, check projects that might match
        for grant in new_grants:
            # Get all users' projects
            projects = Project.objects.all().select_related('user')
            
            for project in projects:
                # Check if there's already a match record
                existing_match = GrantMatch.objects.filter(
                    grant=grant,
                    project=project
                ).exists()
                
                if not existing_match:
                    # Calculate match score (simplified - would be done in matching.py)
                    # This is a placeholder - actual matching logic should be integrated
                    match_score = grant.match_score  # Use pre-calculated match_score
                    
                    if match_score >= 80:  # Only notify for high matches
                        # Check if notification already exists
                        existing_notif = Notification.objects.filter(
                            user=project.user,
                            title='New High Match Grant Available',
                            created_at__date=timezone.now().date()
                        ).filter(message__contains=grant.title).exists()
                        
                        if not existing_notif:
                            NotificationService.notify_new_matching_grant(
                                project.user, 
                                grant, 
                                project, 
                                match_score
                            )
    
    @staticmethod
    def check_upcoming_deadlines():
        """Notify users about grants with upcoming deadlines"""
        # Get grants closing in the next 7 days
        today = timezone.now().date()
        seven_days = today + timedelta(days=7)
        
        upcoming_grants = Grant.objects.filter(
            status='open',
            closing_date__gte=today,
            closing_date__lte=seven_days
        ).select_related('agency')
        
        for grant in upcoming_grants:
            # Get users who have this grant saved or matched
            users_with_match = GrantMatch.objects.filter(
                grant=grant
            ).values_list('project__user', flat=True).distinct()
            
            for user_id in users_with_match:
                user = User.objects.get(id=user_id)
                
                # Check if notification already exists for today
                existing = Notification.objects.filter(
                    user=user,
                    title='Application Deadline Approaching',
                    created_at__date=timezone.now().date()
                ).filter(message__contains=grant.title).exists()
                
                if not existing:
                    NotificationService.notify_upcoming_deadline(user, grant)
