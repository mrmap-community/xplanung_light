"""
Prüft die Normalisierung von Geometrien ohne Tiefenachse (helper/geometrie.py).

Was wird geprüft: die Wege, auf denen eine Geometrie mit Höhen in die Ablage
kommen kann - der Helfer selbst, beide GML-Importe (einzeln und als ZIP-Archiv)
und das Speichern am Modell.

Warum: die Geometriefelder sind zweidimensional angelegt, XPlanung-GML darf
aber Höhen mitführen (`gml:posList srsDimension="3"`). Auf Spatialite nimmt die
Bank so eine Geometrie kommentarlos an, auf PostGIS wirft schon das Speichern
`DataError: Geometry has Z dimension but column does not`. Dieselbe Datei ist
auf dem einen System brauchbar, auf dem anderen unbrauchbar. Der Einzel-Import
strichelte die Höhen bisher, der Archiv-Import und die Kommandos nicht.

Erwartung: in der Datenbank stecken zwei Achsen; X/Y-Werte, Fläche und Umriss
bleiben unverändert.

Geprüft wird die Dimension in der Bank (`ST_NDims`) und gerade nicht `hasz` am
eingelesenen Objekt: Spatialite legt eine Z-Geometrie stillschweigend ab und
Django liest sie zweidimensional zurück - am Objekt wäre der Fehler auf dieser
Bank unsichtbar geblieben.
"""

import warnings

from django.contrib.gis.gdal import OGRGeometry
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.test import SimpleTestCase, TestCase
from unittest.mock import patch

import xplanung_light.helper.xplanung as xplanung_helper
from xplanung_light.helper.geometrie import _streiche_tiefenachse, ohne_tiefenachse
from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import AdministrativeOrganization, BPlan, FPlan
from xplanung_light.tests.test_xplanung_helper_import import (
    AGS,
    GEMEINDE_NAME,
    GEOMETRIE,
    gml_upload,
    make_gml,
    magic_wiehrt_dateityp,
    zip_upload,
)

# Dieselbe Fläche wie GEOMETRIE, nur mit Höhenangabe (dritte Zahl je
# Koordinatenpaar) - die Datensatzform, wie sie Exportwerkzeuge mit
# höhenführenden posList ausliefern.
GEOMETRIE_MIT_HOEHE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
  <gml:exterior>
    <gml:LinearRing>
      <gml:posList srsDimension="3">
        430000.000 5470000.000 45.5
        430200.000 5470000.000 46.0
        430200.000 5470200.000 46.2
        430000.000 5470200.000 45.8
        430000.000 5470000.000 45.5
      </gml:posList>
    </gml:LinearRing>
  </gml:exterior>
</gml:Polygon>"""


def geometrie_aus_gml_gelesen():
    """Geometrie aus dem GML mit srsDimension="3", so wie der Import sie erhält."""
    geometrie = GEOSGeometry.from_gml(GEOMETRIE_MIT_HOEHE)
    geometrie.srid = 25832
    return geometrie


def zweidimensionale_referenz():
    """
    Vergleichsgeometrie: dieselbe Fläche aus der zweidimensionalen Vorlage, auf
    demselben Weg (25832 -> 4326) transformiert wie im Import.
    """
    geometrie = GEOSGeometry.from_gml(GEOMETRIE)
    geometrie.srid = 25832
    geometrie.transform(4326)
    return geometrie


def punktpaare(geometrie):
    """Alle X/Y-Paare einer Geometrie, Polygon und MultiPolygon gleich behandelt."""
    flaechen = [geometrie] if geometrie.geom_type == "Polygon" else geometrie
    return [tuple(p[:2]) for flaeche in flaechen for ring in flaeche for p in ring]


def tiefe_in_der_ablage(plan):
    """
    Zahl der Achsen, wie sie in der Datenbankspalte liegen (vendor-unabhängig).

    ST_NDims gibt es in Spatialite und PostGIS; ST_CoordDim fehlt Spatialite
    (nachgemessen). Am eingelesenen Objekt zu prüfen reicht nicht, weil
    Spatialite eine Z-Geometrie abnimmt und Django sie zweidimensional zurückgibt.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT ST_NDims("geltungsbereich") FROM "%s" WHERE id = %%s'
            % plan._meta.db_table,
            [plan.pk],
        )
        return cursor.fetchone()[0]


class OgrOhneSet3d:
    """
    Nachbau einer OGR-Geometrie ohne `set_3d` - die Lage unter Django 4.2
    (Debian 11/12), wo es die Methode noch nicht gibt. Reicht `wkb` und
    `coord_dim` durch, damit der Ausweichzweig mit echten WKB-Daten geprüft ist.
    """

    def __init__(self, ogr_geometrie):
        self._ogr_geometrie = ogr_geometrie

    @property
    def wkb(self):
        return self._ogr_geometrie.wkb

    @property
    def coord_dim(self):
        return self._ogr_geometrie.coord_dim

    @coord_dim.setter
    def coord_dim(self, wert):
        self._ogr_geometrie.coord_dim = wert


class OhneTiefenachseTests(SimpleTestCase):
    """Der Helfer für sich: Achse entfernen, dims-Täuschung, Auswege."""

    def test_pruefung_laeuft_ueber_hasz_dims_taeuscht_zweidimensional(self):
        """
        Was wird geprüft:
            Welche Eigenschaft einer aus dem GML mit srsDimension="3" gebauten
            Geometrie eine Tiefenachse meldet.

        Warum:
            Der auskommentierte Versuch in import_plan fragte `geometry.dims == 3`
            und hätte echte Höhendaten übersehen. Zu prüfen ist über `hasz`; die
            Falle ist hier festgehalten, damit niemand auf dims zurückfällt.

        Erwartung:
            dims meldet 2, obwohl hasz True ist und der Typname im WKT die Achse
            führt ("POLYGON Z ((..."); ohne_tiefenachse reduziert trotzdem.
        """
        geometrie = geometrie_aus_gml_gelesen()
        self.assertTrue(geometrie.hasz)
        self.assertIn("POLYGON Z", geometrie.wkt)
        self.assertEqual(geometrie.dims, 2)  # die Täuschung

        self.assertFalse(ohne_tiefenachse(geometrie).hasz)

    def test_tiefenachse_faellt_x_y_flaeche_und_umriss_bleiben(self):
        """
        Was wird geprüft:
            Übergabe einer Geometrie mit Höhen an ohne_tiefenachse.

        Warum:
            Das Abschalten der Achse darf die Ebene nicht verändern - sonst
            würden Pläne bei jedem Import verschoben oder verkleinert.

        Erwartung:
            hasz False, Typ und SRID erhalten; alle X/Y-Punktpaare, Fläche und
            Umriss identisch zur Ausgangsgeometrie.
        """
        geometrie = geometrie_aus_gml_gelesen()
        flach = ohne_tiefenachse(geometrie)

        self.assertFalse(flach.hasz)
        self.assertEqual(flach.geom_type, geometrie.geom_type)
        self.assertEqual(flach.srid, geometrie.srid)
        vorher = punktpaare(geometrie)
        nachher = punktpaare(flach)
        self.assertEqual(len(vorher), len(nachher))
        self.assertEqual(vorher, nachher)
        self.assertAlmostEqual(flach.area, geometrie.area, places=12)
        self.assertEqual(tuple(flach.extent), tuple(geometrie.extent))

    def test_zweidimensionale_geometrie_bleibt_dasselbe_objekt(self):
        """
        Was wird geprüft:
            Eine Geometrie ohne Tiefenachse durch ohne_tiefenachse.

        Warum:
            Der Regelfall ist zweidimensional; jede Umwandlung wäre unnötige
            Arbeit und ein Risiko für die Zahlendarstellung.

        Erwartung:
            Dasselbe Objekt, unverändert durchgereicht.
        """
        zweid = GEOSGeometry("POLYGON ((9.5 53.5, 9.51 53.5, 9.51 53.51, 9.5 53.5))")
        zweid.srid = 4326
        self.assertIs(ohne_tiefenachse(zweid), zweid)

    def test_textzuweisung_wird_nur_bei_tiefenachse_zum_objekt(self):
        """
        Was wird geprüft:
            Zuweisungen als Text, wie das Feld sie auch annimmt - mit und ohne
            Höhenangabe ("SRID=4326;MULTIPOLYGON Z (((...").

        Warum:
            Der Modell-Hook sieht sowohl Geometrieobjekte als auch Texte. Eine
            zweidimensionale Textangabe darf in der Darstellung nicht verändert
            werden, und ein unlesbarer Text muss die Meldung des Feldes selbst
            behalten statt einer aus diesem Helfer.

        Erwartung:
            Text mit Z wird zur zweidimensionalen Geometrie (SRID bleibt), Text
            ohne Z und unlesbarer Text bleiben dasselbe Objekt.
        """
        ergebnis = ohne_tiefenachse("SRID=4326;MULTIPOLYGON Z (((0 0 5, 4 0 6, 4 4 7, 0 0 5)))")
        self.assertIsInstance(ergebnis, GEOSGeometry)
        self.assertFalse(ergebnis.hasz)
        self.assertEqual(ergebnis.srid, 4326)
        self.assertEqual(ergebnis.wkt, "MULTIPOLYGON (((0 0, 4 0, 4 4, 0 0)))")

        ohne_achse = "SRID=4326;POLYGON ((7 50, 7.01 50, 7.01 50.01, 7 50))"
        self.assertIs(ohne_tiefenachse(ohne_achse), ohne_achse)

        unlesbar = "MULTIPOLYGON Z (((keine zahlen"
        self.assertIs(ohne_tiefenachse(unlesbar), unlesbar)

    def test_leerwerte_und_fremde_objekte_bleiben_unveraendert(self):
        """
        Was wird geprüft:
            None und ein Nicht-Geometrieobjekt durch ohne_tiefenachse.

        Warum:
            Das Feld ist nicht überall gesetzt und der Helfer läuft an
            Modellstellen, die auch anderes zu sehen bekommen können; dort soll
            er nichts zerstören.

        Erwartung:
            Beide unverändert zurück.
        """
        self.assertIsNone(ohne_tiefenachse(None))
        fremd = object()
        self.assertIs(ohne_tiefenachse(fremd), fremd)

    def test_ausweich_ueber_coord_dim_ohne_set_3d(self):
        """
        Was wird geprüft:
            _streiche_tiefenachse mit einer OGR-Geometrie, die set_3d nicht kennt.

        Warum:
            set_3d gibt es erst in neueren Django-Fassungen; das Projekt
            unterstützt auch Django 4.2 (Debian 11/12), wo coord_dim der einzige
            Weg ist - und umgekehrt meldet Django 5.2 beim coord_dim-Setter
            "RemovedInDjango60Warning ... Use set_3d()". Auf dem hiesigen Stand
            wäre der Ausweichzweig sonst nie geprüft.

        Erwartung:
            Ohne set_3d wird coord_dim gesetzt; das Ergebnis ist zweidimensional.
        """
        getarnt = OgrOhneSet3d(OGRGeometry(geometrie_aus_gml_gelesen().wkt))
        self.assertFalse(hasattr(getarnt, "set_3d"))
        self.assertTrue(hasattr(getarnt, "coord_dim"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # coord_dim ist ab 5.2 abgekündigt
            flach = GEOSGeometry(_streiche_tiefenachse(getarnt).wkb)
        self.assertFalse(flach.hasz)


class ModellAblageOhneTiefenachseTests(TestCase):
    """Der Modell-Hook: Ablage zweidimensional, gültige Pläne bleiben heil."""

    def test_geometrie_mit_tiefenachse_wird_zweidimensional_abgelegt(self):
        """
        Was wird geprüft:
            Anlegen eines BPlans mit einer Geometrie, die Höhen mitführt.

        Warum:
            Nicht jeder Weg über die GML-Importe normalisiert vorher - Formulare
            und die Kommandos importplans/importoffenlagen schreiben direkt; auf
            PostGIS fällt eine Z-Geometrie dort erst beim Speichern auf.

        Erwartung:
            In der Spalte liegen zwei Achsen, der Umriss bleibt gleich.
        """
        plan = BPlan.objects.create(
            name="Plan mit Höhen", public=False,
            geltungsbereich=GEOSGeometry(
                "SRID=4326;POLYGON Z ((9.5 53.5 45.5, 9.51 53.5 46, "
                "9.51 53.51 46.2, 9.5 53.5 45.5))"))
        self.assertEqual(tiefe_in_der_ablage(plan), 2)
        plan.refresh_from_db()
        self.assertFalse(plan.geltungsbereich.hasz)
        self.assertEqual(tuple(round(w, 9) for w in plan.geltungsbereich.extent),
                         (9.5, 53.5, 9.51, 53.51))

    def test_textzuweisung_mit_tiefenachse_wird_zweidimensional_abgelegt(self):
        """
        Was wird geprüft:
            Nachtragen des Geltungsbereichs als WKT-Text mit Höhen und Speichern.

        Warum:
            Das Feld nimmt auch Texte an; der Hook muss dort genauso greifen.

        Erwartung:
            Zwei Achsen in der Spalte, keine Höhen mehr im eingelesenen Objekt.
        """
        plan = BPlan.objects.create(
            name="Plan mit Textgeometrie", public=False,
            geltungsbereich="SRID=4326;POLYGON ((9.5 53.5, 9.51 53.5, "
                            "9.51 53.51, 9.5 53.5))")
        plan.geltungsbereich = (
            "SRID=4326;POLYGON Z ((9.5 53.5 1, 9.51 53.5 2, 9.51 53.51 3, 9.5 53.5 1))")
        plan.save()
        self.assertEqual(tiefe_in_der_ablage(plan), 2)
        plan.refresh_from_db()
        self.assertFalse(plan.geltungsbereich.hasz)

    def test_zweidimensionaler_plan_bleibt_beim_erneuten_speichern_heil(self):
        """
        Was wird geprüft:
            Wiederholtes Speichern eines normalen, zweidimensionalen Plans.

        Warum:
            Der Hook läuft jetzt bei jedem save(); er darf bestehende Pläne
            nicht verschieben, verkleinern oder in der Zahlendarstellung
            verändern.

        Erwartung:
            Fläche und Umriss unverändert, weiterhin zwei Achsen in der Spalte.
        """
        plan = BPlan.objects.create(
            name="Richtiger Plan", public=False,
            geltungsbereich="SRID=4326;POLYGON ((9.5 53.5, 9.51 53.5, "
                            "9.51 53.51, 9.5 53.5))")
        vorher = BPlan.objects.get(pk=plan.pk)
        plan.beschreibung = "nachgetragen"
        plan.save()
        nachher = BPlan.objects.get(pk=plan.pk)

        self.assertEqual(tiefe_in_der_ablage(nachher), 2)
        self.assertAlmostEqual(vorher.geltungsbereich.area,
                               nachher.geltungsbereich.area, places=12)
        self.assertEqual(tuple(vorher.geltungsbereich.extent),
                         tuple(nachher.geltungsbereich.extent))
        self.assertEqual(nachher.beschreibung, "nachgetragen")


class GmlImportOhneTiefenachseTests(TestCase):
    """Beide GML-Importe mit Höhendaten - der Archivweg war die Lücke."""

    def setUp(self):
        AdministrativeOrganization.objects.create(
            name=GEMEINDE_NAME, ls=AGS[:2], ks=AGS[2:5], gs=AGS[5:8])

    def test_einzel_gml_import_streicht_die_tiefenachse(self):
        """
        Was wird geprüft:
            Import einer einzelnen GML-Datei mit posList srsDimension="3".

        Warum:
            Der Einzel-Import strichelte die Höhen über OGR; die Prüfung hält das
            Verhalten nach dem Umbau auf den gemeinsamen Helfer fest.

        Erwartung:
            Plan vorhanden, zwei Achsen in der Spalte, Umriss und Fläche wie beim
            zweidimensionalen Vergleich.
        """
        self.assertTrue(XPlanung(gml_upload(make_gml(
            name="Einzelplan mit Höhen",
            geometrie=GEOMETRIE_MIT_HOEHE))).import_plan())
        plan = BPlan.objects.get(name="Einzelplan mit Höhen")

        self.assertEqual(tiefe_in_der_ablage(plan), 2)
        referenz = zweidimensionale_referenz()
        self.assertEqual(tuple(round(w, 8) for w in plan.geltungsbereich.extent),
                         tuple(round(w, 8) for w in referenz.extent))
        self.assertAlmostEqual(plan.geltungsbereich.area, referenz.area, places=12)

    def test_archiv_import_streicht_die_tiefenachse(self):
        """
        Was wird geprüft:
            Import eines ZIP-Archivs mit einem höhenführenden GML (FP_Plan).

        Warum:
            import_plan_archiv hatte bisher keinen Strip - der häufigere
            Uploadweg ("Upload XPlan-Archiv" im Formular) gab die Geometrie
            unverändert an die Spalte weiter und scheitert auf PostGIS mit
            "Geometry has Z dimension but column does not", während Spatialite
            sie unbemerkt annimmt.

        Erwartung:
            Plan vorhanden und zweidimensional abgelegt, Umriss unverändert.
        """
        gml = make_gml(plan_element="FP_Plan", name="Archivplan mit Höhen",
                       geometrie=GEOMETRIE_MIT_HOEHE)
        with patch.object(xplanung_helper.magic, "from_buffer",
                          side_effect=magic_wiehrt_dateityp):
            self.assertTrue(XPlanung(zip_upload(gml)).import_plan_archiv(plan_typ="fplan"))
        plan = FPlan.objects.get(name="Archivplan mit Höhen")

        self.assertEqual(tiefe_in_der_ablage(plan), 2)
        plan.refresh_from_db()
        self.assertFalse(plan.geltungsbereich.hasz)
        referenz = zweidimensionale_referenz()
        self.assertEqual(tuple(round(w, 8) for w in plan.geltungsbereich.extent),
                         tuple(round(w, 8) for w in referenz.extent))
