"""
Tests für Hilfsfunktionen in views/xplan.py: GML-Geometrie qualifizieren und Seitengröße der
Tabellen. Reine Logik ohne Datenbank.
"""

import contextlib
import io

from django.test import RequestFactory, SimpleTestCase

from xplanung_light.views.xplan import XPlanListView, XPlanPublicListView, qualify_gml_geometry

POLYGON = ('<gml:Polygon srsName="EPSG:25832"><gml:exterior><gml:LinearRing>'
           '<gml:posList>0 0 0 1 1 1 1 0 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>')
MULTI = ('<gml:MultiSurface srsName="EPSG:25832">'
         f'<gml:surfaceMember>{POLYGON}</gml:surfaceMember><gml:surfaceMember>{POLYGON}</gml:surfaceMember>'
         '</gml:MultiSurface>')


class QualifyGmlGeometryTests(SimpleTestCase):
    """
    Die Funktion qualify_gml_geometry macht aus einer GML-Geometrie ein MultiSurface mit gml:id
    an jedem Element (Pflicht für XPlanung-GML).
    """

    def test_single_polygon_is_wrapped_in_multisurface(self):
        """
        Was wird geprüft:
            Ein einzelnes Polygon wird in ein MultiSurface mit surfaceMember verpackt.

        Warum:
            XPlanung erwartet für den Geltungsbereich ein MultiSurface, auch bei einfachen
            Flächen.

        Erwartung:
            Das Ergebnis beginnt mit dem MultiSurface-Element, das Polygon trägt genau eine
            gml:id.

        Hinweis:
            Die Funktion ruft ET.dump() auf und schreibt dabei auf die Konsole; der Test
            fängt das ab.
        """
        with contextlib.redirect_stdout(io.StringIO()):          # die Funktion ruft ET.dump() auf
            result = qualify_gml_geometry(POLYGON)
        self.assertTrue(result.startswith('<gml:MultiSurface srsName="EPSG:25832"><gml:surfaceMember>'))
        self.assertEqual(result.count('gml:id="GML_'), 1)

    def test_multisurface_gets_ids_on_surface_and_polygons(self):
        """
        Was wird geprüft:
            Ein MultiSurface mit zwei Polygonen.

        Warum:
            Jedes Element braucht eine eigene eindeutige gml:id.

        Erwartung:
            Das Ergebnis bleibt ein MultiSurface und enthält drei gml:id (Fläche plus zwei
            Polygone).
        """
        result = qualify_gml_geometry(MULTI)
        self.assertTrue(result.lstrip().startswith("<gml:MultiSurface"))
        self.assertEqual(result.count('gml:id="GML_'), 3)         # MultiSurface + 2 Polygone


class TablePaginationTests(SimpleTestCase):
    """Auswertung des Parameters per_page für die Tabellen-Views."""

    def test_per_page_parsing(self):
        """
        Was wird geprüft:
            per_page fehlt, ist eine Zahl oder ist Text (beide Listen-Views).

        Warum:
            Ungültige Eingaben dürfen nicht zu einem Fehler führen.

        Erwartung:
            Standard 10; 25 wird übernommen; abc fällt auf 10 zurück.
        """
        for view_cls in (XPlanListView, XPlanPublicListView):
            for query, expected in (({}, 10), ({"per_page": "25"}, 25), ({"per_page": "abc"}, 10)):
                with self.subTest(view=view_cls.__name__, query=query):
                    view = view_cls()
                    view.request = RequestFactory().get("/", query)
                    self.assertEqual(view.get_table_pagination(None), {"per_page": expected})
