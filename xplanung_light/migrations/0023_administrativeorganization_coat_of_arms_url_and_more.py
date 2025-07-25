# Generated by Django 4.2.21 on 2025-07-14 13:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xplanung_light', '0022_remove_adminorgauser_user_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='administrativeorganization',
            name='coat_of_arms_url',
            field=models.URLField(blank=True, help_text='Hier bietet sich an den Link von Wikipedia zu übernehmen.', null=True, verbose_name='Link zum Wappen'),
        ),
        migrations.AddField(
            model_name='historicaladministrativeorganization',
            name='coat_of_arms_url',
            field=models.URLField(blank=True, help_text='Hier bietet sich an den Link von Wikipedia zu übernehmen.', null=True, verbose_name='Link zum Wappen'),
        ),
    ]
