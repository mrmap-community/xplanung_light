"""Repariert die räumlichen Indizes der Geometrie-Spalten.

Auf Spatialite baut SQLite für jeden AlterField die ganze Tabelle neu; Django
stellt danach die Geometrie-Metadaten wieder her, aber nicht den R-tree. Übrig
bleibt `spatial_index_enabled=0` mit einer leeren, nicht gepflegten
R-tree-Tabelle - der Raumindex fehlt, obwohl `GeometryField.spatial_index` auf
True steht und `makemigrations` deswegen nichts anzeigt.

Der Punkt läuft nach allen anderen dieser App, damit er das Endergebnis der
Migrationskette sieht. Für PostGIS ist er ein Sicherheitsnetz: Dort legt Django
beim Anlegen der Tabelle einen GiST-Index an und behält ihn bei AlterField;
angelegt wird nur, wenn der Index etwa nach einer Wiederherstellung aus einer
Dump-Datei fehlt.

Hintergrund, Messwerte und die Warnung vor einem halb angelegten Index:
xplanung_light/helper/spatial_index.py
"""

from django.db import migrations


def repariere_indizes(apps, schema_editor):
    """
    Laeuft die Reparatur aus dem Helper, nicht als SQL hier.

    Der Code liegt bewusst im Helper-Modul: Spatialite muss vor dem Anlegen
    aufräumen (überstehende R-tree-Tabellen und Auslöser entfernen) und danach
    Markierung, Füllung und Auslöser nachprüfen. Ein nur als aktiv markierter,
    aber leerer Index wäre schlimmer als kein Index - MapServer zeichnet dann
    leere Karten, ohne dass ein Fehler fällt.
    """
    from xplanung_light.helper.spatial_index import repariere_spatiale_indizes
    repariere_spatiale_indizes(using=schema_editor.connection.alias)


def keine_rueckwaendreparatur(apps, schema_editor):
    """
    Rückwärts wird nichts zurückgenommen.

    Ein angelegter Index stört nicht; ihn im Zuge einer Zurücknahme wieder zu
    entfernen wäre der größere Schaden.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("xplanung_light", "0092_alter_bplanspezexternereferenz_attachment_and_more"),
    ]

    operations = [
        migrations.RunPython(repariere_indizes, keine_rueckwaendreparatur),
    ]
