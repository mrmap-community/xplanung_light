from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from xplanung_light.models import BPlan, BPlanSpezExterneReferenz, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class BPlanSpezExterneReferenzViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie für BPlan
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        # 2. Organisation & Gemeinde-Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan anlegen und der Orga zuweisen
        self.bplan = BPlan.objects.create(name="BPlan Industriegebiet Ost", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)

        # 4. Eine bestehende Test-Anlage (z.B. eine Begründung im PDF-Format) in der DB anlegen
        dummy_pdf = SimpleUploadedFile("begruendung.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")
        self.attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=self.bplan,
            name="Offizielle Begründung",
            typ="1010",  # 'Begruendung' laut REF_TYPE_CHOICES in models.py
            public=True,
            attachment=dummy_pdf
        )

    # ==============================================================================
    # 1. ANLAGEN-LISTE (GET)
    # ==============================================================================

    def test_bplan_attachment_list_view_accessible(self):
        """Ein verifizierter Gemeinde-Admin kann die Anlagenliste des BPlans aufrufen."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("bplanattachment-list", kwargs={"planid": self.bplan.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Offizielle Begründung")

    # ==============================================================================
    # 2. ANLAGE HOCHLADEN / CREATE (POST)
    # ==============================================================================

    def test_bplan_attachment_create_success(self):
        """Das Hochladen einer neuen Textanlage (z.B. Satzungstext) muss erfolgreich durchgehen."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("bplanattachment-create", kwargs={"planid": self.bplan.id})

        # Wir simulieren den Upload eines Textdokuments
        dummy_text_file = SimpleUploadedFile("satzung.txt", b"Satzungsinhalt...", content_type="text/plain")

        payload = {
            "public": True,
            "typ": "1060",  # 'Satzung' laut REF_TYPE_CHOICES in models.py
            "name": "Textliche Festsetzungen",
            "attachment": dummy_text_file
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # DB-Verifikation
        self.assertTrue(BPlanSpezExterneReferenz.objects.filter(bplan=self.bplan, name="Textliche Festsetzungen").exists())

    # ==============================================================================
    # 3. ANLAGE AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_bplan_attachment_update_success(self):
        """Metadaten einer bestehenden Anlage (z.B. Name) können modifiziert werden."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("bplanattachment-update", kwargs={"planid": self.bplan.id, "pk": self.attachment.id})

        # Zum Ändern des Namens schicken wir ein neues Dummy-File mit
        new_file = SimpleUploadedFile("begruendung_v2.pdf", b"%PDF-1.4 updated", content_type="application/pdf")

        payload = {
            "public": False,  # Schalte Sichtbarkeit auf privat um
            "typ": "1010",
            "name": "Offizielle Begründung (Fassung 2026)",  # Neuer Name
            "attachment": new_file
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Refresh und DB-Check
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.name, "Offizielle Begründung (Fassung 2026)")
        self.assertFalse(self.attachment.public)

    # ==============================================================================
    # 4. ANLAGE ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_bplan_attachment_delete_success(self):
        """Ein Admin kann eine zugeordnete Anlage erfolgreich aus dem BPlan entfernen."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("bplanattachment-delete", kwargs={"planid": self.bplan.id, "pk": self.attachment.id})

        # GET-Bestätigungsseite abrufen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST-Löschauftrag ausführen
        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz darf nicht mehr existieren
        self.assertFalse(BPlanSpezExterneReferenz.objects.filter(id=self.attachment.id).exists())
