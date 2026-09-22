from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    BPlanBeteiligung, 
    AdministrativeOrganization, 
    AdminOrgaUser,
    ToebUnit
)

User = get_user_model()

class BeteiligungViewTests(TestCase):

    def setUp(self):
        # 1. Geometrie und Fristen aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisationen anlegen
        self.orga = AdministrativeOrganization.objects.create(
            name="Stadtplanungsamt Schilda", ls="07", ks="111", gs="000", geometry=dummy_polygon
        )

        # 3. User anlegen (Admin und ein TÖB-Reporter)
        self.admin_user = User.objects.create_user(username="beteiligung_admin", password="password123")
        self.reporter_user = User.objects.create_user(username="toeb_user", password="password123")
        
        self.orga_user_entry = AdminOrgaUser.objects.create(
            organization=self.orga, user=self.admin_user, is_admin=True
        )
        self.toeb_reporter_entry = AdminOrgaUser.objects.create(
            organization=self.orga, user=self.reporter_user, is_toeb_reporter=True
        )

        # 4. TÖB-Einheit für den Reporter erzeugen
        self.toeb_unit = ToebUnit.objects.create(
            organization=self.orga, name="Naturschutz-Referat", theme="NSLP", public=True, geometry=dummy_polygon
        )
        self.toeb_unit.editors.add(self.toeb_reporter_entry)

        # 5. BPlan & Beteiligungsverfahren anlegen
        self.bplan = BPlan.objects.create(name="Wohnpark Sonnenwiese", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            typ="1000",  # Öffentliche Auslegung
            bekanntmachung_datum=self.heute,
            start_datum=self.morgen,
            end_datum=self.in_einem_monat,
            allow_online_beitrag=True
        )
        self.beteiligung.assigned_toebs.add(self.toeb_unit)

    # ==============================================================================
    # 1. LISTEN-ANSICHTEN (GET)
    # ==============================================================================

    def test_public_and_internal_beteiligung_lists_accessible(self):
        """Prüft die fehlerfreie Erreichbarkeit der verschiedenen Beteiligungslisten."""
        # 1. Öffentliche Gesamtliste (kein Login erforderlich)
        url_public = reverse("beteiligungen")
        response = self.client.get(url_public)
        self.assertEqual(response.status_code, 200)

        # 2. Organisationsspezifische Liste
        url_orga = reverse("organization-beteiligungen-list", kwargs={"pk": self.orga.id})
        response_orga = self.client.get(url_orga)
        self.assertEqual(response_orga.status_code, 200)

        # 3. TÖB-spezifische Beteiligungsliste (erfordert Login eines TOEB-Reporters)
        self.client.login(username="toeb_user", password="password123")
        url_toeb = reverse("toebbeteiligungen-list")
        response_toeb = self.client.get(url_toeb)
        self.assertEqual(response_toeb.status_code, 200)

    # ==============================================================================
    # 2. DYNAMISCHER PDF-EXPORT (GET STREAM)
    # ==============================================================================

    def test_beteiligung_contributions_pdf_export_success(self):
        """Prüft, ob die PDF-Schnittstelle die Übersicht erfolgreich als Binär-Stream ausgibt."""
        self.client.login(username="beteiligung_admin", password="password123")
        
        # Aufruf des PDF-Links für das Verfahren
        url_pdf = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id
        })
        
        response = self.client.get(url_pdf)
        self.assertEqual(response.status_code, 200)
        
        # Verifiziert, dass der Content-Type im Header auf PDF gesetzt ist
        if response.has_header('Content-Type'):
            self.assertEqual(response['Content-Type'], 'application/pdf')

        # Binär-Inhalt prüfen: Ein valides PDF beginnt immer mit dem magischen Header %PDF
        binary_data = b"".join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertTrue(binary_data.startswith(b'%PDF'))
