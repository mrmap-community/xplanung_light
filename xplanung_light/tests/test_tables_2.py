from types import SimpleNamespace

from django.contrib.gis.geos import GEOSGeometry
from django.test import SimpleTestCase
from django.urls import reverse

from xplanung_light import tables as t


def ns(**kw):
    return SimpleNamespace(**kw)


class PlanTableRenderTests(SimpleTestCase):

    def test_status_icons(self):
        for table in (t.BPlanTable([]), t.FPlanTable([]), t.BPlanPublicTable([]), t.FPlanPublicTable([])):
            with self.subTest(table=type(table).__name__):
                self.assertIn("fa-check", table.render_xplangml("x", None))
                self.assertIn("fa-xmark", table.render_xplangml("", None))
        self.assertIn("fa-xmark", t.BPlanPublicTable([]
                                                     ).render_xplangml(None, None))
        for table in (t.BPlanTable([]), t.FPlanTable([])):
            self.assertIn("fa-check", table.render_public(True))
            self.assertIn("fa-xmark", table.render_public(False))

    def test_zoom_and_name_links(self):
        geometry = GEOSGeometry(
            "POLYGON((0 0, 0 2, 1 2, 1 0, 0 0))", srid=4326)
        for table in (t.BPlanTable([]), t.FPlanTable([]), t.BPlanPublicTable([]), t.FPlanPublicTable([])):
            with self.subTest(table=type(table).__name__):
                self.assertIn("[[0.0, 0.0], [2.0, 1.0]]",
                              table.render_zoom(geometry))
        for table, name in ((t.BPlanPublicTable([]), "bplan-detail"), (t.FPlanPublicTable([]), "fplan-detail")):
            html = table.render_name("A <b>", ns(id=4))
            self.assertIn(reverse(name, kwargs={"pk": 4}), html)
            self.assertIn("A &lt;b&gt;", html)

    def test_count_links(self):
        for cls, method, prefix in (
            (t.BPlanTable, "render_count_attachments", "bplanattachment"),
            (t.BPlanTable, "render_count_beteiligungen", "bplanbeteiligung"),
            (t.BPlanTable, "render_count_uvps", "uvp"),
            (t.FPlanTable, "render_count_attachments", "fplanattachment"),
            (t.FPlanTable, "render_count_beteiligungen", "fplanbeteiligung"),
            (t.FPlanTable, "render_count_uvps", "fplan-uvp"),
        ):
            with self.subTest(table=cls.__name__, method=method):
                render = getattr(cls([]), method)
                self.assertIn(
                    reverse(f"{prefix}-create", kwargs={"planid": 5}), render(0, ns(id=5)))
                self.assertIn(
                    reverse(f"{prefix}-list", kwargs={"planid": 5}), render(3, ns(id=5)))


class BeteiligungTableTests(SimpleTestCase):
    TABLES = ((t.BPlanBeteiligungTable, "bplan"),
              (t.FPlanBeteiligungTable, "fplan"))

    def test_count_comments(self):
        for cls, plantyp in self.TABLES:
            with self.subTest(plantyp=plantyp):
                table, record = cls([]), ns(id=7, **{plantyp: ns(id=3)})
                kw = {"plantyp": plantyp, "planid": 3, "beteiligungid": 7}
                self.assertIn(reverse("beteiligungbeitrag-generic-create",
                              kwargs=kw), table.render_count_comments(0, record))
                self.assertIn(reverse("beteiligungbeitrag-list",
                              kwargs=kw), table.render_count_comments(2, record))

    def test_notification_button(self):
        for cls, plantyp in self.TABLES:
            table = cls([])

            def render(value, typ="2000", status=2, toebs=2):
                record = ns(id=7, typ=typ, status=status,
                            count_toebs=toebs, **{plantyp: ns(id=3)})
                return str(table.render_count_notifications(value, record))

            with self.subTest(plantyp=plantyp):
                self.assertIn("btn-success", render(0))
                self.assertIn("Benachrichtigen (2)", render(2))
                self.assertIn("btn-secondary", render(4, status=3))
                self.assertEqual(render(0, status=3), "")
                self.assertEqual(render(0, typ="1000"), "")
                # rot, solange None zurückkommt
                self.assertEqual(render(0, toebs=0), "")


class OrganizationTableTests(SimpleTestCase):

    def test_names_and_ags_are_escaped(self):
        for table in (t.AdministrativeOrganizationTable([]), t.AdministrativeOrganizationPublishingTable([])):
            for name_part, ts in (("Teil", "01"), ("", "")):
                with self.subTest(table=type(table).__name__, name_part=name_part):
                    record = ns(
                        id=3, name="St. {Ort} <b>", name_part=name_part, ags="07{316}<", ts=ts)
                    name, ags = str(table.render_name(record)), str(
                        table.render_ags(record))
                    # rot: KeyError beim Formatieren
                    self.assertIn("{Ort}", name)
                    self.assertIn("&lt;b&gt;", name)
                    self.assertIn("&lt;", ags)

    def test_publishing_counts_and_links(self):
        base = dict(id=3, num_bplan=2, num_fplan=1, num_bplan_public=1, num_fplan_public=1,
                    num_bplan_beteiligung=1, num_fplan_beteiligung=1)
        zero = {k: (v if k == "id" else 0) for k, v in base.items()}
        for cls, bplan_list, fplan_list in (
            (t.AdministrativeOrganizationPublishingTable, "bplan-list", "fplan-list"),
            (t.AdministrativeOrganizationPublishingPublicTable,
             "bplan-public-list", "fplan-public-list"),
        ):
            table, rec, empty = cls([]), ns(**base), ns(**zero)
            with self.subTest(table=cls.__name__):
                self.assertIn(
                    f"{reverse(bplan_list)}?gemeinde=3&is_public=on", table.render_num_bplan_public(rec))
                self.assertIn(
                    f"{reverse(fplan_list)}?gemeinde=3&is_public=on", table.render_num_fplan_public(rec))
                self.assertEqual(table.render_num_bplan_public(empty), "0")
                self.assertEqual(table.render_num_fplan_public(empty), "0")
                self.assertIn("SERVICE=WMS", table.render_wms(rec))
                self.assertIn("SERVICE=WFS", table.render_wfs(rec))
                self.assertIn(
                    reverse("ows", kwargs={"pk": 3}), table.render_wms(rec))
                if cls is t.AdministrativeOrganizationPublishingTable:
                    self.assertIn(">2<", table.render_laufende_verfahren(rec))
                else:
                    self.assertEqual(table.render_laufende_verfahren(rec), "2")
                self.assertEqual(table.render_laufende_verfahren(empty), "0")
                self.assertEqual(table.render_laufende_verfahren(empty), "0")
        table, rec, empty = t.AdministrativeOrganizationPublishingTable(
            []), ns(**base), ns(**zero)
        self.assertIn(f"{reverse('bplan-list')}?gemeinde=3",
                      table.render_num_bplan(rec))
        self.assertIn(f"{reverse('fplan-list')}?gemeinde=3",
                      table.render_num_fplan(rec))
        self.assertEqual(table.render_num_bplan(empty), "0")
        self.assertEqual(table.render_num_fplan(empty), "0")

    def test_request_for_role_admin_table_escapes_user_data(self):
        user = ns(username="armin", email='"<b>x</b>"@example.org')
        html = str(t.RequestForRoleAdminTable(
            []).render_owned_by_user(None, ns(owned_by_user=user)))
        self.assertIn("armin", html)
        # rot, bis der Formatstring gefixt ist
        self.assertNotIn("<b>x</b>", html)
