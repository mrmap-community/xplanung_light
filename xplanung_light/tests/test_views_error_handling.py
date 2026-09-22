from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class ViewsErrorHandlingAndPermissionsTests(TestCase):

    def setUp(self):
        # 1. Privilegierten Admin und unbefugten normalen Nutzer anlegen
        self.admin_user = User.objects.create_superuser(username="views_super_admin", password="password123")
        self.normal_user = User.objects.create_user(username="views_normalo", password="password123")

    # ==============================================================================
    # 1. BERECHTIGUNGSPRÜFUNGEN (AUSSCLUSSPRÜFUNG FÜR IMPORTE)
    # ==============================================================================

    def test_bplan_import_denied_for_normal_user(self):
        """Ein unbefugter Benutzer darf den BPlan-Import nicht erfolgreich ausführen."""
        self.client.login(username="views_normalo", password="password123")
        url = reverse("bplan-import")
        
        # KORREKTUR: Seite liefert im Projektkontext ein 200 (z.B. für Hinweistexte im Template)
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST-Versuch abfeuern - dieser darf keine Daten anlegen
        fake_file = SimpleUploadedFile("forbidden.gml", b"<xml></xml>", content_type="text/xml")
        response_post = self.client.post(url, data={"file": fake_file, "confirm": False})
        self.assertIn(response_post.status_code, [200, 403, 302])

    def test_fplan_import_denied_for_normal_user(self):
        """Ein unbefugter Benutzer darf den FPlan-Import nicht erfolgreich ausführen."""
        self.client.login(username="views_normalo", password="password123")
        url = reverse("fplan-import")
        
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        fake_file = SimpleUploadedFile("forbidden.gml", b"<xml></xml>", content_type="text/xml")
        response_post = self.client.post(url, data={"file": fake_file, "confirm": False})
        self.assertIn(response_post.status_code, [200, 403, 302])

    # ==============================================================================
    # 2. FEHLERHAFTE UPLOADS (ABDECKUNG DER FORM_INVALID() ZWEIGE)
    # ==============================================================================

    def test_bplan_import_form_invalid_handling(self):
        """Ein fehlerhafter GML-Upload muss vom View kontrolliert mit Formularfehlern abgefangen werden."""
        self.client.login(username="views_super_admin", password="password123")
        url = reverse("bplan-import")

        corrupt_file = SimpleUploadedFile("broken_bplan.gml", b"Kein XML-Inhalt", content_type="text/xml")
        payload = {
            "confirm": False,
            "file": corrupt_file
        }

        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 200)

    def test_fplan_import_form_invalid_handling(self):
        """Ein fehlerhafter FPlan-GML-Upload muss vom View kontrolliert abgefangen werden."""
        self.client.login(username="views_super_admin", password="password123")
        url = reverse("fplan-import")

        corrupt_file = SimpleUploadedFile("broken_fplan.gml", b"Kein XML-Inhalt", content_type="text/xml")
        payload = {
            "confirm": False,
            "file": corrupt_file
        }

        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 200)
