"""
Tests für die Render-Methoden in tables.py, ohne Datenbank. Die Methoden werden direkt mit
einfachen Platzhalter-Objekten aufgerufen.

Schwerpunkte: Icons, Links, korrektes Escapen von Namen und Nutzerdaten (HTML-Injection) sowie
die Schaltflächen für Benachrichtigungen.
"""

from types import SimpleNamespace

from django.contrib.gis.geos import GEOSGeometry
from django.test import SimpleTestCase
from django.urls import reverse

from xplanung_light import tables as t


def ns(**kw):
    """Kurzform für einen einfachen Platzhalter mit den übergebenen Attributen (SimpleNamespace)."""
    return SimpleNamespace(**kw)


class PlanTableRenderTests(SimpleTestCase):
    """Render-Methoden der Plan-Tabellen (BPlan und FPlan, intern und öffentlich)."""

    def test_status_icons(self):
        """
        Was wird geprüft:
            Statusspalten: XPlan-GML vorhanden und öffentlich (Häkchen oder Kreuz).

        Warum:
            Die Liste zeigt auf einen Blick, ob eine GML-Datei vorliegt und der Plan
            öffentlich ist.

        Erwartung:
            Ein Wert ergibt fa-check, leer oder None ergibt fa-xmark.
        """
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
        """
        Was wird geprüft:
            Zoom-Link (Kartenausschnitt aus der Geometrie) und Namenslink der öffentlichen
            Tabelle.

        Warum:
            Der Name kommt aus der Datenbank und muss beim Ausgeben maskiert werden.

        Erwartung:
            Der Zoom enthält die Koordinaten des Ausschnitts, der Link zeigt auf die
            Detailseite und ein HTML-Name wird zu &lt;b&gt;.
        """
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
        """
        Was wird geprüft:
            Anzahl-Spalten für Anhänge, Beteiligungen und UVPs (BPlan und FPlan).

        Warum:
            Bei null Einträgen führt der Link zum Anlegen, sonst zur Liste.

        Erwartung:
            Wert 0 verweist auf die create-URL, Wert 3 auf die list-URL des Plans.
        """
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
    """Render-Methoden der Beteiligungs-Tabellen: Beitragszahl und Benachrichtigungen."""

    TABLES = ((t.BPlanBeteiligungTable, "bplan"),
              (t.FPlanBeteiligungTable, "fplan"))

    def test_count_comments(self):
        """
        Was wird geprüft:
            Beitragszahl in der Beteiligungstabelle.

        Warum:
            Ohne Beiträge soll direkt zum Erfassen, sonst zur Beitragsliste verlinkt werden.

        Erwartung:
            0 ergibt den Link zum generischen Beitrag anlegen, 2 den Link zur Beitragsliste.
        """
        for cls, plantyp in self.TABLES:
            with self.subTest(plantyp=plantyp):
                table, record = cls([]), ns(id=7, **{plantyp: ns(id=3)})
                kw = {"plantyp": plantyp, "planid": 3, "beteiligungid": 7}
                self.assertIn(reverse("beteiligungbeitrag-generic-create",
                              kwargs=kw), table.render_count_comments(0, record))
                self.assertIn(reverse("beteiligungbeitrag-list",
                              kwargs=kw), table.render_count_comments(2, record))

    def test_notification_button(self):
        """
        Was wird geprüft:
            Schaltfläche für TÖB-Benachrichtigungen je nach Beteiligungstyp, Status und
            Anzahl der TÖBs.

        Warum:
            Regressionstest: Bei aktiver Beteiligung ohne zugeordnete TÖBs gab die Methode
            None zurück und die Zelle zeigte vermutlich den Text None.

        Erwartung:
            Grün (btn-success) ohne Benachrichtigung, Gelb mit Zahl bei bereits versendeten,
            Grau bei beendetem Verfahren mit Benachrichtigungen; in allen übrigen Fällen ein
            leerer Text.
        """
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
                self.assertEqual(render(0, toebs=0), "")


class OrganizationTableTests(SimpleTestCase):
    """Render-Methoden der Organisations- und Rollenantrags-Tabellen."""

    def test_names_and_ags_are_escaped(self):
        """
        Was wird geprüft:
            Namen und AGS mit geschweiften Klammern und HTML-Zeichen, mit und ohne
            Namenszusatz.

        Warum:
            Regressionstest: format_html wurde mit einem selbst zusammengesetzten
            Formatstring aufgerufen. Das führte bei geschweiften Klammern zu KeyError und
            ließ HTML ungeschützt.

        Erwartung:
            Keine Ausnahme; geschweifte Klammern bleiben erhalten und HTML wird maskiert.
        """
        for table in (t.AdministrativeOrganizationTable([]), t.AdministrativeOrganizationPublishingTable([])):
            for name_part, ts in (("Teil", "01"), ("", "")):
                with self.subTest(table=type(table).__name__, name_part=name_part):
                    record = ns(
                        id=3, name="St. {Ort} <b>", name_part=name_part, ags="07{316}<", ts=ts)
                    name, ags = str(table.render_name(record)), str(
                        table.render_ags(record))
                    self.assertIn("{Ort}", name)
                    self.assertIn("&lt;b&gt;", name)
                    self.assertIn("&lt;", ags)

    def test_publishing_counts_and_links(self):
        """
        Was wird geprüft:
            Veröffentlichungstabellen: Planzahlen, Links, WMS/WFS-Adressen und laufende
            Verfahren.

        Warum:
            Die interne und die öffentliche Variante verlinken auf unterschiedliche Listen.

        Erwartung:
            Zahlen größer 0 sind Links auf die gefilterte Liste, 0 bleibt Text; WMS/WFS
            verweisen auf den ows-Endpunkt der Organisation.
        """
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
        table, rec, empty = t.AdministrativeOrganizationPublishingTable(
            []), ns(**base), ns(**zero)
        self.assertIn(f"{reverse('bplan-list')}?gemeinde=3",
                      table.render_num_bplan(rec))
        self.assertIn(f"{reverse('fplan-list')}?gemeinde=3",
                      table.render_num_fplan(rec))
        self.assertEqual(table.render_num_bplan(empty), "0")
        self.assertEqual(table.render_num_fplan(empty), "0")

    def test_request_for_role_admin_table_escapes_user_data(self):
        """
        Was wird geprüft:
            Die Spalte Antragsteller der Rollenantrags-Tabelle mit einer E-Mail, die HTML
            enthält.

        Warum:
            Regressionstest gegen HTML-Injection: Ein Antragsteller kann über seine E-Mail-
            Adresse Markup einschleusen, das Administratoren in der Tabelle sehen würden.

        Erwartung:
            Der Nutzername erscheint, das eingeschleuste HTML nicht unmaskiert.
        """
        user = ns(username="armin", email='"<b>x</b>"@example.org')
        html = str(t.RequestForRoleAdminTable(
            []).render_owned_by_user(None, ns(owned_by_user=user)))
        self.assertIn("armin", html)
        self.assertNotIn("<b>x</b>", html)
