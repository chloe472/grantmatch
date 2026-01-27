# CSRF and Security Settings
CSRF_TRUSTED_ORIGINS = [
    'https://grantmatch-405803716705.asia-southeast1.run.app',
    'https://*.run.app',
]

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
