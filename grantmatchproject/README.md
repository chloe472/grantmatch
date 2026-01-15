# Granted - AI-Powered Funding Platform

A Django-based web application for matching organizations with grant opportunities, integrated with Singapore's OurSG Grants Portal.

## Features

- **Dashboard**: Overview of grant opportunities, matches, and deadlines
- **Project Management**: Create and manage projects for grant matching
- **Grant Browsing**: Browse and search through available grants
- **AI-Powered Matching**: Automatic matching of projects with relevant grants
- **Application Tracking**: Track grant applications through their lifecycle
- **OurSG Grants Integration**: Sync grants from Singapore's official grants portal

## Setup Instructions

### Prerequisites

- Python 3.8+
- pip
- virtualenv (recommended)

### Installation

1. **Clone the repository** (if not already done):
   ```bash
   cd grantmatchproject
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create a superuser** (optional, for admin access):
   ```bash
   python manage.py createsuperuser
   ```

6. **Load sample grants data**:
   ```bash
   python manage.py sync_grants --sample
   ```

7. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

8. **Access the application**:
   - Open your browser and go to `http://127.0.0.1:8000`
   - Register a new account or login

## OurSG Grants Portal Integration

The application includes integration with Singapore's OurSG Grants Portal (https://oursggrants.gov.sg/).

### Syncing Grants

To sync grants from the portal:

```bash
# Use sample data (for development)
python manage.py sync_grants --sample

# Fetch from actual portal (when API/scraping is configured)
python manage.py sync_grants
```

### Data Integration Service

The `grants/services.py` file contains the `SGGrantsService` class which handles:
- API integration (when available)
- Web scraping fallback (use responsibly and in compliance with terms)
- Data parsing and transformation
- Database synchronization

**Note**: The actual API endpoints for OurSG Grants Portal may need to be configured. Check the Singapore Government Developer Portal (https://developer.tech.gov.sg/) for official API access.

## Project Structure

```
grantmatchproject/
├── grants/                    # Main application
│   ├── models.py             # Database models
│   ├── views.py              # View functions
│   ├── urls.py               # URL routing
│   ├── services.py           # SG Grants integration service
│   ├── templates/            # HTML templates
│   └── management/commands/  # Management commands
├── static/                   # Static files (CSS, JS)
│   └── css/
│       └── style.css
├── grantmatchproject/        # Django project settings
│   ├── settings.py
│   └── urls.py
└── manage.py
```

## Key Models

- **Grant**: Grant opportunities from various agencies
- **Agency**: Government agencies providing grants
- **Project**: User projects for grant matching
- **GrantMatch**: AI-calculated matches between projects and grants
- **Application**: Grant applications submitted by users
- **UserProfile**: Extended user information

## Development

### Adding New Features

1. Create models in `grants/models.py`
2. Create views in `grants/views.py`
3. Add URL patterns in `grants/urls.py`
4. Create templates in `grants/templates/grants/`
5. Update CSS in `static/css/style.css`

### Running Tests

```bash
python manage.py test
```

## Production Deployment

Before deploying to production:

1. Set `DEBUG = False` in `settings.py`
2. Set a secure `SECRET_KEY`
3. Configure `ALLOWED_HOSTS`
4. Set up proper database (PostgreSQL recommended)
5. Configure static files serving
6. Set up SSL/HTTPS
7. Configure environment variables for sensitive data

## License

This project is for educational/demonstration purposes.

## References

- OurSG Grants Portal: https://oursggrants.gov.sg/
- Singapore Government Developer Portal: https://developer.tech.gov.sg/
- Django Documentation: https://docs.djangoproject.com/
