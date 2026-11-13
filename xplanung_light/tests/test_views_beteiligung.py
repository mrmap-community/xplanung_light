"""
Tests für Hilfsfunktionen in views/beteiligung.py: TipTap-Konverter für das PDF, JSON-
Aggregationen und die ReportLab-Helferklassen des PDF-Exports.
"""

from io import BytesIO
import datetime
import json
from unittest.mock import MagicMock, patch

from django.contrib.gis.geos import GEOSGeometry
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate

from xplanung_light.models import (
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    ToebUnit,
)
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


class AggregatAufAktiverBankTests(TestCase):
    """
    Die von den Beteiligungs-Listen benutzten JSON-Aggregationen auf der jeweils
    laufenden Datenbank - jeweils genau auf der Modellabfrage, die die View nutzt.
    """

    def setUp(self):
        self.orga = AdministrativeOrganization.objects.create(
            name="Kreis Ahrweiler", ls="07", ks="117", gs="000")
        self.behoerde = AdministrativeOrganization.objects.create(
            name="Bezirksregierung", ls="07", ks="000", gs="000")
        self.bplan = BPlan.objects.create(
            name="Plan mit Gemeindenaggregat", public=True,
            geltungsbereich=GEOSGeometry("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"))
        self.bplan.gemeinde.add(self.orga)
        heute = timezone.now().date()
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, typ="1000", bekanntmachung_datum=heute,
            start_datum=heute, end_datum=heute + datetime.timedelta(days=14))
        self.toeb = ToebUnit.objects.create(
            organization=self.behoerde, name="Fachbereich Umwelt",
            theme=ToebUnit.OTH, public=True)
        self.beteiligung.assigned_toebs.add(self.toeb)

    @staticmethod
    def als_liste(wert):
        """Das Aggregat kommt je nach Bank als Text oder als Liste zurück."""
        return json.loads(wert) if isinstance(wert, str) else wert

    def test_gemeinden_aggregat_in_der_planliste(self):
        """
        Was wird geprüft:
            organization_json_aggregation() über der Beteiligungsabfrage, wie sie
            BeteiligungenListView annotiert.

        Warum:
            Die Ausdrücke wurden bisher nur konstruiert, nie ausgeführt - der
            PostgreSQL-Zweig lief in keiner Prüfung gegen eine echte Bank. Genau
            dort entsteht aber die Spalte "Gemeinden" der Beteiligungslisten.

        Erwartung:
            Ein Eintrag mit id und name der Gemeinde, auf beiden Banken.
        """
        beteiligung = BPlanBeteiligung.objects.filter(pk=self.beteiligung.pk).annotate(
            gemeinden=bv.organization_json_aggregation()).get()
        self.assertEqual(self.als_liste(beteiligung.gemeinden),
                         [{"id": self.orga.pk, "name": "Kreis Ahrweiler"}])

    def test_gemeinden_aggregat_in_der_reporterliste(self):
        """
        Was wird geprüft:
            organization_json_aggregation(beteiligung=True) über der Abfrage der
            Verknüpfungstabelle TÖB-Einheit <-> Beteiligung, wie sie
            ToebUnitBeteiligungenListView annotiert.

        Warum:
            Dieser Ast hängt an einer eigenen Beziehungskette (Verknüpfungstabelle
            -> Beteiligung -> Plan -> Gemeinde) und war nie ausgeführt.

        Erwartung:
            Derselbe Gemeindeeintrag wie in der Planliste.
        """
        verknuepfung = BPlanBeteiligung.assigned_toebs.through.objects.filter(
            toebunit=self.toeb).annotate(
            gemeinden=bv.organization_json_aggregation(
                plantyp="bplan", beteiligung=True)).get()
        self.assertEqual(self.als_liste(verknuepfung.gemeinden),
                         [{"id": self.orga.pk, "name": "Kreis Ahrweiler"}])

    def test_aggregat_mit_zwei_gemeinden_ohne_wiederholungen(self):
        """
        Was wird geprüft:
            Das Aggregat über einen Plan mit zwei Gemeinden (der distinct-Zweig).

        Warum:
            distinct=True ist der Grund, warum diese Aggregate überhaupt
            Handarbeit brauchen; ein weggefallenes DISTINCT fällt sonst nicht auf.

        Erwartung:
            Beide Gemeinden genau einmal, unabhängig von der Zahl der Treffer.
        """
        zweite = AdministrativeOrganization.objects.create(
            name="Stadt Bonn", ls="07", ks="221", gs="000")
        self.bplan.gemeinde.add(zweite)
        beteiligung = BPlanBeteiligung.objects.filter(pk=self.beteiligung.pk).annotate(
            gemeinden=bv.organization_json_aggregation()).get()
        namen = sorted(e["name"] for e in self.als_liste(beteiligung.gemeinden))
        self.assertEqual(namen, ["Kreis Ahrweiler", "Stadt Bonn"])


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

