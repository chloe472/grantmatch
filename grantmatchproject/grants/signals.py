from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application
from .notifications_service import NotificationService


@receiver(post_save, sender=Application)
def application_status_changed(sender, instance, created, update_fields, **kwargs):
    """Signal handler for application status changes"""
    if created:
        # New application created
        NotificationService.notify_application_submitted(instance)
    elif update_fields and 'status' in update_fields:
        # Application status was updated
        if instance.status == 'approved':
            NotificationService.notify_application_approved(instance)
        elif instance.status == 'rejected':
            NotificationService.notify_application_rejected(instance)
