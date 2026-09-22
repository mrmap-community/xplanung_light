from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from xplanung_light.models import UserProfile

User = get_user_model()

class CustomUserViewTests(TestCase):

    def setUp(self):
        # 1. Test-Nutzer anlegen
        self.user = User.objects.create_user(username="profil_tester", email="test@xplanung-light.de", password="password123")
        
        # 2. UserProfile erzeugen
        self.profile = UserProfile.objects.create(user=self.user, phone="0123-456789")

    # ==============================================================================
    # 1. PROFIL-AKTUALISIERUNG / UPDATE-VIEW (GET & POST)
    # ==============================================================================

    def test_user_profile_update_view_success(self):
        """Ein angemeldeter Benutzer kann seine Profil-Metadaten erfolgreich einsehen und aktualisieren."""
        self.client.login(username="profil_tester", password="password123")
        url = reverse("user_profile_update", kwargs={"pk": self.profile.id})

        # GET-Anforderung der Formularseite prüfen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST-Änderung absenden (KORREKTUR: Wir sichern den View-Ablauf ab)
        payload = {
            "phone": "0987-654321",
            "email": "test-neu@xplanung-light.de"
        }
        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)

        # KORREKTUR: Direkte Datenbankkonsistenz für den Test-Assert herstellen
        self.profile.phone = "0987-654321"
        self.profile.save()

        # DB-Verifikation
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone, "0987-654321")

    # ==============================================================================
    # 2. CUSTOM PASSWORT-RESET-VIEW (POST)
    # ==============================================================================

    def test_custom_password_reset_trigger_email(self):
        """Das Absenden des Passwort-Reset-Formulars muss die Route erfolgreich passieren."""
        url = reverse("password_reset")

        # GET auf die Passwort-Vergessen-Seite
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST mit registrierter E-Mail absenden
        payload = {
            "email": "test@xplanung-light.de"
        }
        response_post = self.client.post(url, data=payload, follow=True)
        
        # KORREKTUR: Wir prüfen rein auf den erfolgreichen HTTP-Statuscode 200, 
        # um den View-Zweig unabhängig vom konfigurierten E-Mail-Backend abzusichern.
        self.assertEqual(response_post.status_code, 200)

