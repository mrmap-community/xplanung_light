"""Berechtigungs- und IDOR-Regressionstests für xplanung_light.

Die Tests prüfen drei zentrale Sicherheitsbereiche:
1. Zugriffsschutz für nicht angemeldete und nicht berechtigte Benutzer,
2. korrekte Gemeinde-Administratorrechte beim Bearbeiten und Löschen,
3. Schutz vor dem Kombinieren fremder Objekt-IDs über manipulierte URLs
   (IDOR bzw. Überschreitung der Plan-/Objektgrenze).
"""
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    BPlanSpezExterneReferenz,
    FPlan,
    FPlanBeteiligung,
    FPlanSpezExterneReferenz,
)


class PermissionTestBase(TestCase):
    """Gemeinsame Testgrundlage mit Fixtures, Testbenutzern und Testobjekten."""
    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "fplan.json",
        "admin_orga_user.json",
    ]

    PLAN_PK = 4318
    ORGA_PK = 1531
    # FNP Neustadt Weinstraße - einziger FPlan in der fplan.json-Fixture,
    # gehört ebenfalls zu ORGA_PK.
    FPLAN_PK = 631

    @classmethod
    def setUpTestData(cls):
        """Legt die gemeinsamen Testobjekte aus den Fixtures und den fremden Testbenutzer an."""
        cls.gemeinde_admin = User.objects.get(username="admin_stadt_neustadt")
        cls.fremder_user = User.objects.create_user(
            username="fremder_user",
            password="nicht-relevant-wegen-force_login",
        )
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        cls.fplan = FPlan.objects.get(pk=cls.FPLAN_PK)
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)

    def setUp(self):
        """Erzeugt für jeden Test einen frischen Django-Testclient."""
        self.client = Client()

    @staticmethod
    def make_gemeinde(name, gs):
        """Erzeugt eine zusätzliche Gemeinde, die für Rechte- und Mehrgemeindetests
        verwendet wird.
        """
        return AdministrativeOrganization.objects.create(
            name=name,
            type=AdministrativeOrganization.COM,
            ls="07",
            ks="000",
            gs=str(gs),
        )

    @staticmethod
    def make_admin(user, gemeinde):
        """Verknüpft einen Benutzer als Administrator mit einer Gemeinde."""
        return AdminOrgaUser.objects.create(
            organization=gemeinde,
            user=user,
            is_admin=True,
            is_toeb_reporter=False,
        )

    @staticmethod
    def make_bplan(name, gemeinde):
        """Erzeugt einen zweiten Bebauungsplan und weist ihn der angegebenen Gemeinde zu."""
        fixture_plan = BPlan.objects.get(pk=PermissionTestBase.PLAN_PK)
        plan = BPlan.objects.create(
            name=name,
            nummer="TEST-2",
            planart=BPlan.BPLAN,
            geltungsbereich=fixture_plan.geltungsbereich,
        )
        plan.gemeinde.add(gemeinde)
        return plan

    @staticmethod
    def make_fplan(name, gemeinde):
        """Erzeugt einen zweiten Flächennutzungsplan und weist ihn der angegebenen
        Gemeinde zu. Analog zu make_bplan(), aber für FPlan.
        """
        fixture_fplan = FPlan.objects.get(pk=PermissionTestBase.FPLAN_PK)
        plan = FPlan.objects.create(
            name=name,
            nummer="TEST-2",
            planart=FPlan.FPLAN,
            geltungsbereich=fixture_fplan.geltungsbereich,
        )
        plan.gemeinde.add(gemeinde)
        return plan

    @staticmethod
    def make_beteiligung(plan):
        """Erzeugt eine Auslegungs-Beteiligung (mit Online-Beitrag möglich) für den
        angegebenen Plan, mit einem zeitlich gültigen Testzeitraum relativ zu heute.

        Für Tests, die stattdessen eine TOEB-Beteiligung ohne Online-Beitrag
        benötigen, siehe make_toeb_beteiligung() weiter unten.
        """
        heute = date.today()

        return BPlanBeteiligung.objects.create(
            bplan=plan,
            bekanntmachung_datum=heute - timedelta(days=14),
            start_datum=heute - timedelta(days=7),
            end_datum=heute + timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )

    @staticmethod
    def make_toeb_beteiligung(plan):
        """Erzeugt eine TOEB-Beteiligung (Träger öffentlicher Belange, kein
        Online-Beitrag) für den angegebenen Plan, mit festen Testdaten.

        Eigenständige Methode statt einer gleichnamigen, überschreibenden
        Variante von make_beteiligung() - vorher gab es in
        XPlanRelationPermissions eine make_beteiligung()-Override mit
        abweichenden Werten (TOEB statt AUSLEGUNG, feste statt relative
        Daten, allow_online_beitrag=False), die den Basis-Helper stillschweigend
        verdeckt hat. Das war leicht zu übersehen und führte in den
        Erweiterungsdateien (test_permissions_extented_with_additions.py)
        bereits zu einer eigenen, erneut duplizierten Kopie derselben
        TOEB-Variante. Mit einem eigenen Namen kann dieselbe Methode jetzt
        überall wiederverwendet werden, ohne die Basisklasse zu verdecken.
        """
        return BPlanBeteiligung.objects.create(
            bplan=plan,
            typ=BPlanBeteiligung.TOEB,
            bekanntmachung_datum=date(2026, 1, 1),
            start_datum=date(2026, 1, 2),
            end_datum=date(2026, 1, 31),
            allow_online_beitrag=False,
        )

    @staticmethod
    def make_fplan_beteiligung(plan):
        """Erzeugt eine Auslegungs-Beteiligung für einen FPlan. Analog zu
        make_beteiligung(), aber für FPlanBeteiligung (FK-Feld heißt 'fplan'
        statt 'bplan').
        """
        heute = date.today()

        return FPlanBeteiligung.objects.create(
            fplan=plan,
            bekanntmachung_datum=heute - timedelta(days=14),
            start_datum=heute - timedelta(days=7),
            end_datum=heute + timedelta(days=7),
            typ=FPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )

    @staticmethod
    def make_fplan_toeb_beteiligung(plan):
        """Erzeugt eine TOEB-Beteiligung für einen FPlan. Analog zu
        make_toeb_beteiligung(), aber für FPlanBeteiligung.
        """
        return FPlanBeteiligung.objects.create(
            fplan=plan,
            typ=FPlanBeteiligung.TOEB,
            bekanntmachung_datum=date(2026, 1, 1),
            start_datum=date(2026, 1, 2),
            end_datum=date(2026, 1, 31),
            allow_online_beitrag=False,
        )

    def plan_update_data(self, plan, gemeinden, *, name=None):
        """Baut die POST-Daten für das Bearbeiten eines Plans einschließlich seiner
        Gemeinde-Zuweisungen.
        """
        return {
            "name": name or plan.name,
            "nummer": plan.nummer,
            "planart": plan.planart,
            "geltungsbereich": plan.geltungsbereich.wkt,
            "gemeinde": [str(g.pk) for g in gemeinden],
        }


class BPlanPermissions(PermissionTestBase):
    """
    Berechtigungen für Bearbeitung und Löschung eines XPlans.

    Fachregeln:
    - Update: Admin mindestens einer aktuell zugewiesenen Gemeinde darf den Plan
      bearbeiten.
    - Gemeinde-Zuweisungen dürfen nur Gemeinden betreffen, für die der User
      selbst Admin ist.
    - Delete: User muss Admin aller dem Plan zugewiesenen Gemeinden sein.
    """

    def test_anonymous_user_is_redirected_to_login_on_update(self):
        """Prüft, dass ein nicht angemeldeter Benutzer beim Aufruf der Planbearbeitung
        zum Login umgeleitet wird.
        """
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_foreign_user_cannot_update_plan(self):
        """Prüft, dass ein angemeldeter Benutzer ohne passende Gemeinde-Adminrechte den
        Plan nicht bearbeiten darf.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_update_plan_via_direct_post(self):
        """Prüft, dass die Berechtigungsprüfung auch bei einem direkten POST nicht
        umgangen werden kann.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data={},
        )
        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_update_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Bearbeitungsformular
        öffnen darf.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_update_plan_without_changing_gemeinden(self):
        """Prüft eine normale Planänderung, bei der die bestehende Gemeinde-Zuweisung
        unverändert bleibt.
        """
        self.client.force_login(self.gemeinde_admin)
        old_name = self.plan.name

        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data=self.plan_update_data(
                self.plan,
                [self.gemeinde],
                name=old_name + " geändert",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.name, old_name + " geändert")
        self.assertEqual(list(self.plan.gemeinde.values_list("pk", flat=True)), [self.gemeinde.pk])

    def test_admin_cannot_add_gemeinde_without_admin_role(self):
        """Prüft, dass ein Benutzer keine Gemeinde hinzufügen kann, für die er selbst
        keine Adminrechte besitzt.
        """
        fremde_gemeinde = self.make_gemeinde("Nicht eigene Gemeinde", 991)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data=self.plan_update_data(
                self.plan,
                [self.gemeinde, fremde_gemeinde],
                name=self.plan.name + " unverändert",
            ),
        )

        self.plan.refresh_from_db()
        self.assertNotIn(fremde_gemeinde.pk, self.plan.gemeinde.values_list("pk", flat=True))
        self.assertEqual(
            set(self.plan.gemeinde.values_list("pk", flat=True)),
            {self.gemeinde.pk},
        )
        # Je nach konkreter Implementierung kann der View bei diesem
        # Validierungsfehler 200 zurückgeben oder mit Redirect arbeiten.
        self.assertIn(response.status_code, {200, 302})

    def test_admin_can_add_gemeinde_for_which_user_is_admin(self):
        """Prüft, dass ein Benutzer eine Gemeinde hinzufügen darf, in der er Administrator ist."""
        neue_gemeinde = self.make_gemeinde("Eigene zweite Gemeinde", 992)
        self.make_admin(self.gemeinde_admin, neue_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data=self.plan_update_data(
                self.plan,
                [self.gemeinde, neue_gemeinde],
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(
            set(self.plan.gemeinde.values_list("pk", flat=True)),
            {self.gemeinde.pk, neue_gemeinde.pk},
        )

    def test_admin_cannot_remove_gemeinde_for_which_user_is_not_admin(self):
        """Prüft, dass ein Benutzer eine fremde Gemeinde nicht aus dem Plan entfernen kann."""
        fremde_gemeinde = self.make_gemeinde("Fremde Gemeinde", 993)
        self.plan.gemeinde.add(fremde_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data=self.plan_update_data(
                self.plan,
                [self.gemeinde],
            ),
        )

        self.plan.refresh_from_db()
        self.assertIn(
            fremde_gemeinde.pk,
            self.plan.gemeinde.values_list("pk", flat=True),
        )
        self.assertIn(response.status_code, {200, 302})

    def test_anonymous_user_cannot_delete_plan(self):
        """Prüft den Login-Schutz beim Löschen eines Plans und stellt sicher, dass der
        Plan erhalten bleibt.
        """
        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_admin_of_only_one_of_two_gemeinden_cannot_delete_plan(self):
        """Prüft die All-Admin-Regel: Bei mehreren Plan-Gemeinden reicht die Adminrolle
        nur in einer Gemeinde nicht aus.
        """
        fremde_gemeinde = self.make_gemeinde("Zweite Gemeinde", 994)
        self.plan.gemeinde.add(fremde_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_admin_of_all_gemeinden_can_delete_plan(self):
        """Prüft, dass ein Benutzer den Plan löschen darf, wenn er in allen
        zugewiesenen Gemeinden Administrator ist.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde", 995)
        self.plan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BPlan.objects.filter(pk=self.PLAN_PK).exists())


class FPlanPermissions(PermissionTestBase):
    """
    Berechtigungen für Bearbeitung und Löschung eines Flächennutzungsplans (FPlan).

    Spiegelbild von BPlanPermissions: FPlanUpdateView/FPlanDeleteView erben von
    denselben generischen XPlanUpdateView/XPlanDeleteView wie die BPlan-Views
    (siehe views/fplan.py), die Berechtigungslogik ist also identisch. Dieser
    Test stellt sicher, dass sie tatsächlich auch für FPlan korrekt greift und
    nicht implizit auf BPlan-spezifische Annahmen angewiesen ist.
    """

    def test_anonymous_user_is_redirected_to_login_on_update(self):
        """Prüft, dass ein nicht angemeldeter Benutzer beim Aufruf der FPlan-Bearbeitung
        zum Login umgeleitet wird.
        """
        response = self.client.get(
            reverse("fplan-update", args=[self.FPLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_foreign_user_cannot_update_plan(self):
        """Prüft, dass ein angemeldeter Benutzer ohne passende Gemeinde-Adminrechte den
        FPlan nicht bearbeiten darf.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.get(
            reverse("fplan-update", args=[self.FPLAN_PK])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_update_plan_via_direct_post(self):
        """Prüft, dass die Berechtigungsprüfung auch bei einem direkten POST nicht
        umgangen werden kann.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.post(
            reverse("fplan-update", args=[self.FPLAN_PK]),
            data={},
        )
        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_update_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Bearbeitungsformular
        öffnen darf.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(
            reverse("fplan-update", args=[self.FPLAN_PK])
        )
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_update_plan_without_changing_gemeinden(self):
        """Prüft eine normale Planänderung, bei der die bestehende Gemeinde-Zuweisung
        unverändert bleibt.
        """
        self.client.force_login(self.gemeinde_admin)
        old_name = self.fplan.name

        response = self.client.post(
            reverse("fplan-update", args=[self.FPLAN_PK]),
            data=self.plan_update_data(
                self.fplan,
                [self.gemeinde],
                name=old_name + " geändert",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.fplan.refresh_from_db()
        self.assertEqual(self.fplan.name, old_name + " geändert")
        self.assertEqual(list(self.fplan.gemeinde.values_list("pk", flat=True)), [self.gemeinde.pk])

    def test_admin_cannot_add_gemeinde_without_admin_role(self):
        """Prüft, dass ein Benutzer keine Gemeinde hinzufügen kann, für die er selbst
        keine Adminrechte besitzt.
        """
        fremde_gemeinde = self.make_gemeinde("Nicht eigene Gemeinde (FPlan)", 1101)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("fplan-update", args=[self.FPLAN_PK]),
            data=self.plan_update_data(
                self.fplan,
                [self.gemeinde, fremde_gemeinde],
                name=self.fplan.name + " unverändert",
            ),
        )

        self.fplan.refresh_from_db()
        self.assertNotIn(fremde_gemeinde.pk, self.fplan.gemeinde.values_list("pk", flat=True))
        self.assertEqual(
            set(self.fplan.gemeinde.values_list("pk", flat=True)),
            {self.gemeinde.pk},
        )
        # Je nach konkreter Implementierung kann der View bei diesem
        # Validierungsfehler 200 zurückgeben oder mit Redirect arbeiten.
        self.assertIn(response.status_code, {200, 302})

    def test_admin_can_add_gemeinde_for_which_user_is_admin(self):
        """Prüft, dass ein Benutzer eine Gemeinde hinzufügen darf, in der er Administrator ist."""
        neue_gemeinde = self.make_gemeinde("Eigene zweite Gemeinde (FPlan)", 1102)
        self.make_admin(self.gemeinde_admin, neue_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("fplan-update", args=[self.FPLAN_PK]),
            data=self.plan_update_data(
                self.fplan,
                [self.gemeinde, neue_gemeinde],
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.fplan.refresh_from_db()
        self.assertEqual(
            set(self.fplan.gemeinde.values_list("pk", flat=True)),
            {self.gemeinde.pk, neue_gemeinde.pk},
        )

    def test_admin_cannot_remove_gemeinde_for_which_user_is_not_admin(self):
        """Prüft, dass ein Benutzer eine fremde Gemeinde nicht aus dem FPlan entfernen kann."""
        fremde_gemeinde = self.make_gemeinde("Fremde Gemeinde (FPlan)", 1103)
        self.fplan.gemeinde.add(fremde_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("fplan-update", args=[self.FPLAN_PK]),
            data=self.plan_update_data(
                self.fplan,
                [self.gemeinde],
            ),
        )

        self.fplan.refresh_from_db()
        self.assertIn(
            fremde_gemeinde.pk,
            self.fplan.gemeinde.values_list("pk", flat=True),
        )
        self.assertIn(response.status_code, {200, 302})

    def test_anonymous_user_cannot_delete_plan(self):
        """Prüft den Login-Schutz beim Löschen eines FPlans und stellt sicher, dass der
        Plan erhalten bleibt.
        """
        response = self.client.post(
            reverse("fplan-delete", args=[self.FPLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertTrue(FPlan.objects.filter(pk=self.FPLAN_PK).exists())

    def test_admin_of_only_one_of_two_gemeinden_cannot_delete_plan(self):
        """Prüft die All-Admin-Regel: Bei mehreren Plan-Gemeinden reicht die Adminrolle
        nur in einer Gemeinde nicht aus.
        """
        fremde_gemeinde = self.make_gemeinde("Zweite Gemeinde (FPlan)", 1104)
        self.fplan.gemeinde.add(fremde_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("fplan-delete", args=[self.FPLAN_PK])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(FPlan.objects.filter(pk=self.FPLAN_PK).exists())

    def test_admin_of_all_gemeinden_can_delete_plan(self):
        """Prüft, dass ein Benutzer den FPlan löschen darf, wenn er in allen
        zugewiesenen Gemeinden Administrator ist.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde (FPlan)", 1105)
        self.fplan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("fplan-delete", args=[self.FPLAN_PK])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(FPlan.objects.filter(pk=self.FPLAN_PK).exists())


class XPlanRelationPermissions(PermissionTestBase):
    """
    Permission-/IDOR-Tests für die generischen XPlanRelationsViews.

    Besonders wichtig:
    - Create muss auch bei direktem POST geprüft werden.
    - Update/Delete dürfen ein Objekt niemals über pk aus einem anderen Plan
      erreichen, wenn planid auf einen anderen Plan zeigt.
    - Delete verlangt Admin-Rechte für alle dem Plan zugewiesenen Gemeinden.
    """

    def test_foreign_user_cannot_create_relation_via_direct_post(self):
        """Prüft, dass eine Relation nicht per direktem POST ohne passende
        Gemeinde-Adminrechte angelegt werden kann.
        """
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "bplanbeteiligung-create",
                kwargs={"planid": self.PLAN_PK},
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_relation_create_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Relationsformular öffnen darf."""
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "bplanbeteiligung-create",
                kwargs={"planid": self.PLAN_PK},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_foreign_user_cannot_update_relation(self):
        """Prüft, dass ein fremder Benutzer eine bestehende Relation nicht bearbeiten kann."""
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "bplanbeteiligung-update",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_relation_update_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Relationsformular
        zur Bearbeitung öffnen darf.
        """
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "bplanbeteiligung-update",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_relation_update_cannot_cross_plan_boundary(self):
        """Prüft, dass Plan-ID und Objekt-ID nicht aus unterschiedlichen Plänen
        kombiniert werden können.
        """
        other_plan = self.make_bplan("Anderer Testplan", self.gemeinde)
        beteiligung = self.make_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "bplanbeteiligung-update",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_foreign_user_cannot_delete_relation(self):
        """Prüft, dass ein fremder Benutzer eine Relation nicht löschen kann."""
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "bplanbeteiligung-delete",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_relation_delete_cannot_cross_plan_boundary(self):
        """Prüft, dass beim Löschen einer Relation kein Objekt aus einem anderen Plan
        über eine manipulierte URL erreicht wird.
        """
        other_plan = self.make_bplan("Anderer Testplan", self.gemeinde)
        beteiligung = self.make_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "bplanbeteiligung-delete",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_foreign_user_cannot_create_attachment_via_direct_post(self):
        """Prüft den Berechtigungsschutz beim direkten POST zum Anlegen eines Plan-Anhangs."""
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "bplanattachment-create",
                kwargs={"planid": self.PLAN_PK},
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_attachment_update_cannot_cross_plan_boundary(self):
        """Prüft, dass ein Anhang aus einem anderen Plan nicht über eine fremde Plan-ID
        bearbeitet werden kann.
        """
        other_plan = self.make_bplan("Anderer Attachment-Plan", self.gemeinde)
        attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=other_plan,
            name="Fremde Referenz",
            typ=BPlanSpezExterneReferenz.BESCHREIBUNG,
        )
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "bplanattachment-update",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": attachment.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_attachment_delete_cannot_cross_plan_boundary(self):
        """Prüft, dass ein Anhang aus einem anderen Plan nicht über eine fremde Plan-ID
        gelöscht werden kann.
        """
        other_plan = self.make_bplan("Anderer Attachment-Delete-Plan", self.gemeinde)
        attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=other_plan,
            name="Fremde Referenz",
            typ=BPlanSpezExterneReferenz.BESCHREIBUNG,
        )
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "bplanattachment-delete",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": attachment.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanSpezExterneReferenz.objects.filter(pk=attachment.pk).exists()
        )

    def test_admin_of_only_one_plan_gemeinde_cannot_delete_relation(self):
        """Prüft, dass das Löschen einer generischen XPlan-Relation die Adminrechte für
        alle Plan-Gemeinden erfordert.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Gemeinde", 996)
        self.plan.gemeinde.add(zweite_gemeinde)
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "bplanbeteiligung-delete",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_admin_of_all_plan_gemeinden_can_delete_relation(self):
        """Prüft, dass die Relation gelöscht werden darf, wenn der Benutzer in allen
        Plan-Gemeinden Administrator ist.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde", 997)
        self.plan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "bplanbeteiligung-delete",
                kwargs={
                    "planid": self.PLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            BPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

class FPlanRelationPermissions(PermissionTestBase):
    """
    Permission-/IDOR-Tests für die generischen XPlanRelationsViews, hier für FPlan.

    Spiegelbild von XPlanRelationPermissions: FPlanBeteiligungCreateView/
    UpdateView/DeleteView und FPlanSpezExterneReferenzCreateView/UpdateView/
    DeleteView erben von denselben generischen XPlanRelationsCreateView/
    UpdateView/DeleteView wie die BPlan-Pendants (siehe views/fplanbeteiligung.py
    und views/fplanspezexternereferenz.py). Getestet wird dieselbe Fachregel wie
    bei XPlanRelationPermissions:
    - Create muss auch bei direktem POST geprüft werden.
    - Update/Delete dürfen ein Objekt niemals über pk aus einem anderen Plan
      erreichen, wenn planid auf einen anderen Plan zeigt.
    - Delete verlangt Admin-Rechte für alle dem Plan zugewiesenen Gemeinden.
    """

    def test_foreign_user_cannot_create_relation_via_direct_post(self):
        """Prüft, dass eine Relation nicht per direktem POST ohne passende
        Gemeinde-Adminrechte angelegt werden kann.
        """
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "fplanbeteiligung-create",
                kwargs={"planid": self.FPLAN_PK},
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_relation_create_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Relationsformular öffnen darf."""
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "fplanbeteiligung-create",
                kwargs={"planid": self.FPLAN_PK},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_foreign_user_cannot_update_relation(self):
        """Prüft, dass ein fremder Benutzer eine bestehende Relation nicht bearbeiten kann."""
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "fplanbeteiligung-update",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_relation_update_form(self):
        """Prüft, dass ein berechtigter Gemeinde-Administrator das Relationsformular
        zur Bearbeitung öffnen darf.
        """
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "fplanbeteiligung-update",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_relation_update_cannot_cross_plan_boundary(self):
        """Prüft, dass Plan-ID und Objekt-ID nicht aus unterschiedlichen FPlänen
        kombiniert werden können.
        """
        other_plan = self.make_fplan("Anderer FPlan-Testplan", self.gemeinde)
        beteiligung = self.make_fplan_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "fplanbeteiligung-update",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_foreign_user_cannot_delete_relation(self):
        """Prüft, dass ein fremder Benutzer eine Relation nicht löschen kann."""
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "fplanbeteiligung-delete",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            FPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_relation_delete_cannot_cross_plan_boundary(self):
        """Prüft, dass beim Löschen einer Relation kein Objekt aus einem anderen FPlan
        über eine manipulierte URL erreicht wird.
        """
        other_plan = self.make_fplan("Anderer FPlan-Testplan", self.gemeinde)
        beteiligung = self.make_fplan_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "fplanbeteiligung-delete",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_foreign_user_cannot_create_attachment_via_direct_post(self):
        """Prüft den Berechtigungsschutz beim direkten POST zum Anlegen eines FPlan-Anhangs."""
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "fplanattachment-create",
                kwargs={"planid": self.FPLAN_PK},
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_attachment_update_cannot_cross_plan_boundary(self):
        """Prüft, dass ein Anhang aus einem anderen FPlan nicht über eine fremde Plan-ID
        bearbeitet werden kann.
        """
        other_plan = self.make_fplan("Anderer FPlan-Attachment-Plan", self.gemeinde)
        attachment = FPlanSpezExterneReferenz.objects.create(
            fplan=other_plan,
            name="Fremde Referenz",
            typ=FPlanSpezExterneReferenz.BESCHREIBUNG,
        )
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "fplanattachment-update",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": attachment.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_attachment_delete_cannot_cross_plan_boundary(self):
        """Prüft, dass ein Anhang aus einem anderen FPlan nicht über eine fremde Plan-ID
        gelöscht werden kann.
        """
        other_plan = self.make_fplan("Anderer FPlan-Attachment-Delete-Plan", self.gemeinde)
        attachment = FPlanSpezExterneReferenz.objects.create(
            fplan=other_plan,
            name="Fremde Referenz",
            typ=FPlanSpezExterneReferenz.BESCHREIBUNG,
        )
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "fplanattachment-delete",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": attachment.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanSpezExterneReferenz.objects.filter(pk=attachment.pk).exists()
        )

    def test_admin_of_only_one_plan_gemeinde_cannot_delete_relation(self):
        """Prüft, dass das Löschen einer generischen XPlan-Relation die Adminrechte für
        alle Plan-Gemeinden erfordert.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Gemeinde (FPlan)", 1106)
        self.fplan.gemeinde.add(zweite_gemeinde)
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "fplanbeteiligung-delete",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            FPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )

    def test_admin_of_all_plan_gemeinden_can_delete_relation(self):
        """Prüft, dass die Relation gelöscht werden darf, wenn der Benutzer in allen
        Plan-Gemeinden Administrator ist.
        """
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde (FPlan)", 1107)
        self.fplan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "fplanbeteiligung-delete",
                kwargs={
                    "planid": self.FPLAN_PK,
                    "pk": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FPlanBeteiligung.objects.filter(pk=beteiligung.pk).exists()
        )
