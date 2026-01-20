# Granted - AI-Powered Funding Platform

Problem Statement: TSAO 1 Grants
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

4. **Configure Gemini API Key** (for AI-powered matching):
   ```bash
   
   Manually create a `.env` file in the `grantmatchproject` directory with:
   ```
   GEMINI_API_KEY=your_actual_api_key_here
   ```
   
   **Note**: If you don't configure the API key, the system will use a simple fallback matching algorithm instead of AI-powered matching.

5. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create a superuser** (optional, for admin access):
   ```bash
   python manage.py createsuperuser
   ```

7. **Sync grants from OurSG Grants Portal**:
   ```bash
   python manage.py sync_grants 
   ```

8. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

9. **Access the application**:
   - Open your browser and go to `http://127.0.0.1:8000`
   - Register a new account or login

## Gemini AI Integration

The application uses Google's Gemini AI for intelligent grant matching. When you create a project, the system automatically:

1. Analyzes your project details (description, focus area, budget, beneficiaries, etc.)
2. Compares it against all available grants using Gemini AI
3. Generates match scores (0-100) and specific match reasons
4. Creates matches for grants with 70%+ compatibility

### How It Works

- **AI-Powered Analysis**: Gemini analyzes project goals, budget compatibility, beneficiary alignment, focus areas, timelines, and eligibility criteria
- **Intelligent Scoring**: Provides nuanced match scores (90-100: Excellent, 80-89: Strong, 70-79: Good, below 70: Not recommended)
- **Specific Reasons**: Generates 3 clear, actionable reasons for each match
- **Fallback Logic**: If Gemini API is unavailable, falls back to keyword-based matching

### Getting a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key and add it to your `.env` file

## OurSG Grants Portal Integration

The application includes integration with Singapore's OurSG Grants Portal (https://oursggrants.gov.sg/).

### Syncing Grants

To sync grants from the portal:

```bash
# Fetch from OurSG Grants Portal
python manage.py sync_grants

# Also fetch agency logos
python manage.py sync_grants --fetch-logos
```

### Data Integration Service

The `grants/services.py` file contains the `SGGrantsService` class which handles:
- API integration (when available)
- Web scraping fallback (use responsibly and in compliance with terms)
- Data parsing and transformation
- Database synchronization

**Note**: The actual API endpoints for OurSG Grants Portal may need to be configured. Check the Singapore Government Developer Portal (https://developer.tech.gov.sg/) for official API access.

### Fetching Agency Logos

You can automatically fetch agency logos from the Our SG Grants Portal and official agency websites:

```bash
# Fetch all agency logos
python manage.py fetch_logos

# Fetch logo for a specific agency
python manage.py fetch_logos --agency AIC

# Fetch logos and automatically update database
python manage.py fetch_logos --update-db
```

The command will:
1. Try to find logos on the Our SG Grants Portal
2. If not found, fetch from official agency websites (AIC, MSF, HPB, NCSS, IMDA)
3. Download and save logos to `/static/agency-logos/`
4. Optionally update the Agency model's `logo_url` field

**Alternative**: You can also manually download logos and place them in `/static/agency-logos/` with the naming convention: `{agency_acronym}.png` (lowercase, e.g., `aic.png`)

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
```p

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
