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


class TipTapConverterTests(SimpleTestCase):

    def convert(self, *content):
        doc = TipTapNode.model_validate({"type": "doc", "content": list(content)})
        return TipTapToReportLab().convert_to_elements(doc)

    def test_headings_including_fallback_level(self):
        for level in (1, 3, 9):          # Stufe 9 gibt es im Stylesheet nicht -> Fallback auf Heading2
            with self.subTest(level=level):
                heading = {"type": "heading", "attrs": {"level": level}, "content": [text("Titel")]}
                self.assertTrue(self.convert(heading))

    def test_lists(self):
        items = [{"type": "listItem", "content": [para(text("Punkt"))]}, {"type": "listItem"}]
        for list_type in ("bulletList", "orderedList"):
            with self.subTest(list=list_type):
                self.assertTrue(self.convert({"type": list_type, "content": items}))

    def test_text_marks(self):
        link = {"type": "link", "attrs": {"href": "https://example.org"}}
        self.assertTrue(self.convert(para(text("fett", "bold"), text("kursiv", "italic"),
                                          text("Link", link), text("ohne Href", {"type": "link"}))))


class AggregationHelperTests(SimpleTestCase):

    def test_postgres_expressions_can_be_built(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                self.assertIsNotNone(bv.postgres_beitrag_aggregation(plantyp))
                for beteiligung in (True, False):
                    self.assertIsNotNone(bv.postgres_organization_aggregation(plantyp, beteiligung))

    def test_vendor_dispatch(self):
        for fn, args in ((bv.organization_json_aggregation, ("bplan", True)),
                         (bv.beitrag_json_aggregation, ("bplan",))):
            with self.subTest(fn=fn.__name__):
                with patch.object(bv, "connection", MagicMock(vendor="postgresql")):
                    self.assertIsNotNone(fn(*args))
                with patch.object(bv, "connection", MagicMock(vendor="oracle")), \
                     self.assertRaises(NotImplementedError):
                    fn(*args)

