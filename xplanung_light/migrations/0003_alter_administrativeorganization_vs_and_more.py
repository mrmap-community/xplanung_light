# Generated by Django 4.2.21 on 2025-06-03 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xplanung_light', '0002_historicalbplan_bplan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='administrativeorganization',
            name='vs',
            field=models.CharField(blank=True, default='00', help_text='Eindeutiger zweistelliger Schlüssel für den Gemeindeverband', max_length=2, null=True, verbose_name='Gemeindeverbandsschlüssel'),
        ),
        migrations.AlterField(
            model_name='historicaladministrativeorganization',
            name='vs',
            field=models.CharField(blank=True, default='00', help_text='Eindeutiger zweistelliger Schlüssel für den Gemeindeverband', max_length=2, null=True, verbose_name='Gemeindeverbandsschlüssel'),
        ),
    ]
