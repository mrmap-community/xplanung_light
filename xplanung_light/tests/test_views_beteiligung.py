"""
Tests für Hilfsfunktionen in views/beteiligung.py: TipTap-Konverter für das PDF und JSON-
Aggregationen.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

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

