"""Repariert die räumlichen Indizes, die der vorherige Punkt still zerstört hat.

Hintergrund (gemessen 23.11.2026, Django 5.2, frische Spatialite-Bank):
`0003_alter_administrativeorganization_slug_and_more` ändert das `slug`-Feld der
Gebietskörperschaft und ihrer Historientabelle. Für ein AlterField baut SQLite die
Tabelle komplett neu — und dabei verliert die Geometriespalte ihren R-tree:
`spatial_index_enabled` steht danach auf 0, obwohl `spatial_index=True` am Feld
steht. `makemigrations` zeigt das nie an, weil der Punkt kein Geometriefeld
beschreibt. Nachteil im Betrieb: MapServer zeichnet leere Karten, ohne dass ein
Fehler fällt (derselbe Schaden wie in #34, nur durch eine neue Migration).

Der Reparaturpunkt `0002_spatiale_indizes` kann das nicht abfangen — er läuft vor
`0003` und sieht den Schaden noch nicht. Also gehört nach jeder Migration, die per
AlterField eine Tabelle mit Geometriespalte neu baut, ein eigener Reparaturschritt.
Die Suite erwischt ein Vergessen: `test_spatial_index.RaumindexNachMigrationslaufTests`
prüft auf der frisch migrierten Testbank, dass jede Geometriespalte einen lebenden
Index hat — ein fehlender Punkt macht die Suite rot.

Warum der Code wieder im Helper liegt und nicht als SQL hier: steht in
`0002_spatiale_indizes` — Spatialite muss vor dem Anlegen aufräumen und danach
Markierung, Füllung und Auslöser nachprüfen; ein nur markierter, leerer Index ist
schlimmer als kein Index. Für PostGIS ist der Punkt ein Sicherheitsnetz ohne
Wirkung, wenn alles stimmt.
"""

from django.db import migrations


def setze_spatiale_indizes(apps, schema_editor):
    """
    Läuft die Helper-Funktion, nicht eine SQL-Abschrift hier.

    Der Helper prüft pro Spalte den tatsächlichen Zustand und legt nur an, was
    fehlt — der Punkt ist damit beliebig oft wiederholbar (idempotent).
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
        ("xplanung_light", "0003_alter_administrativeorganization_slug_and_more"),
    ]

    operations = [
        migrations.RunPython(setze_spatiale_indizes, keine_rueckwaendreparatur),
    ]
