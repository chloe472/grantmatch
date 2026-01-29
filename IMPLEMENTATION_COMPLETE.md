# Grant Section Fields Implementation - Setup Instructions

## Changes Completed

### 1. Grant Model Updates (`grants/models.py`)
✅ Added four new TextFields to the Grant model (all blank=True):
- `about_text` - About this grant section
- `who_can_apply_text` - Who can apply section  
- `when_to_apply_text` - When to apply section
- `funding_text` - Funding information section

The existing `description` field is preserved unchanged.

### 2. Django Migration (`grants/migrations/0008_add_section_fields.py`)
✅ Created migration file that adds the four new TextFields.
The migration depends on `0007_remove_grant_funding_info_and_more`.

### 3. Service Logic Updates (`grants/services.py`)
✅ Modified `sync_grant_by_id()` to:
- Render the OurSG instruction page with Playwright
- Detect clear section headings (3+ target headings)
- If headings found: use heading-aware extraction
- If not: use sentence-level classifier to bucket sentences into sections
- Populate `about_text`, `who_can_apply_text`, `when_to_apply_text`, `funding_text` fields
- Parse and populate `funding_min`, `funding_max` from funding text
- Preserve transaction safety and log updates

### 4. Template Updates (`grants/templates/grants/grant_detail.html`)
✅ Updated all four tabs to display new fields:
- "About this grant" → uses `grant.about_text` (fallback to `live_data.about_grant`, then `grant.description`)
- "Who can apply" → uses `grant.who_can_apply_text` (fallback to `live_data.who_can_apply`, then `grant.eligibility_criteria`)
- "When to apply" → uses `grant.when_to_apply_text` (fallback to `live_data.when_to_apply`)
- "How much funding" → uses `grant.funding_text` (fallback to table/text display logic)

All fields use `linebreaksbr` filter to preserve line breaks and render full content.

✅ CSS clamping overrides already applied to prevent truncation.

## Steps to Deploy

### Step 1: Apply Migration
```bash
cd /Users/ednachong/Documents/grantmatch/grantmatchproject
python3 manage.py migrate grants
```

### Step 2: Sync Young Changemakers Grant (nycycm)
First, find the grant by title or external ID:
```bash
python3 manage.py shell
>>> from grants.models import Grant
>>> g = Grant.objects.filter(title__icontains='young changemakers').first()
>>> print(g.id, g.external_id)  # Should print the DB id
>>> exit()
```

Then sync using the id:
```bash
python3 manage.py sync_grants --id <DB_ID>
```

Or if external_id is available:
```bash
python3 manage.py sync_grants --external-id nycycm
```

### Step 3: Verify
Open the grant detail page in browser:
- Navigate to the Young Changemakers grant
- Check "About this grant" tab → should show full OurSG content
- Check "When to apply", "Who can apply", "How much funding" tabs → all should show complete text
- No truncation should occur

## Files Modified
1. `/Users/ednachong/Documents/grantmatch/grantmatchproject/grants/models.py` - Added 4 TextFields
2. `/Users/ednachong/Documents/grantmatch/grantmatchproject/grants/migrations/0008_add_section_fields.py` - NEW migration file
3. `/Users/ednachong/Documents/grantmatch/grantmatchproject/grants/services.py` - Updated sync_grant_by_id()
4. `/Users/ednachong/Documents/grantmatch/grantmatchproject/grants/templates/grants/grant_detail.html` - Updated tabs

## Notes
- Existing grants keep their `description` field intact
- If OurSG page has no clear headings, sentence-level classifier assigns each sentence to exactly one section
- Funding amounts are parsed from `funding_text` into `funding_min`/`funding_max`
- All new fields are optional (blank=True) so no data loss on partial extraction
- Template has fallback chain: new field → live_data → old field (backward compatible)
