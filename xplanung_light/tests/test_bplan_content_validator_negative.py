from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from xplanung_light.validators import bplan_content_validator


XPLAN_NS = 'http://www.xplanung.de/xplangml/6/0'
GML_NS = 'http://www.opengis.net/gml/3.2'

# Passend zur Fixture-Organisation (ls=07, ks=316, gs=000)
GUELTIGE_AGS = '07316000'
GUELTIGER_GEMEINDE_NAME = 'Neustadt an der Weinstraße, kreisfreie Stadt'

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>"""


def build_gml(namespace=XPLAN_NS,
              root_tag='XPlanAuszug',
              include_name=True,
              include_planart=True,
              include_geltungsbereich=True,
              gemeinden=(( GUELTIGE_AGS, GUELTIGER_GEMEINDE_NAME),)):
    """
    Baut ein minimales XPlan-GML mit gezielt weglassbaren/verfälschbaren
    Bestandteilen, um die einzelnen Prüfpfade in bplan_content_validator()
    getrennt auslösen zu können.

    gemeinden: Liste von (ags, gemeindeName)-Tupeln. Leere Liste = kein
    xplan:gemeinde-Block im GML.
    """
    name_element = '<xplan:name>Testplan</xplan:name>' if include_name else ''
    planart_element = '<xplan:planArt>1000</xplan:planArt>' if include_planart else ''
    geltungsbereich_element = (
        '<xplan:raeumlicherGeltungsbereich>%s</xplan:raeumlicherGeltungsbereich>' % GEOMETRIE
        if include_geltungsbereich else ''
    )
    gemeinde_blocks = ''.join(
        '<xplan:gemeinde><xplan:XP_Gemeinde>'
        '<xplan:ags>%s</xplan:ags><xplan:gemeindeName>%s</xplan:gemeindeName>'
        '</xplan:XP_Gemeinde></xplan:gemeinde>' % (ags, name)
        for ags, name in gemeinden
    )
    return (
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>'
        '<xplan:%s xmlns:xplan="%s" xmlns:gml="%s" '
        'xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<gml:featureMember><xplan:BP_Plan gml:id="GML_testplan">'
        '%s%s%s%s'
        '</xplan:BP_Plan></gml:featureMember>'
        '</xplan:%s>'
    ) % (root_tag, namespace, GML_NS, name_element, geltungsbereich_element,
         gemeinde_blocks, planart_element, root_tag)


def upload(xml_string, content_type='text/xml'):
    return SimpleUploadedFile(
        'testplan.gml', xml_string.encode('utf-8'), content_type=content_type,
    )


class BPlanContentValidatorNegativ(TestCase):
    """
    Negativtests für bplan_content_validator() - jeder Test löst genau einen
    Prüfpfad aus und prüft die konkrete Fehlermeldung, nicht nur, dass
    überhaupt ein ValidationError kommt.
    """

    fixtures = ['administrative_organization.json']

    def _get_messages(self, xml_string, content_type='text/xml'):
        with self.assertRaises(forms.ValidationError) as ctx:
            bplan_content_validator(upload(xml_string, content_type))
        return ctx.exception.messages

    # --- Vorprüfungen (vor dem XML-Parsing) --------------------------------

    def test_falscher_content_type_wird_abgelehnt(self):
        # Vorprüfung noch vor dem XML-Parsing: falscher Content-Type -> sofortige Ablehnung.
        messages = self._get_messages(
            build_gml(), content_type='application/pdf',
        )
        self.assertEqual(messages, ["Es handelt sich nicht um eine GML-Datei!"])

    def test_ungueltige_utf8_bytes_werden_abgelehnt(self):
        # Kaputte Bytes statt gültigem UTF-8 -> eigener Decode-Fehlerpfad.
        upload_file = SimpleUploadedFile(
            'testplan.gml', b'\xff\xfe kaputte Bytes', content_type='text/xml',
        )
        with self.assertRaises(forms.ValidationError) as ctx:
            bplan_content_validator(upload_file)
        self.assertEqual(
            ctx.exception.messages,
            ["Das decodieren nach UTF-8 war nicht erfolgreich!"],
        )

    # --- Root-Element / Namespace ------------------------------------------

    def test_nicht_unterstuetzter_namespace_wird_abgelehnt(self):
        # Falscher xplan-Namespace (z.B. altes XPlan 4.0) muss abgelehnt werden.
        messages = self._get_messages(
            build_gml(namespace='http://www.xplanung.de/xplangml/4/0')
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('wird nicht unterstützt', messages[0])
        self.assertIn('XPlanAuszug', messages[0])

    def test_falsches_root_element_wird_abgelehnt(self):
        # Analog, aber mit falschem Element-Namen statt falschem Namespace.
        messages = self._get_messages(build_gml(root_tag='EtwasAnderes'))
        self.assertEqual(len(messages), 1)
        self.assertIn('wird nicht unterstützt', messages[0])

    # --- Pflichtfeld gemeinde (korrekt behandelter Fall) --------------------

    def test_fehlende_gemeinde_wird_mit_konkreter_meldung_abgelehnt(self):
        # Kein xplan:gemeinde-Block im GML -> spezifische Pflichtfeld-Meldung.
        messages = self._get_messages(build_gml(gemeinden=()))
        self.assertEqual(len(messages), 1)
        self.assertIn('gemeinde', messages[0])
        self.assertIn('keine Pflichtelemente', messages[0])

    def test_unbekannte_ags_wird_abgelehnt(self):
        # AGS-Format ok, aber keine passende AdministrativeOrganization in der DB.
        messages = self._get_messages(
            build_gml(gemeinden=(('99999999', 'Nicht existente Gemeinde'),))
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('99999999', messages[0])
        self.assertIn('Datenbank gefunden', messages[0])

    def test_gemeindename_stimmt_nicht_mit_datenbank_ueberein(self):
        # AGS existiert, aber der im GML angegebene Gemeindename passt nicht dazu.
        messages = self._get_messages(
            build_gml(gemeinden=((GUELTIGE_AGS, 'Falscher Gemeindename'),))
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('stimmt nicht mit dem name der Organisation', messages[0])

    # --- Geltungsbereich (korrekt behandelter Fall) -------------------------

    def test_fehlender_geltungsbereich_wird_mit_konkreter_meldung_abgelehnt(self):
        # Kein raeumlicherGeltungsbereich im GML -> eigene, klare Fehlermeldung.
        messages = self._get_messages(build_gml(include_geltungsbereich=False))
        self.assertEqual(messages, ["Geltungsbereich nicht gefunden!"])

    # --- Bekannte Schwäche der Fehlerbehandlung -----------------------------

    def test_fehlendes_pflichtfeld_name_liefert_nur_generische_fehlermeldung(self):
        """
        Dokumentiert eine bestehende Schwäche: root.find(...).text wirft bei
        fehlendem xplan:name ein AttributeError (find() liefert None), das vom
        äußeren pauschalen 'except:' aufgefangen wird. Statt der eigentlich
        vorgesehenen Meldung "Das Pflichtelement *xplan:name* wurde nicht
        gefunden!" kommt nur die generische Parse-Fehlermeldung an - und alle
        nachfolgenden Prüfungen (planArt, gemeinde, Geltungsbereich) werden
        gar nicht mehr ausgeführt.

        Falls die Fehlerbehandlung in bplan_content_validator() künftig
        verbessert wird (z.B. durch ein try/except je Feld), muss dieser Test
        entsprechend angepasst werden - er soll dann die spezifische Meldung
        erwarten statt der generischen.
        """
        messages = self._get_messages(build_gml(include_name=False))
        self.assertEqual(
            messages, ["XML-Dokument konnte nicht geparsed werden!"],
        )

    def test_fehlendes_pflichtfeld_planart_liefert_ebenfalls_nur_generische_meldung(self):
        """Gleiche Schwäche wie oben, für xplan:planArt."""
        messages = self._get_messages(build_gml(include_planart=False))
        self.assertEqual(
            messages, ["XML-Dokument konnte nicht geparsed werden!"],
        )

    # --- Positiv-Gegenprobe --------------------------------------------------

    def test_gueltiges_gml_wird_nicht_abgelehnt(self):
        """
        Kontrollprobe: das in allen anderen Tests als 'Basis' verwendete
        build_gml() ohne Modifikationen muss durch den Validator laufen -
        sonst wären die Negativtests wertlos, weil schon die Grundform
        fehlerhaft wäre.
        """
        try:
            bplan_content_validator(upload(build_gml()))
        except forms.ValidationError as error:
            self.fail(
                "Das als gültig gedachte Basis-GML wurde abgelehnt: "
                + "; ".join(error.messages)
            )