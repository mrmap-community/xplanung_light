from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanBeteiligung, 
    FPlanBeteiligung, 
    BPlanBeteiligungBeitrag, 
    FPlanBeteiligungBeitrag,
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class BeteiligungBeitragListViewTests(TestCase):

    def setUp(self):
        # 1. Gemeinsame Dummy-Geometrie und Datumsfelder
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # 2. Erstelle zwei getrennte Gemeinden (Organisationen)
        self.gemeinde_a = AdministrativeOrganization.objects.create(name="Gemeinde A")
        self.gemeinde_b = AdministrativeOrganization.objects.create(name="Gemeinde B")

        # 3. Erstelle Test-Nutzer
        self.admin_user_a = User.objects.create_user(username="admin_a", password="password123")
        self.normal_user = User.objects.create_user(username="normalo", password="password123")

        # Zuweisung: admin_user_a ist Admin für Gemeinde A
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a,
            user=self.admin_user_a,
            is_admin=True
        )

        # 4. Setup für Bebauungspläne (BPlan) in Gemeinde A
        self.bplan = BPlan.objects.create(name="BPlan Gemeinde A", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.gemeinde_a)
        
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        
        # Ein Testbeitrag für die BPlan-Liste
        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="Lärmschutzbeschwerde",
            beschreibung="Viel zu laut hier.",
            eingangsdatum=heute,
            typ=1000
        )

        # 5. Setup für Flächennutzungspläne (FPlan) in Gemeinde A
        self.fplan = FPlan.objects.create(name="FPlan Gemeinde A", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.gemeinde_a)
        
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        
        # KORREKTUR: Zuweisung über 'fplan_beteiligung' statt des fehlerhaften 'fplan' Keywords
        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="Grünflächenerhalt",
            beschreibung="Mehr Bäume bitte.",
            eingangsdatum=heute,
            typ=1000
        )

    def test_bplan_list_view_allowed_for_gemeinde_admin(self):
        """Ein Admin von Gemeinde A darf die Beiträge des BPlans von Gemeinde A einsehen."""
        self.client.login(username="admin_a", password="password123")
        
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lärmschutzbeschwerde")

    def test_fplan_list_view_allowed_for_gemeinde_admin(self):
        """Ein Admin von Gemeinde A darf die Beiträge des FPlans von Gemeinde A einsehen."""
        self.client.login(username="admin_a", password="password123")
        
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "fplan",
            "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Grünflächenerhalt")

    def test_bplan_list_view_denied_for_unauthorized_user(self):
        """Ein Nutzer ohne Adminrechte für die Gemeinde wird mit 403 abgewiesen."""
        self.client.login(username="normalo", password="password123")
        
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_fplan_list_view_denied_for_unauthorized_user(self):
        """Ein Nutzer ohne Adminrechte wird auch beim FPlan mit 403 blockiert."""
        self.client.login(username="normalo", password="password123")
        
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "fplan",
            "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

