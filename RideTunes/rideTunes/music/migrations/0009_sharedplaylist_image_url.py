# Generated by Django 4.1.7 on 2023-05-19 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0008_notification_playlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharedplaylist',
            name='image_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
