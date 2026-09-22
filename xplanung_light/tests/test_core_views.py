from django.test import TestCase
from django.urls import reverse
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanSpezExterneReferenz, 
    FPlanSpezExterneReferenz, 
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class CoreViewsBusinessLogicTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie und Organisation anlegen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        self.orga = AdministrativeOrganization.objects.create(
            name="Zentrales Prüfungsamt",
            ls="07", ks="111", gs="000"
        )
        
        # Admin-Nutzer deklarieren, falls Downloads berechtigungsgeschützt sind
        self.admin_user = User.objects.create_user(username="download_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)
        
        # 2. Testpläne für Statistiken und Anlagen bereitstellen
        self.bplan = BPlan.objects.create(name="BPlan Ost", massstab=1000, geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        
        self.fplan = FPlan.objects.create(name="FPlan West", massstab=2500, geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)

        # 3. Dummy-Dateien erzeugen und an die SpezExterneReferenz-Modelle hängen
        dummy_pdf_bplan = SimpleUploadedFile("bplan_text.pdf", b"%PDF-1.4 bplan raw content", content_type="application/pdf")
        self.bplan_attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=self.bplan,
            name="BPlan Textliche Festsetzung",
            typ="1000",
            public=True,
            attachment=dummy_pdf_bplan
        )

        dummy_pdf_fplan = SimpleUploadedFile("fplan_report.pdf", b"%PDF-1.4 fplan raw content", content_type="application/pdf")
        self.fplan_attachment = FPlanSpezExterneReferenz.objects.create(
            fplan=self.fplan,
            name="FPlan Erläuterungsbericht",
            typ="1080",
            public=True,
            attachment=dummy_pdf_fplan
        )

    # ==============================================================================
    # 1. STATISCHE & STATISTISCHE VIEWS
    # ==============================================================================

    def test_static_info_pages_accessible(self):
        """Prüft die fehlerfreie Erreichbarkeit aller statischen Info- und Rechtstexte-Seiten."""
        static_routes = ["home", "about", "datenschutz", "impressum"]
        for route in static_routes:
            url = reverse(route)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_aggregates_statistics_view_success(self):
        """Der Statistik-View muss erreichbar sein und relationale Berechnungen fehlerfrei ausführen."""
        url = reverse("aggregates")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. ANLAGEN-DOWNLOAD ROUTEN (FILERESPONSE VERARBEITUNG)
    # ==============================================================================

    def test_get_bplan_attachment_download_success(self):
        """Prüft, ob die Download-Route für BPlan-Anlagen die Datei korrekt ausliefert."""
        self.client.login(username="download_admin", password="password123")
        url = reverse("bplanattachment-download", kwargs={"pk": self.bplan_attachment.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verifiziert, dass es sich um eine FileResponse / StreamingResponse handelt
        if response.has_header('Content-Type'):
            self.assertEqual(response['Content-Type'], 'application/pdf')
            
        # Binär-Inhalt prüfen (Chunks zusammenfügen, falls es ein Stream ist)
        binary_data = b"".join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertTrue(binary_data.startswith(b'%PDF'))

    def test_get_fplan_attachment_download_success(self):
        """Prüft, ob die Download-Route für FPlan-Anlagen die Datei korrekt ausliefert."""
        self.client.login(username="download_admin", password="password123")
        url = reverse("fplanattachment-download", kwargs={"pk": self.fplan_attachment.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        if response.has_header('Content-Type'):
            self.assertEqual(response['Content-Type'], 'application/pdf')
            
        binary_data = b"".join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertTrue(binary_data.startswith(b'%PDF'))
