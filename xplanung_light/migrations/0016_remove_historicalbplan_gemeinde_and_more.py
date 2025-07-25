# Generated by Django 4.2.21 on 2025-06-30 13:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xplanung_light', '0015_historicalbplanbeteiligung_bplanbeteiligung'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalbplan',
            name='gemeinde',
        ),
        migrations.RemoveField(
            model_name='bplan',
            name='gemeinde',
        ),
        migrations.AlterField(
            model_name='bplanbeteiligung',
            name='bekanntmachung_datum',
            field=models.DateField(help_text='Datum der Bekanntmachung des Verfahrens', verbose_name='Datum der Bekanntmachung'),
        ),
        migrations.AlterField(
            model_name='bplanbeteiligung',
            name='end_datum',
            field=models.DateField(help_text='Enddatum des Beteiligungsverfahrens', verbose_name='Ende'),
        ),
        migrations.AlterField(
            model_name='bplanbeteiligung',
            name='start_datum',
            field=models.DateField(help_text='Datum des Beginns des Beteiligungsverfahrens', verbose_name='Beginn'),
        ),
        migrations.AlterField(
            model_name='bplanbeteiligung',
            name='typ',
            field=models.CharField(choices=[('1000', 'Öffentliche Auslegung'), ('2000', 'Träger öffentlicher Belange')], db_index=True, default='1000', help_text='Typ des Beteiligungsverfahrens - aktuell Auslegung oder TÖB', max_length=5, verbose_name='Typ des Beteiligungsverfahrens'),
        ),
        migrations.AlterField(
            model_name='historicalbplanbeteiligung',
            name='bekanntmachung_datum',
            field=models.DateField(help_text='Datum der Bekanntmachung des Verfahrens', verbose_name='Datum der Bekanntmachung'),
        ),
        migrations.AlterField(
            model_name='historicalbplanbeteiligung',
            name='end_datum',
            field=models.DateField(help_text='Enddatum des Beteiligungsverfahrens', verbose_name='Ende'),
        ),
        migrations.AlterField(
            model_name='historicalbplanbeteiligung',
            name='start_datum',
            field=models.DateField(help_text='Datum des Beginns des Beteiligungsverfahrens', verbose_name='Beginn'),
        ),
        migrations.AlterField(
            model_name='historicalbplanbeteiligung',
            name='typ',
            field=models.CharField(choices=[('1000', 'Öffentliche Auslegung'), ('2000', 'Träger öffentlicher Belange')], db_index=True, default='1000', help_text='Typ des Beteiligungsverfahrens - aktuell Auslegung oder TÖB', max_length=5, verbose_name='Typ des Beteiligungsverfahrens'),
        ),
        migrations.AddField(
            model_name='bplan',
            name='gemeinde',
            field=models.ManyToManyField(to='xplanung_light.administrativeorganization'),
        ),
    ]
