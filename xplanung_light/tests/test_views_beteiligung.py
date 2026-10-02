from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from xplanung_light.views import beteiligung as bv
from xplanung_light.views.beteiligung import TipTapNode, TipTapToReportLab


def text(t, *marks):
    node = {"type": "text", "text": t}
    if marks:
        node["marks"] = [{"type": m} if isinstance(m, str) else m for m in marks]
    return node


def para(*content):
    return {"type": "paragraph", "content": list(content)}


# Testklasse: TipTapConverterTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class TipTapConverterTests(SimpleTestCase):

    def convert(self, *content):
        doc = TipTapNode.model_validate({"type": "doc", "content": list(content)})
        return TipTapToReportLab().convert_to_elements(doc)

    # Testfall: headings including Fallback level.
    # Erwartung/Absicherung: verwendet assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_headings_including_fallback_level(self):
        for level in (1, 3, 9):          # Stufe 9 gibt es im Stylesheet nicht -> Fallback auf Heading2
            with self.subTest(level=level):
                heading = {"type": "heading", "attrs": {"level": level}, "content": [text("Titel")]}
                self.assertTrue(self.convert(heading))

    # Testfall: lists.
    # Erwartung/Absicherung: verwendet assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_lists(self):
        items = [{"type": "listItem", "content": [para(text("Punkt"))]}, {"type": "listItem"}]
        for list_type in ("bulletList", "orderedList"):
            with self.subTest(list=list_type):
                self.assertTrue(self.convert({"type": list_type, "content": items}))

    # Testfall: text marks.
    # Erwartung/Absicherung: verwendet assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_text_marks(self):
        link = {"type": "link", "attrs": {"href": "https://example.org"}}
        self.assertTrue(self.convert(para(text("fett", "bold"), text("kursiv", "italic"),
                                          text("Link", link), text("ohne Href", {"type": "link"}))))


# Testklasse: AggregationHelperTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class AggregationHelperTests(SimpleTestCase):

    # Testfall: postgres expressions can be built.
    # Erwartung/Absicherung: verwendet assertIsNotNone.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_postgres_expressions_can_be_built(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                self.assertIsNotNone(bv.postgres_beitrag_aggregation(plantyp))
                for beteiligung in (True, False):
                    self.assertIsNotNone(bv.postgres_organization_aggregation(plantyp, beteiligung))

    # Testfall: vendor dispatch.
    # Erwartung/Absicherung: verwendet assertIsNotNone, assertRaises.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_vendor_dispatch(self):
        for fn, args in ((bv.organization_json_aggregation, ("bplan", True)),
                         (bv.beitrag_json_aggregation, ("bplan",))):
            with self.subTest(fn=fn.__name__):
                with patch.object(bv, "connection", MagicMock(vendor="postgresql")):
                    self.assertIsNotNone(fn(*args))
                with patch.object(bv, "connection", MagicMock(vendor="oracle")), \
                     self.assertRaises(NotImplementedError):
                    fn(*args)

