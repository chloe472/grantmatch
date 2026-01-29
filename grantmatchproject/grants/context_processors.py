from .models import Notification


def notifications(request):
    """Add user notifications to context for all templates"""
    context = {
        'unread_notifications': 0,
        'user_notifications': [],
    }
    
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        user_notifs = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        
        context['unread_notifications'] = unread
        context['user_notifications'] = user_notifs
    
    return context
