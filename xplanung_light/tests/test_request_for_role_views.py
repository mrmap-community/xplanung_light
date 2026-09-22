from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from xplanung_light.models import AdministrativeOrganization, RequestForRole, AdminOrgaUser

User = get_user_model()

class RequestForRoleViewTests(TestCase):

    def setUp(self):
        # 1. Test-Kommune anlegen
        self.orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Schilda", ls="07", ks="111", gs="000"
        )

        # 2. Test-Nutzer anlegen
        self.superuser = User.objects.create_superuser(username="zentral_admin", password="password123")
        self.applicant = User.objects.create_user(username="antragsteller", password="password123")

        # 3. Vorab einen bestehenden Antrag anlegen
        self.pending_request = RequestForRole.objects.create(
            owned_by_user=self.applicant,
            role="OA"  # Organisationsadministrator
        )
        self.pending_request.organizations.add(self.orga)

    # ==============================================================================
    # 1. LIST-VIEWS & ERSTELLUNG (GET/POST)
    # ==============================================================================

    def test_request_for_role_create_and_list_views(self):
        """Prüft das Erstellen eines Antrags und die eigene Antragsliste des Nutzers."""
        self.client.login(username="antragsteller", password="password123")
        
        # Test List-View
        list_url = reverse("requestforrole-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # Test Create-View Formularseite (GET)
        create_url = reverse("requestforrole-create")
        response_get = self.client.get(create_url)
        self.assertEqual(response_get.status_code, 200)

        # Neuen Antrag per POST einreichen
        payload = {
            "role": "TR",  # TÖB-Reporter
            "organizations": [self.orga.id]
        }
        response_post = self.client.post(create_url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        self.assertTrue(RequestForRole.objects.filter(owned_by_user=self.applicant, role="TR").exists())

    def test_request_for_role_admin_list_accessible(self):
        """Der Zentral-Admin muss die globale Antragsliste einsehen können."""
        self.client.login(username="zentral_admin", password="password123")
        url = reverse("requestforrole-admin-list")
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. ANTRAG GENEHMIGEN (CONFIRM)
    # ==============================================================================

    def test_request_for_role_confirm_success(self):
        """Das Bestätigen eines Antrags fügt den User hinzu und entfernt den verarbeiteten Antrag."""
        self.client.login(username="zentral_admin", password="password123")
        url = reverse("requestforrole-confirm", kwargs={"pk": self.pending_request.id})

        # GET auf das Bestätigungsformular
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST zum Bestätigen absenden
        payload = {"editing_note": "Nach telefonischer Rücksprache freigegeben."}
        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)

        # KORREKTUR: Der Antrag wurde systemkonform nach dem Confirm gelöscht
        self.assertFalse(RequestForRole.objects.filter(id=self.pending_request.id).exists())
        
        # Das übergeordnete Ziel muss in der DB stehen: User ist jetzt echter Admin
        self.assertTrue(
            AdminOrgaUser.objects.filter(organization=self.orga, user=self.applicant, is_admin=True).exists()
        )

    # ==============================================================================
    # 3. ANTRAG ABLEHNEN (REFUSE)
    # ==============================================================================

    def test_request_for_role_refuse_success(self):
        """Das Ablehnen entfernt den verarbeiteten Antrag und gewährt keine Rechte."""
        self.client.login(username="zentral_admin", password="password123")
        
        refuse_request = RequestForRole.objects.create(owned_by_user=self.applicant, role="TR")
        refuse_request.organizations.add(self.orga)
        
        url = reverse("requestforrole-refuse", kwargs={"pk": refuse_request.id})

        # POST Ablehnung absenden
        payload = {"editing_note": "Zuständigkeit konnte nicht verifiziert werden."}
        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)

        # KORREKTUR: Der Antrag wurde systemkonform nach dem Refuse gelöscht
        self.assertFalse(RequestForRole.objects.filter(id=refuse_request.id).exists())
        
        # Es darf KEINE TÖB-Reporter-Rolle für den User erzeugt worden sein
        self.assertFalse(
            AdminOrgaUser.objects.filter(organization=self.orga, user=self.applicant, is_toeb_reporter=True).exists()
        )

    # ==============================================================================
    # 4. ANTRAG LÖSCHEN / ZURÜCKZIEHEN
    # ==============================================================================

    def test_request_for_role_delete(self):
        """Ein Antragsteller kann seinen eigenen offenen Antrag löschen/zurückziehen."""
        self.client.login(username="antragsteller", password="password123")
        url = reverse("requestforrole-delete", kwargs={"pk": self.pending_request.id})

        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        self.assertFalse(RequestForRole.objects.filter(id=self.pending_request.id).exists())

