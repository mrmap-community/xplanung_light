import contextlib
import io

from django.test import RequestFactory, SimpleTestCase

from xplanung_light.views.xplan import XPlanListView, XPlanPublicListView, qualify_gml_geometry

POLYGON = ('<gml:Polygon srsName="EPSG:25832"><gml:exterior><gml:LinearRing>'
           '<gml:posList>0 0 0 1 1 1 1 0 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>')
MULTI = ('<gml:MultiSurface srsName="EPSG:25832">'
         f'<gml:surfaceMember>{POLYGON}</gml:surfaceMember><gml:surfaceMember>{POLYGON}</gml:surfaceMember>'
         '</gml:MultiSurface>')


# Testklasse: QualifyGmlGeometryTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class QualifyGmlGeometryTests(SimpleTestCase):

    # Testfall: single Polygon ist wrapped in MultiSurface.
    # Erwartung/Absicherung: verwendet assertTrue, assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_single_polygon_is_wrapped_in_multisurface(self):
        with contextlib.redirect_stdout(io.StringIO()):          # die Funktion ruft ET.dump() auf
            result = qualify_gml_geometry(POLYGON)
        self.assertTrue(result.startswith('<gml:MultiSurface srsName="EPSG:25832"><gml:surfaceMember>'))
        self.assertEqual(result.count('gml:id="GML_'), 1)

    # Testfall: MultiSurface gets ids on surface and polygons.
    # Erwartung/Absicherung: verwendet assertTrue, assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_multisurface_gets_ids_on_surface_and_polygons(self):
        result = qualify_gml_geometry(MULTI)
        self.assertTrue(result.lstrip().startswith("<gml:MultiSurface"))
        self.assertEqual(result.count('gml:id="GML_'), 3)         # MultiSurface + 2 Polygone


# Testklasse: TablePaginationTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class TablePaginationTests(SimpleTestCase):

    # Testfall: per page parsing.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_per_page_parsing(self):
        for view_cls in (XPlanListView, XPlanPublicListView):
            for query, expected in (({}, 10), ({"per_page": "25"}, 25), ({"per_page": "abc"}, 10)):
                with self.subTest(view=view_cls.__name__, query=query):
                    view = view_cls()
                    view.request = RequestFactory().get("/", query)
                    self.assertEqual(view.get_table_pagination(None), {"per_page": expected})
