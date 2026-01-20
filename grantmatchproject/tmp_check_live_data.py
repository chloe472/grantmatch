import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','grantmatchproject.settings')
import django
django.setup()
from grants.models import Grant
from grants.services import SGGrantsService

service = SGGrantsService()

titles = ['Active Citizen Grant', 'Communities of Care Grant']
for t in titles:
    g = Grant.objects.filter(title__icontains=t).first()
    print('\n---', t, '---')
    if not g:
        print('Grant not found')
        continue
    grant_value = None
    import re
    if g.source_url:
        match = re.search(r'/grants/([^/]+)/', g.source_url)
        if match:
            grant_value = match.group(1)
    data = service.fetch_grant_detail(grant_value=grant_value, external_id=g.external_id)
    if not data:
        print('No live data')
        continue
    print('when_to_apply:\n', data.get('when_to_apply'))
    print('\nfunding_info:\n', data.get('funding_info'))
    print('\nhow_to_apply:\n', data.get('how_to_apply'))
    print('\ndocument_links:\n', data.get('document_links'))
