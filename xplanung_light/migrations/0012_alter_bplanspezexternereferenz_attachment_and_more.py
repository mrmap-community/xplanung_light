# Generated by Django 4.2.21 on 2025-06-13 06:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('xplanung_light', '0011_bplanspezexternereferenz'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bplanspezexternereferenz',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='uploads', verbose_name='Dokument'),
        ),
        migrations.AlterField(
            model_name='bplanspezexternereferenz',
            name='bplan',
            field=models.ForeignKey(help_text='BPlan', on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='xplanung_light.bplan', verbose_name='BPlan'),
        ),
        migrations.AlterField(
            model_name='bplanspezexternereferenz',
            name='typ',
            field=models.CharField(choices=[('1000', 'Beschreibung'), ('1010', 'Begruendung'), ('1020', 'Legende'), ('1030', 'Rechtsplan'), ('1040', 'Plangrundlage'), ('1050', 'Umweltbericht'), ('1060', 'Satzung'), ('1065', 'Verordnung'), ('1070', 'Karte'), ('1080', 'Erlaeuterung'), ('1090', 'ZusammenfassendeErklaerung'), ('2000', 'Koordinatenliste'), ('2100', 'Grundstuecksverzeichnis'), ('2200', 'Pflanzliste'), ('2300', 'Gruenordnungsplan'), ('2400', 'Erschliessungsvertrag'), ('2500', 'Durchfuehrungsvertrag'), ('2600', 'StaedtebaulicherVertrag'), ('2700', 'UmweltbezogeneStellungnahmen'), ('2800', 'Beschluss'), ('2900', 'VorhabenUndErschliessungsplan'), ('3000', 'MetadatenPlan'), ('3100', 'StaedtebaulEntwicklungskonzeptInnenentwicklung'), ('4000', 'Genehmigung'), ('5000', 'Bekanntmachung'), ('6000', 'Schutzgebietsverordnung'), ('9998', 'Rechtsverbindlich'), ('9999', 'Informell')], db_index=True, default='1000', help_text='Typ / Inhalt des referierten Dokuments oder Rasterplans', max_length=5, verbose_name='Typ / Inhalt des referierten Dokuments oder Rasterplans'),
        ),
    ]
