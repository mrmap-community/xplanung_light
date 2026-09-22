import json
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

class BeteiligungBeitragListPdfViewTests(TestCase):

    def setUp(self):
        # 1. Gemeinsame Dummy-Geometrie und Datumsfelder
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # Minimale, valide TipTap-JSON-Struktur für den Pydantic-Parser
        self.tiptap_beschreibung = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Textinhalt des Einwands."
                        }
                    ]
                }
            ]
        }

        # 2. Erstelle Organisation (Kommune) und Test-Nutzer
        self.gemeinde_a = AdministrativeOrganization.objects.create(name="Gemeinde A")
        
        self.admin_user_a = User.objects.create_user(username="admin_pdf", password="password123")
        self.normal_user = User.objects.create_user(username="normalo_pdf", password="password123")

        # admin_user_a ist Admin für Gemeinde A
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a,
            user=self.admin_user_a,
            is_admin=True
        )

        # 3. Setup für BPlan + Beteiligung + Beitrag
        self.bplan = BPlan.objects.create(name="BPlan PDF-Test", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.gemeinde_a)
        
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="BPlan Einwand",
            beschreibung=self.tiptap_beschreibung,
            eingangsdatum=heute,
            typ=1000
        )

        # 4. Setup für FPlan + Beteiligung + Beitrag
        self.fplan = FPlan.objects.create(name="FPlan PDF-Test", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.gemeinde_a)
        
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="FPlan Einwand",
            beschreibung=self.tiptap_beschreibung,
            eingangsdatum=heute,
            typ=1000
        )

    # ==============================================================================
    # 1. ERFOLGSFÄLLE FÜR GEMEINDE-ADMINS
    # ==============================================================================

    def test_bplan_pdf_export_success_for_admin(self):
        """Ein Admin darf den PDF-Export des BPlans aufrufen und erhält eine PDF-Datei."""
        self.client.login(username="admin_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # KORREKTUR: streaming_content Chunks zu einem flachen Binärstrom zusammenfügen
        binary_content = b"".join(response.streaming_content)
        self.assertTrue(binary_content.startswith(b'%PDF'))

    def test_fplan_pdf_export_success_for_admin(self):
        """Ein Admin darf den PDF-Export des FPlans aufrufen und erhält eine PDF-Datei."""
        self.client.login(username="admin_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "fplan",
            "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # KORREKTUR: streaming_content Chunks zusammenfügen
        binary_content = b"".join(response.streaming_content)
        self.assertTrue(binary_content.startswith(b'%PDF'))

    # ==============================================================================
    # 2. AUSSCHLUSS UNBEFUGTER USER
    # ==============================================================================

    def test_pdf_export_denied_for_unauthorized_user(self):
        """Ein Nutzer ohne Adminrechte wird beim Aufruf des PDF-Exports mit HTTP 403 blockiert."""
        self.client.login(username="normalo_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


