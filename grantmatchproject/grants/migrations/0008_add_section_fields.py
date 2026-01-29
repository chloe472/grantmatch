# Generated migration to add section-specific text fields to Grant model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grants', '0007_remove_grant_funding_info_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='grant',
            name='about_text',
            field=models.TextField(blank=True, help_text='About this grant section'),
        ),
        migrations.AddField(
            model_name='grant',
            name='who_can_apply_text',
            field=models.TextField(blank=True, help_text='Who can apply section'),
        ),
        migrations.AddField(
            model_name='grant',
            name='when_to_apply_text',
            field=models.TextField(blank=True, help_text='When to apply section'),
        ),
        migrations.AddField(
            model_name='grant',
            name='funding_text',
            field=models.TextField(blank=True, help_text='Funding information section'),
        ),
    ]
