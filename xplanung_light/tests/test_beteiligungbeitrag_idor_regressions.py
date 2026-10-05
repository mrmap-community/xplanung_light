"""
Regressionstests für die Konsistenz der IDs in den URLs der Beitrags-Views (Schutz gegen
unsichere direkte Objektverweise, IDOR).

Die Tests mischen absichtlich IDs aus verschiedenen Plänen und Beteiligungen. Ein Objekt darf
nie allein deshalb gefunden werden, weil es die Primärschlüssel-ID gibt.
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
    """
    IDs von Plan, Beteiligung und Beitrag in der URL müssen zusammenpassen.

    Ausgangslage: eine Gemeinde mit Administrator, zwei BPläne (A und B), je mit Beteiligung und
    Beitrag, sowie zwei FPläne mit Beteiligungen und einem Beitrag. Der Administrator ist
    angemeldet und hat an sich Zugriff auf alles; jede Anfrage unten scheitert deshalb nur an
    der falschen Kombination der IDs.
    """

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
        """
        Was wird geprüft:
            Beitragsliste mit Plan A in der URL, aber der ID der Beteiligung von Plan B.

        Warum:
            Eine gültige Beteiligungs-ID muss zum Plan in der URL gehören.

        Erwartung:
            Status 404.
        """
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
        """
        Was wird geprüft:
            Dieselbe Prüfung für FPläne.

        Warum:
            Die Regel gilt für beide Plantypen.

        Erwartung:
            Status 404.
        """
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
        """
        Was wird geprüft:
            Bearbeiten eines Beitrags von Plan B über eine URL mit Plan A.

        Warum:
            Die Beteiligung gehört zu Plan B, die URL behauptet Plan A.

        Erwartung:
            Status 404.
        """
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
        """
        Was wird geprüft:
            Bearbeiten mit passender Beteiligung A in der URL, aber der ID eines Beitrags
            aus Beteiligung B.

        Warum:
            Der Beitrag allein darf den Filter auf die Beteiligung nicht umgehen.

        Erwartung:
            Status 404.
        """
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
        """
        Was wird geprüft:
            FPlan-Variante: Beitrag von Beteiligung A, aber die URL nennt Beteiligung B.

        Warum:
            Auch für FPläne müssen Beitrag und Beteiligung zusammenpassen.

        Erwartung:
            Status 404.
        """
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
