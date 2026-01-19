#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
sys.path.append(os.path.dirname(__file__))
django.setup()

from grants.models import Notification
from django.contrib.auth.models import User

def main():
    # Get first user
    user = User.objects.first()
    if not user:
        print("No users found in database")
        return

    # Get all notifications for this user
    notifications = Notification.objects.filter(user=user).order_by('-created_at')

    print(f"Found {notifications.count()} notifications for user: {user.username}")
    print("=" * 60)

    for i, notification in enumerate(notifications, 1):
        print(f"{i}. {notification.title}")
        print(f"   {notification.message}")
        print(f"   Read: {notification.is_read}")
        print(f"   Created: {notification.created_at}")
        if notification.link:
            print(f"   Link: {notification.link}")
        print("-" * 40)

if __name__ == '__main__':
    main()