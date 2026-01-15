# Quick Start Guide - How to Run Your Project

## Step 1: Navigate to Project Directory

```powershell
cd grantmatchproject
```

## Step 2: Activate Virtual Environment (if you have one)

If you have a virtual environment set up:

```powershell
# If virtual environment is in the parent directory
..\venv\Scripts\Activate.ps1

# Or if it's in the current directory
.\venv\Scripts\Activate.ps1
```

**Note**: If you don't have a virtual environment, you can skip this step, but it's recommended.

## Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

This will install Django and all required packages including:
- Django 6.0.1
- requests (for API calls)
- beautifulsoup4 (for web scraping)
- lxml (for HTML parsing)

## Step 4: Create Database Tables

```powershell
python manage.py makemigrations
python manage.py migrate
```

This creates all the database tables for your models (Grant, Project, Agency, etc.).

## Step 5: Load Sample Grants Data

```powershell
python manage.py sync_grants --sample
```

This loads sample grant data so you can see the application in action.

## Step 6: Create a Superuser (Optional but Recommended)

```powershell
python manage.py createsuperuser
```

Follow the prompts to create an admin account. This lets you access the Django admin panel at `/admin/`.

## Step 7: Start the Development Server

```powershell
python manage.py runserver
```

You should see output like:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

## Step 8: Access Your Application

Open your web browser and go to:
- **Main Application**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/

## First Time Setup

1. **Register a new account** at http://127.0.0.1:8000/register/
2. **Login** with your new account
3. **Create a project** to start matching with grants
4. **Browse grants** to see available opportunities

## Troubleshooting

### "ModuleNotFoundError: No module named 'django'"
- Make sure you've activated your virtual environment
- Run `pip install -r requirements.txt`

### "No such table" errors
- Run `python manage.py migrate` again

### Port already in use
- The server might already be running
- Or use a different port: `python manage.py runserver 8001`

### Static files not loading
- Make sure the `static` folder exists in `grantmatchproject/`
- Run `python manage.py collectstatic` (for production)

## Common Commands

```powershell
# Run migrations
python manage.py migrate

# Create new migrations (after model changes)
python manage.py makemigrations

# Load sample grants
python manage.py sync_grants --sample

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver

# Start server on different port
python manage.py runserver 8001
```

## Next Steps

1. Create a project describing your organization's needs
2. Browse available grants
3. Save grants that match your project
4. Create applications for grants you want to apply for

Enjoy your Granted application! 🎉
