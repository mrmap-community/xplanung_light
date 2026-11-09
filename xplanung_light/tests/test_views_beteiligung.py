"""
Tests für Hilfsfunktionen in views/beteiligung.py: TipTap-Konverter für das PDF, JSON-
Aggregationen und die ReportLab-Helferklassen des PDF-Exports.
"""

from io import BytesIO
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate

from xplanung_light.models import AdministrativeOrganization
from xplanung_light.views import beteiligung as bv
from xplanung_light.views.beteiligung import TipTapNode, TipTapToReportLab


def text(t, *marks):
    """
    Erzeugt einen TipTap-Textknoten, optional mit Auszeichnungen (marks). Strings werden zu
    Dicts mit dem Schlüssel type.
    """
    node = {"type": "text", "text": t}
    if marks:
        node["marks"] = [{"type": m} if isinstance(m, str) else m for m in marks]
    return node


def para(*content):
    """Erzeugt einen TipTap-Absatzknoten (paragraph) aus den übergebenen Inhaltsknoten."""
    return {"type": "paragraph", "content": list(content)}


class TipTapConverterTests(SimpleTestCase):
    """
    Umwandlung von TipTap-JSON (Rich-Text-Editor) in ReportLab-Elemente für das PDF der
    Beteiligungsbeiträge. Reine Logik ohne Datenbank (SimpleTestCase).
    """

    def convert(self, *content):
        """Wandelt die übergebenen Knoten als Dokument (type doc) in ReportLab-Elemente um."""
        doc = TipTapNode.model_validate({"type": "doc", "content": list(content)})
        return TipTapToReportLab().convert_to_elements(doc)

    def test_headings_including_fallback_level(self):
        """
        Was wird geprüft:
            Überschriften der Stufen 1, 3 und 9 werden zu ReportLab-Elementen umgewandelt.

        Warum:
            Stufe 9 gibt es im Stylesheet nicht; der Konverter muss dann auf Heading2
            ausweichen, statt mit einem KeyError abzubrechen.

        Erwartung:
            Das Ergebnis ist für jede Stufe eine nicht leere Liste.
        """
        for level in (1, 3, 9):          # Stufe 9 gibt es im Stylesheet nicht -> Fallback auf Heading2
            with self.subTest(level=level):
                heading = {"type": "heading", "attrs": {"level": level}, "content": [text("Titel")]}
                self.assertTrue(self.convert(heading))

    def test_lists(self):
        """
        Was wird geprüft:
            Aufzählungen (bulletList) und nummerierte Listen (orderedList), auch mit einem
            leeren Listeneintrag.

        Warum:
            Regressionstest: nummerierte Listen wurden früher stillschweigend verworfen und
            fehlten im PDF.

        Erwartung:
            Für beide Listentypen kommt eine nicht leere Elementliste zurück.
        """
        items = [{"type": "listItem", "content": [para(text("Punkt"))]}, {"type": "listItem"}]
        for list_type in ("bulletList", "orderedList"):
            with self.subTest(list=list_type):
                self.assertTrue(self.convert({"type": list_type, "content": items}))

    def test_text_marks(self):
        """
        Was wird geprüft:
            Fett, kursiv sowie Links mit und ohne href-Attribut innerhalb eines Absatzes.

        Warum:
            Ein Link ohne attrs darf nicht zum Absturz führen (Fallback auf den Anker #).

        Erwartung:
            Die Umwandlung läuft fehlerfrei durch und liefert Elemente.
        """
        link = {"type": "link", "attrs": {"href": "https://example.org"}}
        self.assertTrue(self.convert(para(text("fett", "bold"), text("kursiv", "italic"),
                                          text("Link", link), text("ohne Href", {"type": "link"}))))


class AggregationHelperTests(SimpleTestCase):
    """
    Hilfsfunktionen, die JSON-Aggregationen für Datenbankabfragen bauen. Die PostgreSQL-
    Ausdrücke werden hier nur konstruiert, nicht ausgeführt, weil die CI SpatiaLite nutzt.
    """

    def test_postgres_expressions_can_be_built(self):
        """
        Was wird geprüft:
            Die PostgreSQL-Aggregationsausdrücke (JSONBAgg) lassen sich für BPlan und FPlan
            sowie mit und ohne Beteiligungsfilter konstruieren.

        Warum:
            Die PostgreSQL-Zweige laufen in der CI (SpatiaLite) nie in der Datenbank; so
            sind sie wenigstens syntaktisch abgesichert.

        Erwartung:
            Es wird jeweils ein Ausdruck zurückgegeben (nicht None).
        """
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                self.assertIsNotNone(bv.postgres_beitrag_aggregation(plantyp))
                for beteiligung in (True, False):
                    self.assertIsNotNone(bv.postgres_organization_aggregation(plantyp, beteiligung))

    def test_vendor_dispatch(self):
        """
        Was wird geprüft:
            Die Auswahl der Aggregationsfunktion anhand des Datenbank-Vendors
            (connection.vendor).

        Warum:
            Unbekannte Datenbanken müssen auffallen, statt falsches SQL zu erzeugen.

        Erwartung:
            postgresql liefert einen Ausdruck, jeder andere Vendor (hier oracle) löst
            NotImplementedError aus.

        Hinweis:
            connection wird im Modul durch einen MagicMock ersetzt.
        """
        for fn, args in ((bv.organization_json_aggregation, ("bplan", True)),
                         (bv.beitrag_json_aggregation, ("bplan",))):
            with self.subTest(fn=fn.__name__):
                with patch.object(bv, "connection", MagicMock(vendor="postgresql")):
                    self.assertIsNotNone(fn(*args))
                with patch.object(bv, "connection", MagicMock(vendor="oracle")), \
                     self.assertRaises(NotImplementedError):
                    fn(*args)


class JsonGroupArrayTests(TestCase):
    """
    Der Aggregatklasse JsonGroupArray (ältester Stand, funktionsgleich mit
    SQLiteJSONGroupArray) fehlt jeder Aufruf; getestet wird die SQL-Erzeugung direkt.
    """

    def test_aggregation_liefert_distinct_namen(self):
        """
        Was wird geprüft:
            JsonGroupArray aggregiert Namen einer Organisationstabelle als JSON-Array,
            mit distinct.

        Warum:
            Die Klasse wird im Code nicht verwendet, blockiert aber sonst die
            Abdeckung; ihr SQL-Ausdruck muss zumindest lauffähig bleiben.

        Erwartung:
            Beide angelegten Namen erscheinen genau einmal im Aggregat.
        """
        AdministrativeOrganization.objects.create(name="Alpha")
        AdministrativeOrganization.objects.create(name="Beta")
        AdministrativeOrganization.objects.create(name="Beta")
        ergebnis = AdministrativeOrganization.objects.aggregate(
            namen=bv.JsonGroupArray("name", distinct=True))
        wert = ergebnis["namen"]
        if isinstance(wert, str):
            wert = json.loads(wert)
        self.assertEqual(sorted(wert), ["Alpha", "Beta"])


class ReportLabHelferTests(SimpleTestCase):
    """
    ReportLab-Bausteine des PDF-Exports, die vom Deckblatt-Generator (noch) nicht
    aufgerufen werden: Zahlencode-Flowable, verankerte Überschrift für das
    Inhaltsverzeichnis, FinalCanvas und NumberedCanvas. Alle Tests bauen ein
    echtes PDF in den Speicher und prüfen nur den Erfolg — nicht den Bytesinhalt.
    """

    def setUp(self):
        # TOC_REGISTRY ist ein Modul-globaler Zwischenspeicher; sauber halten
        self._toc_stand = dict(bv.TOC_REGISTRY)

    def tearDown(self):
        bv.TOC_REGISTRY.clear()
        bv.TOC_REGISTRY.update(self._toc_stand)

    def test_numbered_canvas_ohne_versionsangabe(self):
        """
        Was wird geprüft:
            NumberedCanvas mit leerer XPLANUNG_LIGHT_VERSION.

        Warum:
            Der Kopf der PDF-Seiten greift auf settings.XPLANUNG_LIGHT_VERSION zu;
            fehlt der Wert, muss der Text mit "unknown" weiterlaufen.

        Erwartung:
            Der Dokumentbau endet mit einem gültigen PDF.
        """
        buf = BytesIO()
        with patch.object(bv.NumberedCanvas, "url", "https://example.org/pdf", create=True), \
             override_settings(XPLANUNG_LIGHT_VERSION=""):
            SimpleDocTemplate(buf, pagesize=A4).build(
                [Paragraph("Fließtext", getSampleStyleSheet()["Normal"])],
                canvasmaker=bv.NumberedCanvas)
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))

    def test_final_canvas_seitenzahl(self):
        """
        Was wird geprüft:
            FinalCanvas schreibt eine Seite mit zentrierter Seitenzahl.

        Warum:
            Die Klasse ist als RESERVED markiert ("Aktuell nicht verwendet") und
            soll für einen möglichen späteren Einsatz syntaktisch validiert bleiben.

        Erwartung:
            showPage/save erzeugen ein gültiges PDF.
        """
        buf = BytesIO()
        canvas = bv.FinalCanvas(buf, pagesize=A4)
        canvas.showPage()
        canvas.save()
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))

    def test_heading_with_anchor_sichert_toc_eintrag(self):
        """
        Was wird geprüft:
            HeadingWithAnchor registriert sich während des Zeichnens im TOC_REGISTRY.

        Warum:
            Für das geplante Inhaltsverzeichnis (siehe TODO im Code) wird die echte
            Seitenzahl einer Überschrift beim Rendern erfasst.

        Erwartung:
            Der Registry-Eintrag enthält Text und Seitenzahl der Überschrift.
        """
        buf = BytesIO()
        SimpleDocTemplate(buf, pagesize=A4).build(
            [bv.HeadingWithAnchor("Abwägungstabelle",
                                  getSampleStyleSheet()["Heading1"], "toc_test_key")])
        self.assertEqual(bv.TOC_REGISTRY["toc_test_key"]["text"], "Abwägungstabelle")
        self.assertGreaterEqual(bv.TOC_REGISTRY["toc_test_key"]["page"], 1)

    def test_qrcode_flowable(self):
        """
        Was wird geprüft:
            QRCodeFlowable meldet seine Größe (wrap) und rendert in ein Dokument.

        Warum:
            Der Zahlencode im PDF-Kopf wird über NumberedCanvas gezeichnet; das
            eigenständige Flowable (z. B. für Fließtext-Einbettung) ist ungenutzt
            und bleibt sonst ungetestet.

        Erwartung:
            wrap liefert (size, size); der Dokumentbau ergibt ein gültiges PDF.
        """
        flowable = bv.QRCodeFlowable("https://example.org", size=2 * cm)
        self.assertEqual(flowable.wrap(0, 0), (2 * cm, 2 * cm))
        buf = BytesIO()
        SimpleDocTemplate(buf, pagesize=A4).build([flowable])
        self.assertTrue(buf.getvalue().startswith(b"%PDF"))

    def test_build_story_discovery_und_final(self):
        """
        Was wird geprüft:
            build_story (Testgerüst für ein zweistufiges Inhaltsverzeichnis) im
            discovery- und im final-Lauf, mit und ohne Registry-Treffer.

        Warum:
            Die Funktion gehört zum ungenutzten TOC-Entwurf; der final-Lauf muss
            bekannte UND unbekannte Schlüssel sicher behandeln.

        Erwartung:
            Beide Läufe liefern eine nicht leere Elementliste; unbekannte Schlüssel
            werden übersprungen, ohne zu fehlschlagen.
        """
        daten = [{"id": "mit_registrierung", "title": "Titel A", "content": "Inhalt A"},
                 {"id": "ohne_registrierung", "title": "Titel B", "content": "Inhalt B"}]
        self.assertTrue(bv.PdfBeteiligungBeitraege.build_story(daten, mode="discovery"))
        bv.TOC_REGISTRY["mit_registrierung"] = {"page": 3, "text": "Titel A"}
        self.assertTrue(bv.PdfBeteiligungBeitraege.build_story(daten, mode="final"))

    def test_legacy_heading_und_list_handler(self):
        """
        Was wird geprüft:
            Die vom Konverter nicht mehr eingebundenen Alt-Handler
            _handle_heading_old und _handle_list_old.

        Warum:
            Beide Methoden liegen weiter im Code; ihr Verhalten (Überschrift mit
            Lesezeichen, Liste mit Bullets) wird hier fixiert, statt sie
            ungetestet mitzuschleppen.

        Erwartung:
            Beide Handler geben eine nicht leere Elementliste zurück.
        """
        converter = TipTapToReportLab()
        heading = TipTapNode.model_validate(
            {"type": "heading", "attrs": {"level": 2}, "content": [text("Alt")]}
        )
        self.assertTrue(converter._handle_heading_old(heading))
        liste = TipTapNode.model_validate(
            {"type": "bulletList",
             "content": [{"type": "listItem", "content": [para(text("Punkt"))]}]}
        )
        self.assertTrue(converter._handle_list_old(liste))

