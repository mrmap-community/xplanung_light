"""Regression tests for plan/participation/contribution URL consistency.

These tests deliberately mix IDs belonging to different parent objects.  The
view must never resolve an object merely because its primary key exists.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    FPlan,
    FPlanBeteiligung,
    FPlanBeteiligungBeitrag,
)


User = get_user_model()


class BeteiligungBeitragIdorRegressionTests(TestCase):
    """Parent IDs in contribution URLs must be mutually consistent."""

    @classmethod
    def setUpTestData(cls):
        polygon = GEOSGeometry("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))")
        today = timezone.now().date()

        cls.orga = AdministrativeOrganization.objects.create(
            name="IDOR Test Gemeinde",
            ls="07",
            ks="111",
            gs="001",
        )
        cls.admin = User.objects.create_user(
            username="idor_gemeinde_admin",
            password="password123",
        )
        AdminOrgaUser.objects.create(
            organization=cls.orga,
            user=cls.admin,
            is_admin=True,
        )

        cls.plan_a = BPlan.objects.create(
            name="IDOR Plan A",
            geltungsbereich=polygon,
        )
        cls.plan_a.gemeinde.add(cls.orga)
        cls.plan_b = BPlan.objects.create(
            name="IDOR Plan B",
            geltungsbereich=polygon,
        )
        cls.plan_b.gemeinde.add(cls.orga)

        cls.beteiligung_a = BPlanBeteiligung.objects.create(
            bplan=cls.plan_a,
            bekanntmachung_datum=today,
            start_datum=today,
            end_datum=today + timedelta(days=30),
        )
        cls.beteiligung_b = BPlanBeteiligung.objects.create(
            bplan=cls.plan_b,
            bekanntmachung_datum=today,
            start_datum=today,
            end_datum=today + timedelta(days=30),
        )

        cls.beitrag_a = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=cls.beteiligung_a,
            titel="Beitrag A",
            beschreibung="Beitrag des ersten Verfahrens",
            eingangsdatum=today,
            typ=1000,
        )
        cls.beitrag_b = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=cls.beteiligung_b,
            titel="Beitrag B",
            beschreibung="Beitrag des zweiten Verfahrens",
            eingangsdatum=today,
            typ=1000,
        )

        cls.fplan_a = FPlan.objects.create(
            name="IDOR FPlan A",
            geltungsbereich=polygon,
        )
        cls.fplan_a.gemeinde.add(cls.orga)
        cls.fplan_b = FPlan.objects.create(
            name="IDOR FPlan B",
            geltungsbereich=polygon,
        )
        cls.fplan_b.gemeinde.add(cls.orga)
        cls.fplan_beteiligung_a = FPlanBeteiligung.objects.create(
            fplan=cls.fplan_a,
            bekanntmachung_datum=today,
            start_datum=today,
            end_datum=today + timedelta(days=30),
        )
        cls.fplan_beteiligung_b = FPlanBeteiligung.objects.create(
            fplan=cls.fplan_b,
            bekanntmachung_datum=today,
            start_datum=today,
            end_datum=today + timedelta(days=30),
        )
        cls.fplan_beitrag_a = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=cls.fplan_beteiligung_a,
            titel="FPlan Beitrag A",
            beschreibung="FPlan Beitrag des ersten Verfahrens",
            eingangsdatum=today,
            typ=1000,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_bplan_list_rejects_participation_from_another_plan(self):
        """A valid participation ID must belong to the plan in the URL."""
        url = reverse(
            "beteiligungbeitrag-list",
            kwargs={
                "plantyp": "bplan",
                "planid": self.plan_a.pk,
                "beteiligungid": self.beteiligung_b.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_fplan_list_rejects_participation_from_another_plan(self):
        """The same parent-consistency rule applies to FPlan."""
        url = reverse(
            "beteiligungbeitrag-list",
            kwargs={
                "plantyp": "fplan",
                "planid": self.fplan_a.pk,
                "beteiligungid": self.fplan_beteiligung_b.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_generic_update_rejects_participation_from_another_plan(self):
        url = reverse(
            "beteiligungbeitrag-generic-update",
            kwargs={
                "plantyp": "bplan",
                "planid": self.plan_a.pk,
                "beteiligungid": self.beteiligung_b.pk,
                "pk": self.beitrag_b.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_generic_update_rejects_contribution_from_another_participation(self):
        """A contribution PK alone must not bypass the participation filter."""
        url = reverse(
            "beteiligungbeitrag-generic-update",
            kwargs={
                "plantyp": "bplan",
                "planid": self.plan_a.pk,
                "beteiligungid": self.beteiligung_a.pk,
                "pk": self.beitrag_b.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_fplan_generic_update_rejects_contribution_from_another_plan(self):
        url = reverse(
            "beteiligungbeitrag-generic-update",
            kwargs={
                "plantyp": "fplan",
                "planid": self.fplan_a.pk,
                "beteiligungid": self.fplan_beteiligung_b.pk,
                "pk": self.fplan_beitrag_a.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
