import uuid
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

class BeteiligungBeitragViewsTests(TestCase):

    def setUp(self):
        # 1. Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # 2. Organisationen und User
        self.orga_a = AdministrativeOrganization.objects.create(name="Gemeinde A", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="beitrag_admin", password="password123")
        self.stranger_user = User.objects.create_user(username="fremder_user", password="password123")

        # Admin zuweisen
        AdminOrgaUser.objects.create(organization=self.orga_a, user=self.admin_user, is_admin=True)

        # 3. BPlan Pipeline aufsetzen
        self.bplan = BPlan.objects.create(name="BPlan Nord", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga_a)
        
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        
        self.bplan_token = uuid.uuid4()
        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="Bedenken zum Lärm",
            beschreibung="Viel zu laut.",
            approved=False,
            generic_id=self.bplan_token,
            eingangsdatum=heute,
            typ=1000
        )

        # 4. FPlan Pipeline aufsetzen
        self.fplan = FPlan.objects.create(name="FPlan Süd", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga_a)
        
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        
        self.fplan_token = uuid.uuid4()
        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="Bedenken zur Grünfläche",
            beschreibung="Mehr Bäume.",
            approved=False,
            generic_id=self.fplan_token,
            eingangsdatum=heute,
            typ=1000
        )

    # ==============================================================================
    # 1. TESTS FÜR LIST-VIEW & RECHTEPRÜFUNG
    # ==============================================================================

    def test_bplan_beitrag_list_success_for_admin(self):
        """Ein Gemeinde-Admin kann die Beitragsliste des BPlans einsehen."""
        self.client.login(username="beitrag_admin", password="password123")
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bedenken zum Lärm")

    def test_fplan_beitrag_list_success_for_admin(self):
        """Ein Gemeinde-Admin kann die Beitragsliste des FPlans einsehen."""
        self.client.login(username="beitrag_admin", password="password123")
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "beteiligungid": self.fplan_beteiligung.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bedenken zur Grünfläche")

    def test_beitrag_list_denied_for_stranger(self):
        """Ein unbefugter Benutzer wird mit HTTP 403 (PermissionDenied) blockiert."""
        self.client.login(username="fremder_user", password="password123")
        url = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    # ==============================================================================
    # 2. TESTS FÜR AKTIVIERUNG, RÜCKZUG & VERIFIZIERUNG (FUNCTION-BASED-VIEWS)
    # ==============================================================================

    def test_beitrag_activate_via_email_link(self):
        """Der Klick auf den Aktivierungslink schaltet die anonyme Stellungnahme frei."""
        url = reverse("beteiligungbeitrag-activate", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
            "generic_id": str(self.bplan_token)
        })
        
        # KORREKTUR: Session-Token setzen, um die Inhaber-Prüfung der FBVs zu passieren
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        
        self.bplan_beitrag.refresh_from_db()
        self.assertTrue(self.bplan_beitrag.approved)

    def test_beitrag_withdraw_via_link(self):
        """Der Ersteller kann seinen Beitrag nachträglich als zurückgezogen markieren."""
        url = reverse("beteiligungbeitrag-withdraw", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
            "generic_id": str(self.bplan_token)
        })
        
        # KORREKTUR: Session-Token setzen
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        
        self.bplan_beitrag.refresh_from_db()
        self.assertTrue(self.bplan_beitrag.withdrawn)

    # ==============================================================================
    # 3. TESTS FÜR LÖSCH-ANSICHTEN
    # ==============================================================================

    def test_delete_beitrag_by_admin(self):
        """Ein berechtigter Admin kann einen eingegangenen Beitrag löschen."""
        self.client.login(username="beitrag_admin", password="password123")
        url = reverse("beteiligungbeitrag-delete", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        
        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(id=self.bplan_beitrag.id).exists())


