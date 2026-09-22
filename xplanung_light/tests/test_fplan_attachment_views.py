from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from xplanung_light.models import FPlan, FPlanSpezExterneReferenz, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class FPlanSpezExterneReferenzViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie für FPlan
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        # 2. Organisation & Gemeinde-Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda FPlan", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="orga_admin_fplan", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. FPlan anlegen und der Orga zuweisen
        self.fplan = FPlan.objects.create(name="FPlan Gesamtfortschreibung", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)

        # 4. Eine bestehende Test-Anlage (z.B. ein Erläuterungsbericht im PDF-Format) in der DB anlegen
        dummy_pdf = SimpleUploadedFile("erlaeuterung.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")
        self.attachment = FPlanSpezExterneReferenz.objects.create(
            fplan=self.fplan,
            name="Erläuterungsbericht",
            typ="1080",  # 'Erlaeuterung' laut REF_TYPE_CHOICES in models.py
            public=True,
            attachment=dummy_pdf
        )

    # ==============================================================================
    # 1. ANLAGEN-LISTE (GET)
    # ==============================================================================

    def test_fplan_attachment_list_view_accessible(self):
        """Ein verifizierter Gemeinde-Admin kann die Anlagenliste des FPlans aufrufen."""
        self.client.login(username="orga_admin_fplan", password="password123")
        url = reverse("fplanattachment-list", kwargs={"planid": self.fplan.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Erläuterungsbericht")

    # ==============================================================================
    # 2. ANLAGE HOCHLADEN / CREATE (POST)
    # ==============================================================================

    def test_fplan_attachment_create_success(self):
        """Das Hochladen einer neuen Textanlage (z.B. Begründungsentwurf) muss erfolgreich durchgehen."""
        self.client.login(username="orga_admin_fplan", password="password123")
        url = reverse("fplanattachment-create", kwargs={"planid": self.fplan.id})

        dummy_text_file = SimpleUploadedFile("begruendung.txt", b"FPlan Begruendung...", content_type="text/plain")

        payload = {
            "public": True,
            "typ": "1010",  # 'Begruendung' laut REF_TYPE_CHOICES in models.py
            "name": "Begründungsentwurf FPlan",
            "attachment": dummy_text_file
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # DB-Verifikation
        self.assertTrue(FPlanSpezExterneReferenz.objects.filter(fplan=self.fplan, name="Begründungsentwurf FPlan").exists())

    # ==============================================================================
    # 3. ANLAGE AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_fplan_attachment_update_success(self):
        """Metadaten einer bestehenden FPlan-Anlage können modifiziert werden."""
        self.client.login(username="orga_admin_fplan", password="password123")
        url = reverse("fplanattachment-update", kwargs={"planid": self.fplan.id, "pk": self.attachment.id})

        new_file = SimpleUploadedFile("erlaeuterung_v2.pdf", b"%PDF-1.4 updated fplan", content_type="application/pdf")

        payload = {
            "public": False,  # Schalte Sichtbarkeit auf privat um
            "typ": "1080",
            "name": "Erläuterungsbericht (Finale Fassung)",  # Neuer Name
            "attachment": new_file
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Refresh und DB-Check
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.name, "Erläuterungsbericht (Finale Fassung)")
        self.assertFalse(self.attachment.public)

    # ==============================================================================
    # 4. ANLAGE ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_fplan_attachment_delete_success(self):
        """Ein Admin kann eine zugeordnete Anlage erfolgreich aus dem FPlan entfernen."""
        self.client.login(username="orga_admin_fplan", password="password123")
        url = reverse("fplanattachment-delete", kwargs={"planid": self.fplan.id, "pk": self.attachment.id})

        # GET-Bestätigungsseite abrufen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST-Löschauftrag ausführen
        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz darf nicht mehr existieren
        self.assertFalse(FPlanSpezExterneReferenz.objects.filter(id=self.attachment.id).exists())
