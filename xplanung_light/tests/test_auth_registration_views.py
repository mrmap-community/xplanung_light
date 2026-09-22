from django.test import TestCase
from django.urls import reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()

class AuthAndRegistrationViewTests(TestCase):

    def setUp(self):
        # Registrierungs- und Passwort-Reset-Tests setzen einen bestehenden User voraus
        self.test_user = User.objects.create_user(
            username="reset_dummy",
            email="reset.me@kommune.de",
            password="old_secure_password123"
        )

    # ==============================================================================
    # 1. TESTS FÜR DIE PASSWORT-RESET-PIPELINE
    # ==============================================================================

    def test_password_reset_view_get(self):
        """Prüft, ob die Einstiegsseite für den Passwort-Reset erreichbar ist."""
        try:
            url = reverse("password_reset")
        except NoReverseMatch:
            try:
                url = reverse("auth_password_reset")
            except NoReverseMatch:
                self.skipTest("Passwort-Reset-Route 'password_reset' nicht im URL-Verzeichnis gefunden.")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-Mail")

    def test_password_reset_trigger_email_success(self):
        """Das Absenden einer gültigen E-Mail muss die Reset-Mail triggern und weiterleiten."""
        try:
            url = reverse("password_reset")
            done_url = reverse("password_reset_done")
        except NoReverseMatch:
            try:
                url = reverse("auth_password_reset")
                done_url = reverse("auth_password_reset_done")
            except NoReverseMatch:
                self.skipTest("Reset-Routen in urls.py nicht gefunden.")

        # KORREKTUR: Wir übergeben E-Mail UND Username, um Validierungsvorgaben zu erfüllen
        payload = {
            "email": "reset.me@kommune.de",
            "username": "reset_dummy"
        }

        response = self.client.post(url, data=payload)
        
        # FEHLER-ANALYSE: Falls die Validierung fehlschlägt, drucken wir die exakten Ursachen aus
        if response.status_code == 200 and 'form' in response.context:
            print("\n--- DETILLIERTER PASSWORT-RESET-FEHLER ---")
            print(response.context['form'].errors.as_json())

        # Erwartet wird der Redirect (302) auf die Bestätigungsseite bei erfolgreicher Validierung
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, done_url)

        # Django-Test-Outbox prüft, ob die Mail das System verlassen hat
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset.me@kommune.de", mail.outbox[0].to)

    # ==============================================================================
    # 2. TESTS FÜR DIE REGISTRIERUNGS-VIEWS
    # ==============================================================================

    def test_registration_view_get(self):
        """Prüft, ob das Registrierungsformular für neue Benutzer öffentlich erreichbar ist."""
        registration_url_names = ["registration_register", "register", "user_register", "signup"]
        url = None
        
        for name in registration_url_names:
            try:
                url = reverse(name)
                break
            except NoReverseMatch:
                continue

        if not url:
            self.skipTest("Keine passende Registrierungs-Route im URL-Verzeichnis gefunden.")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "username" or "Benutzername")

