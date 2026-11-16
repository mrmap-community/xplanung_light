"""Tests der Beteiligungslisten: Trefferzahl, Seiteneinteilung und Sichtbarkeit.

Hintergrund: die drei Beteiligungslisten vereinigen je zwei annotierte Abfragen
(BPlan- und FPlan-Verfahren) und rechnen Beiträge, Anlagen und Gemeinden als Aggregate
dazu. Früher lief diese Rechnung pro Seitenaufruf dreimal — für die Seite selbst, für
das count() der nummerierten Seiteneinteilung und für die „Anzahl"-Zeile der Vorlage.
Die Trefferzahl wird jetzt getrennt und ohne die Aggregate ermittelt
(``TrefferzahlMixIn``), die Seiteneinteilung löst kein count() mehr aus.

Die Tests halten fest, dass die billige Zahl dieselbe Treffermenge zeigt wie die teure
und dass die TÖB-Einschränkung weiterhin genau die eigenen Zuweisungen zeigt.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.views.generic import ListView
from django.urls import reverse
from django.utils import timezone

from xplanung_light.views.beteiligung import TrefferzahlMixIn
from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    FPlan,
    FPlanBeteiligung,
    ToebUnit,
)

User = get_user_model()

POLYGON = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')


class TrefferzahlDerBeteiligungslistenTests(TestCase):
    """Die „Anzahl" der Views muss die Zahl der Zeilen der Liste sein."""

    def setUp(self):
        self.heute = timezone.now().date()

        # Zwei Gebietskörperschaften — ein Plan gehört zu beiden
        self.gemeinde_a = AdministrativeOrganization.objects.create(
            name="Gemeinde Aa", ls="07", ks="111", gs="000", geometry=POLYGON)
        self.gemeinde_b = AdministrativeOrganization.objects.create(
            name="Gemeinde Bb", ls="07", ks="222", gs="000", geometry=POLYGON)

        # Nutzende: Orga-Admin beider Gemeinden, TÖB-Reporter einer Einheit,
        # Reporter ohne Einheit, Superuser
        self.admin = User.objects.create_user(username="schnell_admin", password="pw12345")
        AdminOrgaUser.objects.create(organization=self.gemeinde_a, user=self.admin, is_admin=True)
        AdminOrgaUser.objects.create(organization=self.gemeinde_b, user=self.admin, is_admin=True)

        self.reporter = User.objects.create_user(username="schnell_reporter", password="pw12345")
        reporter_entry = AdminOrgaUser.objects.create(
            organization=self.gemeinde_a, user=self.reporter, is_toeb_reporter=True)
        self.reporter_ohne = User.objects.create_user(
            username="schnell_reporter_leer", password="pw12345")
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a, user=self.reporter_ohne, is_toeb_reporter=True)

        self.unit_eigen = ToebUnit.objects.create(
            organization=self.gemeinde_a, name="Untere Naturschutzbehörde", theme="NSLP",
            public=True, geometry=POLYGON)
        self.unit_eigen.editors.add(reporter_entry)
        self.unit_fremd = ToebUnit.objects.create(
            organization=self.gemeinde_b, name="Wirtschaftsförderung", theme="OESO",
            public=True, geometry=POLYGON)

        self.superuser = User.objects.create_superuser(
            username="schnell_superuser", email="super@example.invalid", password="pw12345")

        # Ein aktives Trägerbeteiligungsverfahren je Plan, jeweils public
        self.plan_beide = self._bplan("BPlan Zwei Gemeinden", [self.gemeinde_a, self.gemeinde_b])
        self.plan_nur_a = self._bplan("BPlan Nur Aa", [self.gemeinde_a])
        self.plan_ohne_orga = self._bplan("BPlan Ohne Gebietskörperschaft", [])
        self.plan_fplan = self._fplan("FPlan Kreis Aa", [self.gemeinde_a])

        self.beteiligung_beide = self._beteiligung(self.plan_beide)
        self.beteiligung_nur_a = self._beteiligung(self.plan_nur_a)
        self.beteiligung_ohne = self._beteiligung(self.plan_ohne_orga)
        self.beteiligung_fplan = self._beteiligung(self.plan_fplan)

        # Zuweisungen: der Reporter sieht zwei BPlan- und ein FPlan-Verfahren. Das
        # Verfahren mit beiden Gemeinden ist auch der fremden Unit zugewiesen.
        self.beteiligung_beide.assigned_toebs.add(self.unit_eigen, self.unit_fremd)
        self.beteiligung_nur_a.assigned_toebs.add(self.unit_eigen)
        self.beteiligung_fplan.assigned_toebs.add(self.unit_eigen)

    # --- Hilfsmittel -------------------------------------------------------------

    def _bplan(self, name, gemeinden):
        """Bebauungsplan mit den angegebenen Gebietskörperschaften, veröffentlicht."""
        plan = BPlan.objects.create(name=name, nummer=name[-3:], planart="10000",
                                    public=True, geltungsbereich=POLYGON)
        plan.gemeinde.set(gemeinden)
        return plan

    def _fplan(self, name, gemeinden):
        """Flächennutzungsplan mit den angegebenen Gebietskörperschaften."""
        plan = FPlan.objects.create(name=name, nummer=name[-3:], planart="10000",
                                    public=True, geltungsbereich=POLYGON)
        plan.gemeinde.set(gemeinden)
        return plan

    def _beteiligung(self, plan):
        """Aktive Trägerbeteiligung: bekanntgegeben, läuft, Frist noch offen."""
        parameter = dict(
            typ="2000",
            bekanntmachung_datum=self.heute - timedelta(days=10),
            start_datum=self.heute - timedelta(days=1),
            end_datum=self.heute + timedelta(days=30),
            allow_online_beitrag=True,
        )
        if isinstance(plan, BPlan):
            return BPlanBeteiligung.objects.create(bplan=plan, **parameter)
        return FPlanBeteiligung.objects.create(fplan=plan, **parameter)

    def _login(self, benutzer):
        self.client.force_login(benutzer)

    def _url_orga(self, gemeinde):
        return reverse("organization-beteiligungen-list", kwargs={"pk": gemeinde.id})

    # --- Trefferzahl -------------------------------------------------------------

    def test_anzahl_ist_die_trefferzahl_der_toeb_liste(self):
        """
        Was wird geprüft: Die „Anzahl" der TÖB-Liste ist die Zahl ihrer Zeilen.

        Warum: die Zahl kommt jetzt aus den Querysets vor den Annotationen statt aus
        dem vereinigten Listenqueryset. Beide müssen auf dieselbe Trefferzahl kommen,
        sonst zeigt die Seite eine Zahl, die nicht zur Tabelle passt.

        Erwartung: anzahl == object_list.count() == 3 (zwei BPlan- und ein
        FPlan-Verfahren der eigenen Unit), die fremde Zuweisung zählt nicht.
        """
        self._login(self.reporter)
        response = self.client.get(reverse("toebbeteiligungen-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["anzahl"], response.context["object_list"].count())
        self.assertEqual(response.context["anzahl"], 3)

    def test_anzahl_ist_die_trefferzahl_der_buerger_und_orga_liste(self):
        """
        Was wird geprüft: Die Trefferzahl stimmt in Bürgerliste und Orga-Liste.

        Warum: der Admin-Filter springt über zwei ManyToMany-Beziehungen (Gemeinden,
        Admin-Rollen). Ein Plan, der zu zwei Gemeinden gehört, die dieselbe Person
        verwaltet, würde mehrfach gezählt — die Liste zeigt ihn trotzdem nur einmal.

        Erwartung: anzahl == object_list.count() == 3, auch für eine Orga-Adminperson.
        """
        self._login(self.admin)
        for url in (reverse("beteiligungen"), self._url_orga(self.gemeinde_a)):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(response.context["anzahl"],
                             response.context["object_list"].count(), url)
            self.assertEqual(response.context["anzahl"], 3, url)

    def test_verfahren_zweier_gemeinden_erscheint_nur_einmal(self):
        """
        Was wird geprüft: Ein Verfahren zweier Gemeinden erscheint nicht doppelt.

        Warum: die Vereinigung der früheren Fassung entfernte Duplikate, die aus den
        Gemeinde-Sprüngen kamen. Jetzt erledigen das die Hälften selbst; fällt das
        weg, steht dasselbe Verfahren zweimal in der Liste.

        Erwartung: in der Liste der Gemeinde A steht „BPlan Zwei Gemeinden" einmal.
        """
        self._login(self.admin)
        response = self.client.get(self._url_orga(self.gemeinde_a))
        namen = [zeile.xplan_name for zeile in response.context["object_list"]]
        self.assertEqual(namen.count("BPlan Zwei Gemeinden"), 1)
        self.assertEqual(len(namen), 3)

    def test_plan_ohne_gebietskoesrperschaft_zaehlt_mit(self):
        """
        Was wird geprüft: Ein Plan ohne Gebietskörperschaft fehlt weder in der Zahl
        noch in den Zeilen der Bürgerliste.

        Warum: ohne Gemeinden liefert das Gemeinde-Aggregat NULL. Die Zählung vor den
        Annotationen darf ein solches Verfahren nicht verlieren. Geprüft wird ohne die
        Tabellenvorlage: die Vorlage der Bürgerliste scheitert an Planen ohne
        Gebietskörperschaft schon auf dem Stand von master (Gemeinde-Link mit Kennung
        None) — das ist ein eigener Punkt und nicht Teil dieser Änderung.

        Erwartung: 4 Zeilen, dieselbe Zahl aus der Zählung, das Verfahren ohne
        Gebietskörperschaft ist dabei.
        """
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from xplanung_light.views.beteiligung import BeteiligungenListView

        view = BeteiligungenListView()
        view.request = RequestFactory().get(reverse("beteiligungen"))
        view.request.user = AnonymousUser()
        zeilen = view.get_queryset()
        self.assertEqual(sum(basis.count() for basis in view.zaehler_basis), zeilen.count())
        self.assertEqual(zeilen.count(), 4)
        self.assertIn("BPlan Ohne Gebietskörperschaft",
                      [zeile.xplan_name for zeile in zeilen])

    def test_anzahl_auf_der_seite_ist_nicht_leer(self):
        """
        Was wird geprüft: Die „Anzahl"-Zeile der Vorlage zeigt eine Zahl.

        Warum: die Vorlage greift nicht mehr auf object_list.count() zu, sondern auf
        den Kontextwert der View. Vergisst eine View den Wert, steht dort eine leere
        Zeile.

        Erwartung: auf der TÖB-Liste und auf der Orga-Liste steht „Anzahl: 3".
        """
        self._login(self.reporter)
        self.assertContains(self.client.get(reverse("toebbeteiligungen-list")), "Anzahl: 3")
        self._login(self.admin)
        self.assertContains(self.client.get(self._url_orga(self.gemeinde_a)), "Anzahl: 3")

    # --- Sichtbarkeit ------------------------------------------------------------

    def test_reporter_sieht_nur_seine_eigenen_zuweisungen(self):
        """
        Was wird geprüft: Die TÖB-Liste zeigt nur die Verfahren der eigenen Unit.

        Warum: die Einschränkung auf die eigenen TÖB-Units steht jetzt als Liste von
        Kennungen vor den Annotationen. Als Unterrabfrage wurde sie erst nach dem
        Voraggregieren geprüft — geprüft wird, dass sich an der Sichtbarkeit nichts
        geändert hat.

        Erwartung: die eigenen Verfahren sind da, das fremde fehlt.
        """
        self._login(self.reporter)
        response = self.client.get(reverse("toebbeteiligungen-list"))
        self.assertContains(response, "BPlan Nur Aa")
        self.assertContains(response, "BPlan Zwei Gemeinden")
        self.assertContains(response, "FPlan Kreis Aa")
        self.assertNotContains(response, "BPlan Ohne Gebietskörperschaft")

    def test_nutzer_ohne_toeb_einheit_sieht_keine_verfahren(self):
        """
        Was wird geprüft: Ohne TÖB-Unit bleibt die Liste leer.

        Warum: die Zahlliste der eigenen Units ist in diesem Fall leer. Eine leere
        Liste darf nicht als „keine Einschränkung" gelesen werden — sonst sähe eine
        Person ohne TÖB-Rolle den ganzen Bestand.

        Erwartung: HTTP 200, keine Zeilen, „Anzahl: 0".
        """
        self._login(self.reporter_ohne)
        response = self.client.get(reverse("toebbeteiligungen-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["anzahl"], 0)
        self.assertEqual(response.context["object_list"].count(), 0)
        self.assertContains(response, "Anzahl: 0")

    def test_superuser_sieht_alle_zuweisungen(self):
        """
        Was wird geprüft: Der Superuser sieht alle Zuweisungen beider Plantypen.

        Warum: für Superuser entfällt die Einschränkung auf eigene TÖB-Units. Die
        Trefferzahl muss ohne diese Einschränkung denselben Wert liefern wie die
        Vereinigung.

        Erwartung: anzahl == object_list.count() == 4 (alle Zuweisungen des Bestands).
        """
        self._login(self.superuser)
        response = self.client.get(reverse("toebbeteiligungen-list"))
        self.assertEqual(response.context["anzahl"], response.context["object_list"].count())
        self.assertEqual(response.context["anzahl"], 4)


class SeitenabfragenOhneDoppelteZaehlungTests(TestCase):
    """Pro Seitenaufruf darf die aggregierte Abfrage nur einmal laufen."""

    @classmethod
    def setUpTestData(cls):
        heute = timezone.now().date()
        orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Zz", ls="07", ks="999", gs="000", geometry=POLYGON)
        cls.reporter = User.objects.create_user(username="schnell_massen", password="pw12345")
        entry = AdminOrgaUser.objects.create(
            organization=orga, user=cls.reporter, is_toeb_reporter=True)
        cls.unit = ToebUnit.objects.create(
            organization=orga, name="Schulamt", theme="GS", public=True, geometry=POLYGON)
        cls.unit.editors.add(entry)

        # 30 laufende Trägerbeteiligungen — mehr als eine Seite fasst
        eigene = []
        for nummer in range(30):
            plan = BPlan.objects.create(
                name=f"BPlan Seite {nummer:02d}", nummer=f"{nummer:02d}", planart="10000",
                public=True, geltungsbereich=POLYGON)
            plan.gemeinde.add(orga)
            beteiligung = BPlanBeteiligung.objects.create(
                bplan=plan, typ="2000",
                bekanntmachung_datum=heute - timedelta(days=10),
                start_datum=heute - timedelta(days=5),
                end_datum=heute + timedelta(days=30 + nummer),
                allow_online_beitrag=True)
            beteiligung.assigned_toebs.add(cls.unit)
            eigene.append(beteiligung)

        # Ein Beitrag mit Anlage, damit die Aggregate nicht ins Leere laufen
        beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=eigene[0], toeb=cls.unit,
            titel="Stellungnahme des Schulamts", beschreibung="<p>Keine Einwände.</p>",
            name="Sachbearbeitung", approved=False, eingangsdatum=heute, typ="2000")
        from xplanung_light.models import BPlanBeteiligungBeitragAnhang
        BPlanBeteiligungBeitragAnhang.objects.create(beitrag=beitrag, name="Lageplan",
                                                     typ="3000")

    def _anfragen(self, url):
        """Seite aufrufen und die dabeigestellten Bankanfragen mitgeben."""
        self.client.force_login(self.reporter)
        with CaptureQueriesContext(connection) as kontext:
            response = self.client.get(url)
        return response, [q["sql"] for q in kontext.captured_queries]

    def test_aggregierte_abfrage_laeuft_nur_einmal_pro_seite(self):
        """
        Was wird geprüft: Die aggregierte Vereinigung läuft genau einmal pro Anfrage.

        Warum: nummerierte Seiteneinteilung und die „Anzahl"-Zeile der Vorlage zählten
        früher über demselben annotierten Vereinigungsqueryset — pro Aufruf liefen die
        Aggregate dreimal. Dagegen schützt dieser Test.

        Erwartung: genau eine Anfrage mit GROUP BY.
        """
        response, anfragen = self._anfragen(reverse("toebbeteiligungen-list"))
        self.assertEqual(response.status_code, 200)
        aggregiert = [a for a in anfragen if "group by" in a.lower()]
        self.assertEqual(len(aggregiert), 1,
                         f"{len(aggregiert)} aggregierte Abfragen statt einer")

    def test_trefferzahl_laeuft_ohne_aggregate(self):
        """
        Was wird geprüft: Die Trefferzahl wird ohne die Aggregate gezählt.

        Warum: die Zahl der Verfahren braucht weder die Beiträge noch die Anlagen oder
        die Gemeinden — auf einem großen Bestand ist das der Unterschied zwischen
        Hundertstel Sekunden und mehreren Sekunden.

        Erwartung: zwei Zählabfragen über die Zuweisungstabelle (eine je Hälfte der
        Vereinigung), ohne GROUP BY und ohne DISTINCT.
        """
        response, anfragen = self._anfragen(reverse("toebbeteiligungen-list"))
        zaehler = [a for a in anfragen
                   if a.lower().lstrip().startswith("select count(*)")
                   and "assigned_toebs" in a.lower()]
        self.assertEqual(len(zaehler), 2, "eine Zählabfrage je Hälfte der Vereinigung")
        for abfrage in zaehler:
            self.assertNotIn("group by", abfrage.lower())
            self.assertNotIn("distinct", abfrage.lower())
        self.assertEqual(response.context["anzahl"], 30)

    def test_zaehlung_der_seiteneinteilung_erspart_sich_die_aggregate(self):
        """
        Was wird geprüft: Die Seiteneinteilung zählt nicht noch einmal die Vereinigung.

        Warum: nummerierte Seiteneinteilung bestimmt vorab die Zahl aller Treffer —
        über den annotierten Queryset. Die Liste nutzt deshalb einen trägen Zähler.

        Erwartung: keine Zählabfrage mit GROUP BY.
        """
        response, anfragen = self._anfragen(reverse("toebbeteiligungen-list"))
        verdoppelt = [a for a in anfragen
                      if a.lower().lstrip().startswith("select count(*)")
                      and "group by" in a.lower()]
        self.assertEqual(verdoppelt, [], "die Seiteneinteilung zählt die Aggregate mit")


class SeiteneinteilungOhneVorabzaehlungTests(TestCase):
    """Die Blätterung funktioniert mit dem trägen Zähler bis an beide Enden."""

    @classmethod
    def setUpTestData(cls):
        heute = timezone.now().date()
        orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Yy", ls="07", ks="888", gs="000", geometry=POLYGON)
        cls.reporter = User.objects.create_user(username="schnell_blettert", password="pw12345")
        entry = AdminOrgaUser.objects.create(
            organization=orga, user=cls.reporter, is_toeb_reporter=True)
        unit = ToebUnit.objects.create(
            organization=orga, name="Bauamt", theme="GS", public=True, geometry=POLYGON)
        unit.editors.add(entry)
        for nummer in range(30):
            plan = BPlan.objects.create(
                name=f"BPlan Blatt {nummer:02d}", nummer=f"{nummer:02d}", planart="10000",
                public=True, geltungsbereich=POLYGON)
            plan.gemeinde.add(orga)
            beteiligung = BPlanBeteiligung.objects.create(
                bplan=plan, typ="2000",
                bekanntmachung_datum=heute - timedelta(days=10),
                start_datum=heute - timedelta(days=5),
                end_datum=heute + timedelta(days=30 + nummer),
                allow_online_beitrag=True)
            beteiligung.assigned_toebs.add(unit)

    def _seite(self, seite):
        self.client.force_login(self.reporter)
        return self.client.get(reverse("toebbeteiligungen-list"), {"page": seite})

    def test_zweite_seite_zeigt_die_restlichen_zeilen(self):
        """
        Was wird geprüft: Blatt 1 und 2 verteilen 30 Verfahren auf 25 und 5 Zeilen.

        Warum: der träge Zähler kennt die Gesamtzahl nicht, sondern sieht nur, ob nach
        der aktuellen Seite noch etwas kommt. Die Aufteilung muss trotzdem stimmen.

        Erwartung: 25 Zeilen auf Seite 1, 5 auf Seite 2, zwei Seiten im Blätterblock.
        """
        erste = self._seite(1)
        self.assertEqual(len(erste.context["table"].page.object_list), 25)
        self.assertEqual(erste.context["table"].paginator.num_pages, 2)
        zweite = self._seite(2)
        self.assertEqual(len(zweite.context["table"].page.object_list), 5)
        self.assertEqual(zweite.context["table"].paginator.num_pages, 2)

    def test_seitenzahl_ausserhalb_des_bestands_ohne_fehler(self):
        """
        Was wird geprüft: Mit ?page außerhalb des Bestands entsteht kein Fehler.

        Warum: ohne vorherige Zählung kann die Einteilung nicht prüfen, ob eine
        Seitenzahl noch im Bestand liegt. Seiten, die ins Leere laufen, müssen
        trotzdem eine Liste ausliefern.

        Erwartung: HTTP 200 für Seite 1, 2, 9999, „abc", 0 und -3 — keine 500er-Antwort.
        """
        for seite in (1, 2, 9999, "abc", 0, -3):
            response = self._seite(seite)
            self.assertEqual(response.status_code, 200, f"?page={seite}")


class ZaehlerOhneBasisTests(TestCase):
    """Der Ausweichfall des Mixins: ohne vorgegebene Basis zählt der Listenqueryset."""

    class NurMixIn(TrefferzahlMixIn, ListView):
        """View, die den Mixin nutzt, aber ``self.zaehler_basis`` nicht füllt."""

    def test_ohne_zaehler_basis_wird_ueber_den_listenqueryset_gezaehlt(self):
        """
        Was wird geprüft: Ohne Zähler-Basis zählt der Mixin über den Listenqueryset.

        Warum: eine View, die den Mixin ohne self.zaehler_basis nutzt, soll nicht ohne
        Zahl dastehen. Die billige Zählung ist eine Optimierung, keine Voraussetzung
        dafür, überhaupt eine Zahl zu zeigen.

        Erwartung: anzahl ist die Zahl der Zeilen des übergebenen Querysets.
        """
        orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Xx", ls="07", ks="777", gs="000", geometry=POLYGON)
        plan = BPlan.objects.create(name="BPlan Ausweichfall", nummer="AUS", planart="10000",
                                    public=True, geltungsbereich=POLYGON)
        plan.gemeinde.add(orga)
        BPlanBeteiligung.objects.create(
            bplan=plan, typ="2000",
            bekanntmachung_datum=timezone.now().date() - timedelta(days=1),
            start_datum=timezone.now().date(), end_datum=timezone.now().date() + timedelta(days=7))

        view = self.NurMixIn()
        view.request = RequestFactory().get("/")
        context = view.get_context_data(object_list=BPlanBeteiligung.objects.all())
        self.assertEqual(context["anzahl"], BPlanBeteiligung.objects.count())
        self.assertEqual(context["anzahl"], 1)
