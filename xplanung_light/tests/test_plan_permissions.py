from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    BPlanSpezExterneReferenz,
)


class PermissionTestBase(TestCase):
    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "fplan.json",
        "admin_orga_user.json",
    ]

    PLAN_PK = 4318
    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_admin = User.objects.get(username="admin_stadt_neustadt")
        cls.fremder_user = User.objects.create_user(
            username="fremder_user",
            password="nicht-relevant-wegen-force_login",
        )
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)

    def setUp(self):
        self.client = Client()

    @staticmethod
    def make_gemeinde(name, gs):
        return AdministrativeOrganization.objects.create(
            name=name,
            type=AdministrativeOrganization.COM,
            ls="07",
            ks="000",
            gs=str(gs),
        )

    @staticmethod
    def make_admin(user, gemeinde):
        return AdminOrgaUser.objects.create(
            organization=gemeinde,
            user=user,
            is_admin=True,
            is_toeb_reporter=False,
        )

    @staticmethod
    def make_bplan(name, gemeinde):
        fixture_plan = BPlan.objects.get(pk=PermissionTestBase.PLAN_PK)
        plan = BPlan.objects.create(
            name=name,
            nummer="TEST-2",
            planart=BPlan.BPLAN,
            geltungsbereich=fixture_plan.geltungsbereich,
        )
        plan.gemeinde.add(gemeinde)
        return plan

    def plan_update_data(self, plan, gemeinden, *, name=None):
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
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_foreign_user_cannot_update_plan(self):
        self.client.force_login(self.fremder_user)
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_update_plan_via_direct_post(self):
        self.client.force_login(self.fremder_user)
        response = self.client.post(
            reverse("bplan-update", args=[self.PLAN_PK]),
            data={},
        )
        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_open_update_form(self):
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(
            reverse("bplan-update", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_update_plan_without_changing_gemeinden(self):
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
        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_admin_of_only_one_of_two_gemeinden_cannot_delete_plan(self):
        fremde_gemeinde = self.make_gemeinde("Zweite Gemeinde", 994)
        self.plan.gemeinde.add(fremde_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_admin_of_all_gemeinden_can_delete_plan(self):
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde", 995)
        self.plan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse("bplan-delete", args=[self.PLAN_PK])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BPlan.objects.filter(pk=self.PLAN_PK).exists())


class XPlanRelationPermissions(PermissionTestBase):
    """
    Permission-/IDOR-Tests für die generischen XPlanRelationsViews.

    Besonders wichtig:
    - Create muss auch bei direktem POST geprüft werden.
    - Update/Delete dürfen ein Objekt niemals über pk aus einem anderen Plan
      erreichen, wenn planid auf einen anderen Plan zeigt.
    - Delete verlangt Admin-Rechte für alle dem Plan zugewiesenen Gemeinden.
    """

    def make_beteiligung(self, plan):
        return BPlanBeteiligung.objects.create(
            bplan=plan,
            typ=BPlanBeteiligung.TOEB,
            bekanntmachung_datum=date(2026, 1, 1),
            start_datum=date(2026, 1, 2),
            end_datum=date(2026, 1, 31),
            allow_online_beitrag=False,
        )

    def test_foreign_user_cannot_create_relation_via_direct_post(self):
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
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "bplanbeteiligung-create",
                kwargs={"planid": self.PLAN_PK},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_foreign_user_cannot_update_relation(self):
        beteiligung = self.make_beteiligung(self.plan)
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
        beteiligung = self.make_beteiligung(self.plan)
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
        other_plan = self.make_bplan("Anderer Testplan", self.gemeinde)
        beteiligung = self.make_beteiligung(other_plan)
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
        beteiligung = self.make_beteiligung(self.plan)
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
        other_plan = self.make_bplan("Anderer Testplan", self.gemeinde)
        beteiligung = self.make_beteiligung(other_plan)
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
        zweite_gemeinde = self.make_gemeinde("Zweite Gemeinde", 996)
        self.plan.gemeinde.add(zweite_gemeinde)
        beteiligung = self.make_beteiligung(self.plan)
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
        zweite_gemeinde = self.make_gemeinde("Zweite Admin-Gemeinde", 997)
        self.plan.gemeinde.add(zweite_gemeinde)
        self.make_admin(self.gemeinde_admin, zweite_gemeinde)
        beteiligung = self.make_beteiligung(self.plan)
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