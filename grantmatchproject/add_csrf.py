with open('grantmatchproject/settings.py', 'r') as f:
    lines = f.readlines()

csrf_settings = '''
# CSRF and Security Settings
CSRF_TRUSTED_ORIGINS = [
    'https://grantmatch-405803716705.asia-southeast1.run.app',
    'https://*.run.app',
]

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG

'''

# Find where to insert (after ALLOWED_HOSTS line)
insert_idx = None
for i, line in enumerate(lines):
    if 'ALLOWED_HOSTS = os.getenv' in line and 'split' in line:
        insert_idx = i + 1
        break

if insert_idx is not None:
    lines.insert(insert_idx, csrf_settings)
    with open('grantmatchproject/settings.py', 'w') as f:
        f.writelines(lines)
    print('CSRF settings added successfully')
else:
    print('Could not find insertion point')
