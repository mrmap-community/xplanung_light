"""
Negativtests für bplan_content_validator: Jeder Test löst genau einen Prüfpfad aus und prüft die
konkrete Fehlermeldung, nicht nur, dass überhaupt eine ValidationError kommt.
"""

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
    Baut ein XPlanung-GML aus Bausteinen. Namensraum, Wurzelelement und Pflichtangaben (Name,
    Planart, Geltungsbereich, Gemeinden als Liste aus AGS und Name) sind einstellbar, damit
    einzelne Fehlerfälle gezielt entstehen.
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
    """Verpackt den XML-Text als hochgeladene Datei mit dem angegebenen Inhaltstyp."""
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
        """
        Erwartet eine ValidationError beim Validieren des GML und liefert deren Meldungen
        zurück.
        """
        with self.assertRaises(forms.ValidationError) as ctx:
            bplan_content_validator(upload(xml_string, content_type))
        return ctx.exception.messages

    # --- Vorprüfungen (vor dem XML-Parsing) --------------------------------

    def test_falscher_content_type_wird_abgelehnt(self):
        """
        Was wird geprüft:
            Ein GML, das mit dem Inhaltstyp application/pdf hochgeladen wird.

        Warum:
            Nur XML-Dateien sind zugelassen.

        Erwartung:
            Genau die Meldung Es handelt sich nicht um eine GML-Datei!.
        """
        # Vorprüfung noch vor dem XML-Parsing: falscher Content-Type -> sofortige Ablehnung.
        messages = self._get_messages(
            build_gml(), content_type='application/pdf',
        )
        self.assertEqual(messages, ["Es handelt sich nicht um eine GML-Datei!"])

    def test_ungueltige_utf8_bytes_werden_abgelehnt(self):
        """
        Was wird geprüft:
            Dateiinhalt, der kein gültiges UTF-8 ist.

        Warum:
            Defekte Zeichenkodierung muss als lesbarer Fehler enden.

        Erwartung:
            Genau die Meldung Das decodieren nach UTF-8 war nicht erfolgreich!.
        """
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
        """
        Was wird geprüft:
            Ein GML mit XPlanung-Namensraum der Version 4.0.

        Warum:
            Es wird nur die unterstützte Version akzeptiert.

        Erwartung:
            Eine Meldung, die wird nicht unterstützt und XPlanAuszug enthält.
        """
        # Falscher xplan-Namespace (z.B. altes XPlan 4.0) muss abgelehnt werden.
        messages = self._get_messages(
            build_gml(namespace='http://www.xplanung.de/xplangml/4/0')
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('wird nicht unterstützt', messages[0])
        self.assertIn('XPlanAuszug', messages[0])

    def test_falsches_root_element_wird_abgelehnt(self):
        """
        Was wird geprüft:
            Ein GML mit anderem Wurzelelement als XPlanAuszug.

        Erwartung:
            Eine Meldung mit wird nicht unterstützt.
        """
        # Analog, aber mit falschem Element-Namen statt falschem Namespace.
        messages = self._get_messages(build_gml(root_tag='EtwasAnderes'))
        self.assertEqual(len(messages), 1)
        self.assertIn('wird nicht unterstützt', messages[0])

    # --- Pflichtfeld gemeinde (korrekt behandelter Fall) --------------------

    def test_fehlende_gemeinde_wird_mit_konkreter_meldung_abgelehnt(self):
        """
        Was wird geprüft:
            Ein GML ohne Gemeinde.

        Warum:
            Ohne Gemeinde ist der Plan keiner Organisation zuzuordnen.

        Erwartung:
            Eine Meldung, die gemeinde und keine Pflichtelemente nennt.
        """
        # Kein xplan:gemeinde-Block im GML -> spezifische Pflichtfeld-Meldung.
        messages = self._get_messages(build_gml(gemeinden=()))
        self.assertEqual(len(messages), 1)
        self.assertIn('gemeinde', messages[0])
        self.assertIn('keine Pflichtelemente', messages[0])

    def test_unbekannte_ags_wird_abgelehnt(self):
        """
        Was wird geprüft:
            Ein GML mit einer AGS, die in der Datenbank fehlt.

        Warum:
            Nur bekannte Organisationen dürfen Pläne erhalten.

        Erwartung:
            Eine Meldung mit der AGS 99999999 und dem Hinweis Datenbank gefunden.
        """
        # AGS-Format ok, aber keine passende AdministrativeOrganization in der DB.
        messages = self._get_messages(
            build_gml(gemeinden=(('99999999', 'Nicht existente Gemeinde'),))
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('99999999', messages[0])
        self.assertIn('Datenbank gefunden', messages[0])

    def test_gemeindename_stimmt_nicht_mit_datenbank_ueberein(self):
        """
        Was wird geprüft:
            Ein GML mit gültiger AGS, aber falschem Gemeindenamen.

        Warum:
            AGS und Name müssen zusammenpassen, sonst ist die Datei vermutlich fehlerhaft.

        Erwartung:
            Eine Meldung, dass der Name nicht mit dem der Organisation übereinstimmt.
        """
        # AGS existiert, aber der im GML angegebene Gemeindename passt nicht dazu.
        messages = self._get_messages(
            build_gml(gemeinden=((GUELTIGE_AGS, 'Falscher Gemeindename'),))
        )
        self.assertEqual(len(messages), 1)
        self.assertIn('stimmt nicht mit dem name der Organisation', messages[0])

    # --- Geltungsbereich (korrekt behandelter Fall) -------------------------

    def test_fehlender_geltungsbereich_wird_mit_konkreter_meldung_abgelehnt(self):
        """
        Was wird geprüft:
            Ein GML ohne Geltungsbereich.

        Erwartung:
            Genau die Meldung Geltungsbereich nicht gefunden!.
        """
        # Kein raeumlicherGeltungsbereich im GML -> eigene, klare Fehlermeldung.
        messages = self._get_messages(build_gml(include_geltungsbereich=False))
        self.assertEqual(messages, ["Geltungsbereich nicht gefunden!"])

    # --- Bekannte Schwäche der Fehlerbehandlung -----------------------------

    def test_fehlendes_pflichtfeld_name_liefert_nur_generische_fehlermeldung(self):
        """
        Was wird geprüft:
            Ein GML ohne Planname.

        Warum:
            Dokumentiert eine bekannte Schwäche: Das fehlende Element führt intern zu einem
            AttributeError, den der Validator zu einer allgemeinen Meldung zusammenfasst.

        Erwartung:
            Nur die generische Meldung XML-Dokument konnte nicht geparsed werden!.

        Hinweis:
            Der Test schlägt fehl, sobald der Validator eine genauere Meldung liefert.
        """
        messages = self._get_messages(build_gml(include_name=False))
        self.assertEqual(
            messages, ["XML-Dokument konnte nicht geparsed werden!"],
        )

    def test_fehlendes_pflichtfeld_planart_liefert_ebenfalls_nur_generische_meldung(self):
        """
        Was wird geprüft:
            Ein GML ohne Planart.

        Warum:
            Dieselbe Schwäche wie beim Planname.

        Erwartung:
            Nur die generische Meldung XML-Dokument konnte nicht geparsed werden!.
        """
        messages = self._get_messages(build_gml(include_planart=False))
        self.assertEqual(
            messages, ["XML-Dokument konnte nicht geparsed werden!"],
        )

    # --- Positiv-Gegenprobe --------------------------------------------------

    def test_gueltiges_gml_wird_nicht_abgelehnt(self):
        """
        Was wird geprüft:
            Kontrollprobe mit dem unveränderten Basis-GML aus build_gml().

        Warum:
            Die Negativtests beweisen nur etwas, wenn das Basis-GML selbst gültig ist.

        Erwartung:
            Der Validator wirft keine ValidationError.
        """
        try:
            bplan_content_validator(upload(build_gml()))
        except forms.ValidationError as error:
            self.fail(
                "Das als gültig gedachte Basis-GML wurde abgelehnt: "
                + "; ".join(error.messages)
            )