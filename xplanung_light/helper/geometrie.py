"""
Werkzeuge für Geometrien auf dem Weg in die Ablage.

Die Geometriefelder der Modelle sind zweidimensional angelegt (Django schreibt
für `GeometryField` eine Spalte `MULTIPOLYGON,4326` ohne Tiefenachse). XPlanung-
GML darf aber Höhen mitführen - `posList srsDimension="3"` kommt in echten
Datensätzen vor, und einige Exportwerkzeuge schreiben die Höhen grundsätzlich
mit. Auf Spatialite läuft so eine Geometrie kommentarlos durch (die Ablage
behält `ST_NDims` = 3, Django liest sie zweidimensional), auf PostGIS wirft
dagegen schon das Speichern `DataError: Geometry has Z dimension but column
does not`. Dieselbe Datei ist also auf dem einen System brauchbar und auf dem
anderen unbrauchbar - darum wird vor der Ablage überall dieselbe Normalisierung
angewandt.
"""

import re

from django.contrib.gis.geos import GEOSGeometry

# Tiefenachse in einer WKT-Angabe: "MULTIPOLYGON Z (((...", "LINESTRING Z M (..."
# Das Muster greift nur in Textangaben; hex-WKB wird hier nicht erkannt (siehe
# ohne_tiefenachse).
WKT_MIT_ACHSE = re.compile(r"\b[ZM]{1,2}\s*\(")

# Die zwei Fassungen desselben Werkzeugs, nachgemessen am 13.11.2026:
#  - Django 4.2 (Debian 11/12, requirements.txt) kennt OGRGeometry.set_3d noch
#    nicht; dort ist der coord_dim-Setter der einzige Weg.
#  - Django 5.2 (Debian 13, requirements_deb13.txt) gibt beim coord_dim-Setter
#    "RemovedInDjango60Warning: coord_dim setter is deprecated. Use set_3d()"
#    - also erst set_3d versuchen, dann ausweichen.
# Ein Weg allein taugt für beide unterstützten Stände nicht.


def _streiche_tiefenachse(ogr_geometrie):
    """Tiefenachse an einer OGR-Geometrie abschalten, je nach Django-Fassung."""
    if hasattr(ogr_geometrie, "set_3d"):
        ogr_geometrie.set_3d(False)
    else:
        ogr_geometrie.coord_dim = 2
    return ogr_geometrie


def ohne_tiefenachse(geometrie):
    """
    Geometrie ohne Tiefenachse zurückgeben; ohne Achse unverändert durchlassen.

    Was wird geprüft bzw. bewirkt: eine Geometrie mit Höhenangabe wird auf ihre
    zweidimensionale Form reduziert, alles andere bleibt unangetastet.

    Warum das nötig ist: die Ablagespalten sind zweidimensional, und PostGIS
    lehnt eine Geometrie mit Tiefenachse beim Speichern ab (Spatialite nicht).
    Weil `transform()` die Höhen mitnimmt, stammt die Achse aus dem GML.

    Die Prüfung läuft über `hasz` und gerade nicht über `dims` oder
    `coord_dim`: für eine aus dem GML mit `srsDimension="3"` gebaute Geometrie
    meldet `dims` nachgemessen **2**, obwohl `hasz` True ist und der Typname im
    WKT die Achse führt (`POLYGON Z ((...`, `MULTIPOLYGON Z (((...`). Der in
    `import_plan` auskommentierte Versuch `if geometry.dims == 3:` hätte genau
    solche Fälle übersehen.

    Textangaben werden mitgenommen, weil das Feld auch mit einer WKT-Zuweisung
    beschrieben werden kann (`plan.geltungsbereich = "SRID=4326;MULTIPOLYGON Z
    (((..."`). Ausgewertet wird Text nur, wenn er eine Achse Ankündigung trägt;
    ist er unlesbar, gibt er unverändert zurück, damit die Meldung des Feldes
    selbst kommt und nicht eine aus diesem Helfer. Hex-WKB-Text wird nicht
    erkannt - der Weg ist hier nicht vorgesehen.
    """
    if geometrie is None:
        return geometrie

    if isinstance(geometrie, str):
        if not WKT_MIT_ACHSE.search(geometrie):
            return geometrie
        try:
            geometrie = GEOSGeometry(geometrie)
        except Exception:
            return geometrie
    elif not hasattr(geometrie, "hasz"):
        # Kein Geometrieobjekt (Fremdes, Bytes) - hier nicht zuständig.
        return geometrie

    if not geometrie.hasz:
        return geometrie

    srid = getattr(geometrie, "srid", None)
    ogr_geometrie = geometrie.ogr
    geometrie_2d = GEOSGeometry(_streiche_tiefenachse(ogr_geometrie).wkb)
    geometrie_2d.srid = srid
    return geometrie_2d
