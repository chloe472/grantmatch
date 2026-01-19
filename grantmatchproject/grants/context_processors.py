from grants.models import Notification

def notifications_context_processor(request):
    """Add notification count and recent notifications to all template contexts"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        return {
            'unread_notifications': unread_count,
            'recent_notifications': recent_notifications
        }
    return {
        'unread_notifications': 0,
        'recent_notifications': []
    }