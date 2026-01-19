# Agency Logos

This directory contains agency logos for the following agencies:

- **AIC** (Agency for Integrated Care) - `aic.png` or `aic.jpg`
- **MSF** (Ministry of Social and Family Development) - `msf.png` or `msf.jpg`
- **HPB** (Health Promotion Board) - `hpb.png` or `hpb.jpg`
- **NCSS** (National Council of Social Service) - `ncss.png` or `ncss.jpg`
- **IMDA** (Infocomm Media Development Authority) - `imda.png` or `imda.jpg`

## Automatic Logo Fetching (Recommended)

You can automatically fetch logos from the Our SG Grants Portal and agency websites:

```bash
# Fetch all agency logos
python manage.py fetch_logos

# Fetch logo for a specific agency
python manage.py fetch_logos --agency AIC

# Fetch logos and update database automatically
python manage.py fetch_logos --update-db
```

The command will:
1. Try to find logos on the Our SG Grants Portal
2. If not found, fetch from official agency websites
3. Download and save logos to this directory
4. Optionally update the Agency model's `logo_url` field

## Manual Logo Upload

If automatic fetching doesn't work, you can manually add logos:

1. Download logos from:
   - Our SG Grants Portal: https://www.giving.sg/our-sg-grants
   - Official agency websites:
     - AIC: https://www.aic.sg
     - MSF: https://www.msf.gov.sg
     - HPB: https://www.hpb.gov.sg
     - NCSS: https://www.ncss.gov.sg
     - IMDA: https://www.imda.gov.sg

2. Save them in this directory with the naming convention: `{agency_acronym}.png` (lowercase)

3. The system will automatically detect and use them

## Logo Specifications

- Size: 48x48px (will be displayed in rounded square containers)
- Format: PNG, JPG, or SVG
- Recommended: Transparent background PNG for best results

## Using logo_url in Database

You can also set the `logo_url` field in the Agency model to point to:
- External URLs (e.g., `https://www.aic.sg/logo.png`)
- Static file paths (e.g., `/static/agency-logos/aic.png`)

The `fetch_logos --update-db` command will automatically set these for you.
