from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from xplanung_light.models import AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class OrganizationUserFormViewTests(TestCase):

    def setUp(self):
        # 1. Test-Kommune anlegen
        self.orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Schilda", ls="07", ks="111", gs="000"
        )

        # 2. Test-Nutzer anlegen
        self.superuser = User.objects.create_superuser(username="master_admin", password="password123")
        self.orga_admin = User.objects.create_user(username="local_admin", password="password123")
        self.user_to_promote = User.objects.create_user(username="sachbearbeiter_neu", password="password123")

        # 3. local_admin zum echten Admin für die Orga machen (wird für Rechteprüfungen in FormView benötigt)
        AdminOrgaUser.objects.create(
            organization=self.orga,
            user=self.orga_admin,
            is_admin=True
        )

    # ==============================================================================
    # 1. TEST FÜR OrganizationUserFormViewAdmin (Zuweisung Gemeinde-Admins)
    # ==============================================================================

    def test_manage_organization_users_admin_get_and_post(self):
        """Ein Superuser darf die Admin-Zuweisung aufrufen und neue Admins deklarieren."""
        self.client.login(username="master_admin", password="password123")
        url = reverse("manage-organization-users-admin")

        # GET-Formularseite prüfen
        response_get = self.client.get(url, {"organization": self.orga.id})
        self.assertEqual(response_get.status_code, 200)

        # POST-Änderung absenden (user_to_promote wird zum Admin ernannt)
        payload = {
            "organization": self.orga.id,
            "admins": [self.user_to_promote.id]
        }
        response_post = self.client.post(url, data=payload)
        
        # Erwartet wird ein Redirect (302) oder ein erfolgreiches Neuladen der Seite (200)
        self.assertIn(response_post.status_code, [200, 302])
        
        # DB-Verifikation: Die Zuweisung muss existieren
        self.assertTrue(
            AdminOrgaUser.objects.filter(organization=self.orga, user=self.user_to_promote, is_admin=True).exists()
        )

    # ==============================================================================
    # 2. TEST FÜR OrganizationUserFormViewToebReporter (Zuweisung TÖB-Reporter)
    # ==============================================================================

    def test_manage_organization_users_toeb_reporter_get_and_post(self):
        """Ein zuständiger Orga-Admin darf TÖB-Reporter für seine Kommune verwalten."""
        self.client.login(username="local_admin", password="password123")
        url = reverse("manage-organization-users-toeb-reporter")

        # GET-Anforderung mitsamt der aktiven Orga im Query-String
        response_get = self.client.get(url, {"organization": self.orga.id})
        self.assertEqual(response_get.status_code, 200)

        # POST-Änderung absenden (user_to_promote wird zum TOEB-Reporter ernannt)
        payload = {
            "organization": self.orga.id,
            "toeb_reporter": [self.user_to_promote.id]
        }
        response_post = self.client.post(url, data=payload)
        self.assertIn(response_post.status_code, [200, 302])
        
        # DB-Verifikation
        self.assertTrue(
            AdminOrgaUser.objects.filter(organization=self.orga, user=self.user_to_promote, is_toeb_reporter=True).exists()
        )

    # ==============================================================================
    # 3. TEST FÜR UserOrganizationFormViewRoles (Rollen-Übersichts-View)
    # ==============================================================================

    def test_users_organization_roles_get_accessible(self):
        """Prüft, ob der Rollen-Zuweisungs-View für den Admin erreichbar ist."""
        self.client.login(username="master_admin", password="password123")
        url = reverse("users-organization-roles")

        response = self.client.get(url, {"user": self.user_to_promote.id})
        self.assertEqual(response.status_code, 200)
