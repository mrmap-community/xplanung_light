"""
Grenzfälle der Rechteprüfung bei TÖB-Stellungnahmen: Reporter einer anderen Organisation und
URLs mit nicht zusammenpassenden Plänen und Beteiligungen.
"""

import copy
import datetime
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    ToebUnit,
)


class BeteiligungBeitragToebAuthorizationBoundaries(TestCase):
    """
    Ein TÖB-Reporter darf nur für seine eigene Organisation handeln, und die URL-IDs müssen
    zusammenpassen.

    Ausgangslage: Fixtures für Nutzer, Organisationen und einen BPlan. Dazu eine fremde
    Organisation mit eigenem Plan. Reporter A gehört zur Gemeinde (Einheit TÖB A), Reporter B
    zur fremden Organisation (Einheit TÖB B). Es gibt eine Beteiligung zu jedem Plan und einen
    freigeschalteten Beitrag der Einheit TÖB B an der Beteiligung der Gemeinde.
    """

    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "admin_orga_user.json",
    ]

    PLAN_PK = 4318
    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        # Create a second valid BPlan so the wrong-parent test really tests
        # a participation whose parent plan differs from the URL's planid.
        cls.foreign_plan = copy.copy(cls.plan)
        cls.foreign_plan.pk = None
        cls.foreign_plan.id = None
        cls.foreign_plan.generic_id = uuid4()
        cls.foreign_plan.name = f"{cls.plan.name} - TÖB Boundary Foreign Plan"
        cls.foreign_plan.save()
        cls.foreign_orga = AdministrativeOrganization.objects.create(
            name="TÖB Boundary Foreign Organization",
            type=AdministrativeOrganization.COM,
            ls="07", ks="998", gs="998",
        )
        cls.reporter_a = User.objects.create_user(
            username="toeb_boundary_reporter_a", password="irrelevant", email="a@example.org"
        )
        cls.reporter_b = User.objects.create_user(
            username="toeb_boundary_reporter_b", password="irrelevant", email="b@example.org"
        )
        AdminOrgaUser.objects.create(
            organization=cls.gemeinde, user=cls.reporter_a,
            is_admin=False, is_toeb_reporter=True,
        )
        AdminOrgaUser.objects.create(
            organization=cls.foreign_orga, user=cls.reporter_b,
            is_admin=False, is_toeb_reporter=True,
        )
        cls.toeb_a = ToebUnit.objects.create(
            name="TÖB A", email="toeb-a@example.org", organization=cls.gemeinde
        )
        cls.toeb_b = ToebUnit.objects.create(
            name="TÖB B", email="toeb-b@example.org", organization=cls.foreign_orga
        )
        today = datetime.date.today()
        cls.beteiligung_a = BPlanBeteiligung.objects.create(
            bplan=cls.plan,
            bekanntmachung_datum=today - datetime.timedelta(days=7),
            start_datum=today - datetime.timedelta(days=7),
            end_datum=today + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.TOEB,
            allow_online_beitrag=False,
        )
        cls.beteiligung_b = BPlanBeteiligung.objects.create(
            bplan=cls.foreign_plan,
            bekanntmachung_datum=today - datetime.timedelta(days=7),
            start_datum=today - datetime.timedelta(days=7),
            end_datum=today + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.TOEB,
            allow_online_beitrag=False,
        )
        cls.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=cls.beteiligung_a,
            titel="TÖB-Beitrag",
            beschreibung="Beitrag für TÖB B",
            typ=BPlanBeteiligungBeitrag.MAIL,
            email="toeb-b@example.org",
            eingangsdatum=today,
            approved=True,
            toeb=cls.toeb_b,
        )

    def setUp(self):
        self.client = Client()

    def _url(self, name, beteiligungid=None, pk=None, toeb_id=None):
        """
        Baut die URL einer TÖB-Ansicht. Ohne Angabe gelten Plan und Beteiligung der Gemeinde;
        beteiligungid, pk und toeb_id lassen sich überschreiben.
        """
        kwargs = {
            "plantyp": "bplan",
            "planid": self.plan.pk,
            "beteiligungid": beteiligungid or self.beteiligung_a.pk,
        }
        if pk is not None:
            kwargs["pk"] = pk
        if toeb_id is not None:
            kwargs["toeb_id"] = toeb_id
        return reverse(name, kwargs=kwargs)

    def test_update_rejects_reporter_from_another_toeb_organization(self):
        """
        Was wird geprüft:
            Reporter A öffnet das Bearbeiten-Formular für einen Beitrag der Einheit TÖB B.

        Warum:
            Reporter dürfen nur Beiträge ihrer eigenen Einheit ändern.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.reporter_a)
        response = self.client.get(self._url("beteiligungbeitrag-toeb-update", pk=self.beitrag.pk))
        self.assertEqual(response.status_code, 403)

    def test_update_rejects_contribution_when_url_points_to_another_participation(self):
        """
        Was wird geprüft:
            Reporter B ist berechtigt, die URL nennt aber die Beteiligung des fremden Plans,
            während der Beitrag zur Beteiligung der Gemeinde gehört.

        Warum:
            Die Kette Plan, Beteiligung, Beitrag muss in der URL stimmig sein.

        Erwartung:
            Status 404.
        """
        self.client.force_login(self.reporter_b)
        response = self.client.get(self._url(
            "beteiligungbeitrag-toeb-update",
            beteiligungid=self.beteiligung_b.pk, pk=self.beitrag.pk,
        ))
        self.assertEqual(response.status_code, 404)

    def test_delete_rejects_reporter_from_another_toeb_organization(self):
        """
        Was wird geprüft:
            Reporter A öffnet die Löschen-Ansicht eines Beitrags der Einheit TÖB B.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.reporter_a)
        response = self.client.get(self._url("beteiligungbeitrag-toeb-delete", pk=self.beitrag.pk))
        self.assertEqual(response.status_code, 403)

    def test_delete_rejects_contribution_when_url_points_to_another_participation(self):
        """
        Was wird geprüft:
            Löschen-Ansicht mit nicht zusammenpassender Beteiligung in der URL.

        Erwartung:
            Status 404.
        """
        self.client.force_login(self.reporter_b)
        response = self.client.get(self._url(
            "beteiligungbeitrag-toeb-delete",
            beteiligungid=self.beteiligung_b.pk, pk=self.beitrag.pk,
        ))
        self.assertEqual(response.status_code, 404)

    def test_create_rejects_reporter_from_another_toeb_organization(self):
        """
        Was wird geprüft:
            Reporter A will eine Stellungnahme im Namen der Einheit TÖB B anlegen.

        Warum:
            Die Einheit steht in der URL und darf nicht frei wählbar sein.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.reporter_a)
        response = self.client.get(self._url(
            "beteiligungbeitrag-toeb-create", toeb_id=self.toeb_b.pk,
        ))
        self.assertEqual(response.status_code, 403)

    def test_create_rejects_participation_from_wrong_parent_context(self):
        """
        Was wird geprüft:
            Reporter B legt mit seiner eigenen Einheit an, die URL nennt aber die
            Beteiligung des fremden Plans zusammen mit der Plan-ID der Gemeinde.

        Warum:
            Plan und Beteiligung in der URL müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
        self.client.force_login(self.reporter_b)
        response = self.client.get(self._url(
            "beteiligungbeitrag-toeb-create",
            beteiligungid=self.beteiligung_b.pk, toeb_id=self.toeb_b.pk,
        ))
        self.assertEqual(response.status_code, 404)
