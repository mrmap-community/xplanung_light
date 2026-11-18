"""Legt die räumlichen Indizes der Geometrie-Spalten an, wo sie fehlen.

Die erste Migration dieser App legt die Tabellen an; welche räumlichen Indizes dabei
entstehen, hängt vom Triebwerk und von der Spalte ab. Auf Spatialite bleibt die
Geometriespalte der Gebietskörperschaft ohne R-tree, obwohl das Modell
`spatial_index=True` sagt — `makemigrations` zeigt das nie an, weil der Punkt keinen
Feldwechsel beschreibt (gemessen 18.11.2026 mit Django 5.2 auf einer frischen Bank:
`spatial_index_enabled=0` für `xplanung_light_administrativeorganization.geometry`,
während `geltungsbereich` bei BPlan und FPlan korrekt indiziert war).

Der Punkt läuft deshalb nach der ersten Migration und gleicht aus, was fehlt. Er ist
keine Altdatenkorrektur, sondern Teil des Aufbaus: Er gehört auch nach jeder
Wiederherstellung aus einer Dump-Datei, die Geometriespalten ohne Typvorgabe
hinterlassen kann.

Warum der Code im Helper liegt und nicht als SQL hier: Spatialite muss vor dem Anlegen
aufräumen (überstehende R-tree-Tabellen und Auslöser entfernen) und danach Markierung,
Füllung und Auslöser nachprüfen. Ein nur als aktiv markierter, aber leerer Index ist
schlimmer als kein Index — MapServer zeichnet dann leere Karten, ohne dass ein Fehler
fällt.

Hintergrund und Messwerte: xplanung_light/helper/spatial_index.py
"""

from django.db import migrations


def setze_spatiale_indizes(apps, schema_editor):
    """
    Laeuft die Helper-Funktion, nicht eine SQL-Abschrift hier.

    Der Helper prüft pro Spalte den tatsächlichen Zustand (bei Spatialite die
    Markierung in geometry_columns, bei PostGIS die Katalogtabellen) und legt nur an,
    was fehlt. Für PostGIS ist der Punkt damit ein Sicherheitsnetz ohne Wirkung, wenn
    alles stimmt.
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
        ("xplanung_light", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(setze_spatiale_indizes, keine_rueckwaendreparatur),
    ]
