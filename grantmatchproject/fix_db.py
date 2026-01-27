with open('grantmatchproject/settings.py', 'r') as f:
    lines = f.readlines()

# Find the database section
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "# Database" in line and i+1 < len(lines) and "https://docs.djangoproject.com" in lines[i+1]:
        start_idx = i + 3
    if start_idx is not None and "# Password validation" in line:
        end_idx = i
        break

if start_idx and end_idx:
    new_db_config = """# Use Cloud SQL in production, SQLite in development
if os.getenv('USE_CLOUD_SQL') == 'True':
    # Production: Cloud SQL PostgreSQL
    # Cloud SQL Proxy provides connection via localhost:5432 when deployed on Cloud Run
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'grantmatchdb'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': '127.0.0.1',
            'PORT': '5432',
        }
    }
else:
    # Development: SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


"""
    lines = lines[:start_idx] + [new_db_config] + lines[end_idx:]
    with open('grantmatchproject/settings.py', 'w') as f:
        f.writelines(lines)
    print('Database config updated')
else:
    print(f'Could not find markers: start={start_idx}, end={end_idx}')
