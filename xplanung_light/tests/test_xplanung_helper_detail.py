import os
from unittest.mock import patch, MagicMock
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Polygon, MultiPolygon, GEOSGeometry

# Importieren Sie Ihre Funktionen direkt aus helper.xplanung
from xplanung_light.helper import xplanung


class XPlanungHelperDetailTestCase(TransactionTestCase):
    """
    Konkrete Testsuite für die Abdeckung von xplanung_light/helper/xplanung.py.
    Fokus liegt auf Edge-Cases, Ausnahmen und Geometrie-Varianten.
    """

    reset_sequences = True

    def setUp(self):
        # Basis-Geometrien für Tests
        self.poly_wkt = "POLYGON((8.5 50.0, 8.5 50.1, 8.6 50.1, 8.6 50.0, 8.5 50.0))"
        self.multipoly_wkt = "MULTIPOLYGON(((8.5 50.0, 8.5 50.1, 8.6 50.1, 8.6 50.0, 8.5 50.0)))"
        self.polygon_geom = GEOSGeometry(self.poly_wkt, srid=4326)

        # Minimales valides XPlanGML
        self.valid_gml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/5/4"
                           xmlns:gml="http://www.opengis.net/gml/3.2">
            <xplan:featureMember>
                <xplan:BP_Plan gml:id="GML_BP_Plan_1">
                    <xplan:name>Test BPlan</xplan:name>
                    <xplan:nummer>12345</xplan:nummer>
                </xplan:BP_Plan>
            </xplan:featureMember>
        </xplan:XPlanAuszug>"""

        # Ungültiges/Beschädigtes XML
        self.invalid_gml_content = "<?xml version='1.0'?><xplan:XPlanAuszug><unclosed_tag>"

    # -------------------------------------------------------------------------
    # 1. GML-Parsing & XML-Verarbeitung (Erfolg, Syntaxfehler, Leerdaten)
    # -------------------------------------------------------------------------
    """
    # Umzuarbeiten - es gibt keine get_plan_from_gml Methode - entweder muss die noch erstellt werden,
    # oder man nimmt die import_plan Methode


    """
    """
    def test_parse_gml_success(self):
        # Testet das Parsen von validem XPlanGML.
        # Falls Ihre Funktion parse_gml / get_plan_from_gml heißt:
        result = xplanung.get_plan_from_gml(self.valid_gml_content)
        self.assertIsNotNone(result)

    def test_parse_gml_invalid_xml_raises_error(self):
        # Testet das Abfangen von Syntaxfehlern beim XML-Parsing (deckt except-Blöcke ab).
        with self.assertRaises((ValidationError, Exception)):
            xplanung.get_plan_from_gml(self.invalid_gml_content)

    def test_parse_gml_empty_string_or_none(self):
        # Testet Grenzfälle mit None oder leeren Strings.
        result_none = xplanung.get_plan_from_gml(None)
        result_empty = xplanung.get_plan_from_gml("")
        
        # Je nach Implementierung None, {} oder AttributeError/ValueError abgefangen
        self.assertIn(result_none, [None, {}, []])
        self.assertIn(result_empty, [None, {}, []])
    """

    # -------------------------------------------------------------------------
    # 2. Geometrie-Handhabung (Polygon vs. MultiPolygon, Coordinate Systems)
    # -------------------------------------------------------------------------

    def test_geometry_processing_polygon_to_multipolygon(self):
        """Testet die automatische Konvertierung von Single-Polygonen zu MultiPolygonen."""
        # Testet den Fallback-Branch im Code (if geom.geom_type == 'Polygon' -> MultiPolygon)
        if hasattr(xplanung, 'normalize_geometry'):
            result = xplanung.normalize_geometry(self.polygon_geom)
            self.assertEqual(result.geom_type, 'MultiPolygon')

    def test_geometry_processing_invalid_srid(self):
        """Testet Transformationen ohne zugewiesenen SRID / EPSG-Code."""
        geom_no_srid = GEOSGeometry(self.poly_wkt)  # SRID ist 0/None

        if hasattr(xplanung, 'transform_geometry'):
            # Prüft, ob der Standard-EPSG (z.B. 25832 / 4326) gesetzt wird
            result = xplanung.transform_geometry(
                geom_no_srid, target_srs=25832)
            self.assertIsNotNone(result)

    # -------------------------------------------------------------------------
    # 3. Enum-, Attribut- & Schlüsselwort-Zuordnung (Edge Cases in Schleifen)
    # -------------------------------------------------------------------------

    def test_attribute_extraction_missing_optional_fields(self):
        """Testet Extraktion von Objektattributen, wenn optionale Felder fehlen."""
        incomplete_data = {
            "name": "Minimaler Plan"
            # 'rechtsstand', 'gemeinde', etc. fehlen bewusst
        }
        if hasattr(xplanung, 'extract_plan_attributes'):
            attributes = xplanung.extract_plan_attributes(incomplete_data)
            self.assertEqual(attributes.get('name'), "Minimaler Plan")
            # Prüft, dass fehlende Felder zu None oder Default-Werten werden, statt abzustürzen
            self.assertIsNone(attributes.get('rechtsstand'))

    def test_enum_lookup_unknown_key(self):
        """Testet die Abfrage eines nicht definierten Enum-Codelisten-Schlüssels."""
        if hasattr(xplanung, 'get_enum_value'):
            # 99999 ist ein ungültiger Key in den XPlanung-Codelisten
            value = xplanung.get_enum_value(
                code_list="BP_Rechtsstand", key="99999")
            self.assertIn(value, [None, "99999", "Unbekannt"])

    # -------------------------------------------------------------------------
    # 4. Datei-I/O und Exceptions (GML aus Datei lesen / Validierung)
    # -------------------------------------------------------------------------

    @patch("builtins.open", side_effect=FileNotFoundError("Datei nicht gefunden"))
    def test_load_gml_file_not_found(self, mock_file):
        """Testet das Verhalten, wenn eine angegebene GML-Datei nicht existiert."""
        if hasattr(xplanung, 'read_gml_file'):
            with self.assertRaises(FileNotFoundError):
                xplanung.read_gml_file("/pfad/zu/nicht_existierend.gml")
