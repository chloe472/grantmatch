#!/usr/bin/env python
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantmatchproject.settings')
django.setup()

from grants.models import Notification, Grant
from django.contrib.auth.models import User

# Get or create test user
user = User.objects.first()
if not user:
    print("No users found. Please create a user first.")
    exit()

# Get a grant with closing date
grant = Grant.objects.filter(closing_date__isnull=False).first()

# Create test notifications
notifications = [
    {
        'title': 'Application Deadline Approaching',
        'message': f'Professional Capability Grant (Closed Grant Call) from NCSS closes in 4 days.',
        'link': '/grants/45/',
    },
    {
        'title': 'New Grant Match Found',
        'message': 'We found a new grant that matches your project "Active Aging Sports Program".',
        'link': '/grants/',
    },
    {
        'title': 'Application Status Update',
        'message': 'Your application for Communities of Care Grant has been submitted successfully.',
        'link': '/applications/',
    },
]

print(f"Creating notifications for user: {user.username}")

for notif_data in notifications:
    notification = Notification.objects.create(
        user=user,
        title=notif_data['title'],
        message=notif_data['message'],
        link=notif_data['link'],
        is_read=False
    )
    print(f"Created: {notification.title}")

print(f"\nCreated {len(notifications)} test notifications!")
print(f"Refresh your browser to see them.")
