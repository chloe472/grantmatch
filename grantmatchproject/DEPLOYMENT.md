# Google Cloud Run Deployment Guide

This guide walks you through deploying the Granted application to Google Cloud Run.

## Prerequisites

- Google Cloud SDK installed and authenticated
- Project ID: `granted-484816`
- Cloud SQL instance: `grantmatch-pg` (already created)
- Database: `grantmatchdb` (already created)
- Postgres password set

## Step-by-Step Deployment

### 1. Verify Configuration

```powershell
gcloud config set project granted-484816
gcloud config set run/region asia-southeast1
```

### 2. Get Cloud SQL Connection Name

```powershell
gcloud sql instances describe grantmatch-pg --format="value(connectionName)"
```

Save this value - it will look like: `granted-484816:asia-southeast1:grantmatch-pg`

### 3. Create Artifact Registry Repository

```powershell
gcloud artifacts repositories create grantmatch-repo `
  --repository-format=docker `
  --location=asia-southeast1 `
  --description="Docker repository for Granted app"
```

### 4. Configure Docker Authentication

```powershell
gcloud auth configure-docker asia-southeast1-docker.pkg.dev
```

### 5. Build Docker Image

```powershell
docker build -t asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest .
```

### 6. Push Image to Artifact Registry

```powershell
docker push asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest
```

### 7. Generate Django Secret Key

Run this in Python to generate a secure secret key:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save the generated key for the next step.
### t56)t3x05d@$!q&1#w*wbm*&chcywp7nik9pe%mv$5jpwf+lvf

### 8. Deploy to Cloud Run

Replace the placeholders with your actual values:
- `YOUR_DB_PASSWORD` - the password you set for Cloud SQL postgres user
- `YOUR_DJANGO_SECRET_KEY` - generated in step 7
- `YOUR_GEMINI_API_KEY` - your Gemini API key from .env

```powershell
gcloud run deploy grantmatch `
  --image=asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest `
  --region=asia-southeast1 `
  --platform=managed `
  --allow-unauthenticated `
  --add-cloudsql-instances=granted-484816:asia-southeast1:grantmatch-pg `
  --set-env-vars="USE_CLOUD_SQL=True,DB_NAME=grantmatchdb,DB_USER=postgres,DB_PASSWORD=@iloveNUS1234,CLOUD_SQL_CONNECTION_NAME=granted-484816:asia-southeast1:grantmatch-pg,DJANGO_SECRET_KEY=t56)t3x05d@$!q&1#w*wbm*&chcywp7nik9pe%mv$5jpwf+lvf,GEMINI_API_KEY=AIzaSyD9uK6kUeArQNXW10CyN4rsLd44aG45xi8,DEBUG=False,ALLOWED_HOSTS=*" `
  --memory=512Mi `
  --cpu=1 `
  --timeout=300 `
  --max-instances=10 `
  --min-instances=0
```

### 9. Get the Service URL

After deployment completes, note the service URL (e.g., `https://grantmatch-xxxxx-as.a.run.app`).

### 10. Update ALLOWED_HOSTS

Redeploy with the actual Cloud Run URL:

```powershell
gcloud run services update grantmatch `
  --region=asia-southeast1 `
  --update-env-vars="ALLOWED_HOSTS=grantmatch-xxxxx-as.a.run.app,localhost,127.0.0.1"
```

Replace `grantmatch-xxxxx-as.a.run.app` with your actual Cloud Run URL (without `https://`).

### 11. Run Database Migrations

Create a Cloud Run job to run migrations:

```powershell
gcloud run jobs create grantmatch-migrate `
  --region=asia-southeast1 `
  --image=asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest `
  --add-cloudsql-instances=granted-484816:asia-southeast1:grantmatch-pg `
  --set-env-vars="USE_CLOUD_SQL=True,DB_NAME=grantmatchdb,DB_USER=postgres,DB_PASSWORD=YOUR_DB_PASSWORD,CLOUD_SQL_CONNECTION_NAME=granted-484816:asia-southeast1:grantmatch-pg,DJANGO_SECRET_KEY=YOUR_DJANGO_SECRET_KEY" `
  --command="python" `
  --args="manage.py,migrate"
```

Execute the migration:

```powershell
gcloud run jobs execute grantmatch-migrate --region=asia-southeast1
```

### 12. Create Superuser (Optional)

Create a job to create a Django superuser:

```powershell
# First, set superuser environment variables
$SUPERUSER_USERNAME = "admin"
$SUPERUSER_EMAIL = "admin@example.com"
$SUPERUSER_PASSWORD = "your-admin-password"

gcloud run jobs create grantmatch-superuser `
  --region=asia-southeast1 `
  --image=asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest `
  --add-cloudsql-instances=granted-484816:asia-southeast1:grantmatch-pg `
  --set-env-vars="USE_CLOUD_SQL=True,DB_NAME=grantmatchdb,DB_USER=postgres,DB_PASSWORD=YOUR_DB_PASSWORD,CLOUD_SQL_CONNECTION_NAME=granted-484816:asia-southeast1:grantmatch-pg,DJANGO_SECRET_KEY=YOUR_DJANGO_SECRET_KEY,DJANGO_SUPERUSER_USERNAME=$SUPERUSER_USERNAME,DJANGO_SUPERUSER_EMAIL=$SUPERUSER_EMAIL,DJANGO_SUPERUSER_PASSWORD=$SUPERUSER_PASSWORD" `
  --command="python" `
  --args="manage.py,createsuperuser,--noinput"

gcloud run jobs execute grantmatch-superuser --region=asia-southeast1
```

### 13. Sync Grants Data

Create a job to sync grants from OurSG Portal:

```powershell
gcloud run jobs create grantmatch-sync-grants `
  --region=asia-southeast1 `
  --image=asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest `
  --add-cloudsql-instances=granted-484816:asia-southeast1:grantmatch-pg `
  --set-env-vars="USE_CLOUD_SQL=True,DB_NAME=grantmatchdb,DB_USER=postgres,DB_PASSWORD=YOUR_DB_PASSWORD,CLOUD_SQL_CONNECTION_NAME=granted-484816:asia-southeast1:grantmatch-pg,DJANGO_SECRET_KEY=YOUR_DJANGO_SECRET_KEY" `
  --command="python" `
  --args="manage.py,sync_grants"

gcloud run jobs execute grantmatch-sync-grants --region=asia-southeast1
```

## Verify Deployment

Visit your Cloud Run URL in a browser:
```
https://grantmatch-xxxxx-as.a.run.app
```

You should see the Granted application homepage.

## Monitoring and Logs

View logs:
```powershell
gcloud run services logs read grantmatch --region=asia-southeast1 --limit=50
```

View service details:
```powershell
gcloud run services describe grantmatch --region=asia-southeast1
```

## Update Deployment

When you make code changes:

1. Rebuild and push the image:
```powershell
docker build -t asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest .
docker push asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest
```

2. Redeploy to Cloud Run:
```powershell
gcloud run services update grantmatch --region=asia-southeast1
```

## Custom Domain (Optional)

To use a custom domain:

1. Map your domain:
```powershell
gcloud run domain-mappings create --service=grantmatch --domain=yourdomain.com --region=asia-southeast1
```

2. Update ALLOWED_HOSTS:
```powershell
gcloud run services update grantmatch `
  --region=asia-southeast1 `
  --update-env-vars="ALLOWED_HOSTS=yourdomain.com,grantmatch-xxxxx-as.a.run.app"
```

## Troubleshooting

### Check deployment status
```powershell
gcloud run services describe grantmatch --region=asia-southeast1
```

### View recent logs
```powershell
gcloud run services logs read grantmatch --region=asia-southeast1 --limit=100
```

### Test database connection
Create a temporary job to test connection:
```powershell
gcloud run jobs create test-db `
  --region=asia-southeast1 `
  --image=asia-southeast1-docker.pkg.dev/granted-484816/grantmatch-repo/web:latest `
  --add-cloudsql-instances=granted-484816:asia-southeast1:grantmatch-pg `
  --set-env-vars="USE_CLOUD_SQL=True,DB_NAME=grantmatchdb,DB_USER=postgres,DB_PASSWORD=YOUR_DB_PASSWORD" `
  --command="python" `
  --args="manage.py,dbshell,--command,SELECT version();"
```

## Cost Optimization

- Set `--min-instances=0` to scale to zero when not in use
- Use `--memory=512Mi` for basic workloads
- Monitor usage in Cloud Console > Cloud Run

## Security Best Practices

1. Never commit secrets to Git
2. Use Secret Manager for sensitive values (alternative to env vars)
3. Enable Cloud Armor for DDoS protection (if needed)
4. Regularly update dependencies
5. Set up Cloud SQL automated backups

## Next Steps

- Set up Cloud SQL backups
- Configure Cloud Monitoring alerts
- Set up CI/CD with Cloud Build or GitHub Actions
- Consider Cloud CDN for static files at scale
