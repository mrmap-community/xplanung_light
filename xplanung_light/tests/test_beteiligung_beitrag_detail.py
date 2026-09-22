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

class BeteiligungBeitragDetailViewTests(TestCase):

    def setUp(self):
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # Organisation und Nutzer anlegen
        self.gemeinde_a = AdministrativeOrganization.objects.create(name="Gemeinde A")
        self.admin_user = User.objects.create_user(username="admin_detail", password="password123")
        self.stranger_user = User.objects.create_user(username="unbefugt", password="password123")

        # Admin-Rechte zuweisen
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a,
            user=self.admin_user,
            is_admin=True
        )

        # --- BPLAN PIPELINE ---
        self.bplan = BPlan.objects.create(name="BPlan Detailplan", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.gemeinde_a)
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        self.bplan_token = uuid.uuid4()
        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="BPlan Geheimbeschwerde",
            beschreibung="Darf nicht jeder sehen.",
            generic_id=self.bplan_token,
            eingangsdatum=heute,
            typ=1000
        )

        # --- FPLAN PIPELINE ---
        self.fplan = FPlan.objects.create(name="FPlan Detailplan", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.gemeinde_a)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        self.fplan_token = uuid.uuid4()
        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="FPlan Geheimbeschwerde",
            beschreibung="Darf auch nicht jeder sehen.",
            generic_id=self.fplan_token,
            eingangsdatum=heute,
            typ=1000
        )

    # ==============================================================================
    # 1. PFAD: GEMEINDE-ADMINS (HTTP 200)
    # ==============================================================================

    def test_bplan_detail_view_allowed_for_gemeinde_admin(self):
        """Ein zuständiger Gemeinde-Admin kann die BPlan-Beitragsdetails einsehen."""
        self.client.login(username="admin_detail", password="password123")
        
        # KORREKTUR: beteiligungid hinzugefügt, um dem echten URL-Pattern zu entsprechen
        url = reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "bplan", 
            "planid": self.bplan.id, 
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BPlan Geheimbeschwerde")

    def test_fplan_detail_view_allowed_for_gemeinde_admin(self):
        """Ein zuständiger Gemeinde-Admin kann die FPlan-Beitragsdetails einsehen."""
        self.client.login(username="admin_detail", password="password123")
        
        # KORREKTUR: beteiligungid hinzugefügt, um dem echten URL-Pattern zu entsprechen
        url = reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "fplan", 
            "planid": self.fplan.id, 
            "beteiligungid": self.fplan_beteiligung.id,
            "pk": self.fplan_beitrag.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FPlan Geheimbeschwerde")

    # ==============================================================================
    # 2. PFAD: SESSION-BYPASS FÜR ERSTELLER (HTTP 200)
    # ==============================================================================

    def test_detail_view_allowed_via_session_token_for_anonymous_creator(self):
        """Der Ersteller kann anonym zuschauen, wenn seine Session die richtige generic_id hält."""
        # KORREKTUR: beteiligungid hinzugefügt
        url = reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "bplan", 
            "planid": self.bplan.id, 
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BPlan Geheimbeschwerde")

    # ==============================================================================
    # 3. PFAD: AUSSCHLUSS UNBEFUGTER (HTTP 404)
    # ==============================================================================

    def test_detail_view_returns_404_for_unauthorized_user(self):
        """Ein unbefugter Nutzer (kein Admin, kein Session-Token) läuft auf einen 404-Fehler."""
        self.client.login(username="unbefugt", password="password123")
        # KORREKTUR: beteiligungid hinzugefügt
        url = reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "bplan", 
            "planid": self.bplan.id, 
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

