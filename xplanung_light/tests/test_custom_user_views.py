"""Tests der Profil-Bearbeitung und des Passwort-Resets."""

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from xplanung_light.models import UserProfile

User = get_user_model()

class CustomUserViewTests(TestCase):
    """Eigene Nutzer-Views der Anwendung."""

    def setUp(self):
        # 1. Test-Nutzer anlegen
        self.user = User.objects.create_user(username="profil_tester", email="test@xplanung-light.de", password="password123")
        
        # 2. UserProfile erzeugen
        self.profile = UserProfile.objects.create(user=self.user, phone="0123-456789")

    # ==============================================================================
    # 1. PROFIL-AKTUALISIERUNG / UPDATE-VIEW (GET & POST)
    # ==============================================================================

    def test_user_profile_update_view_success(self):
        """
        Was wird geprüft:
            Das erfolgreiche Speichern der Profilwerte (Telefon, E-Mail) über
            das Formular des eigenen Profils.

        Warum:
            Die View speichert das UserProfile über das Formular und überträgt
            die E-Mail separat auf den Nutzer - beides muss aus einem echten
            POST resultieren, nicht aus Test-eigenem save().

        Erwartung:
            Umleitung zurück auf die Profilseite; Telefon im Profil und
            E-Mail am Nutzer zeigen die gesendeten Werte.
        """
        self.client.login(username="profil_tester", password="password123")
        url = reverse("user_profile_update", kwargs={"pk": self.profile.id})

        # GET-Anforderung der Formularseite prüfen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        payload = {
            "phone": "0987-654321",
            "email": "test-neu@xplanung-light.de"
        }
        response_post = self.client.post(url, data=payload)
        self.assertRedirects(
            response_post,
            reverse("user_profile_update", kwargs={"pk": self.profile.id}))

        # DB-Verifikation: ausschließlich über die View geändert
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone, "0987-654321")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test-neu@xplanung-light.de")

    def test_user_profile_update_denies_foreign_profile(self):
        """
        Was wird geprüft:
            Ein POST auf das Profil eines anderen Nutzers (fremde pk in der
            URL) durch einen angemeldeten Nutzer.

        Warum:
            Die View prüft in form_valid, ob die pk dem Profil des
            angemeldeten Nutzers gehört - ohne diesen Check könnte jeder
            fremde Profileinträge und E-Mail-Adressen überschreiben.

        Erwartung:
            Formularseite wird mit nichtfeld-Fehler neu ausgeliefert (200),
            das fremde Profil und seine E-Mail bleiben unverändert.
        """
        fremder = User.objects.create_user(
            username="fremder_nutzer", email="fremd@xplanung-light.de",
            password="password123")
        fremdes_profil = UserProfile.objects.create(
            user=fremder, phone="0555-000000")

        self.client.login(username="profil_tester", password="password123")
        url = reverse("user_profile_update", kwargs={"pk": fremdes_profil.id})
        response = self.client.post(url, data={
            "phone": "0000-uebernommen",
            "email": "angegriffen@xplanung-light.de",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gehört nicht dem angemeldeten Nutzer")

        fremdes_profil.refresh_from_db()
        self.assertEqual(fremdes_profil.phone, "0555-000000")
        fremder.refresh_from_db()
        self.assertEqual(fremder.email, "fremd@xplanung-light.de")

    # ==============================================================================
    # 2. CUSTOM PASSWORT-RESET-VIEW (POST)
    # ==============================================================================

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_custom_password_reset_sends_mail_with_username(self):
        """
        Was wird geprüft:
            Das Absenden des Passwort-Reset-Formulars mit Nutzername und
            E-Mail-Adresse eines registrierten Nutzers.

        Warum:
            Das Formularelement username ist eine Projekteigenschaft (E-Mail
            ist hier nicht unique) - erst beide Felder zusammen dürfen den
            Nutzer finden und genau eine Reset-Mail auslösen.

        Erwartung:
            Umleitung auf die Abgeschlossen-Seite; genau eine Mail an die
            hinterlegte Adresse mit Reset-Link auf http (Standard).
        """
        url = reverse("password_reset")
        response = self.client.post(url, data={
            "username": "profil_tester",
            "email": "test@xplanung-light.de",
        })
        self.assertRedirects(response, reverse("password_reset_done"))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@xplanung-light.de"])
        self.assertIn("http://testserver", mail.outbox[0].body)
        self.assertNotIn("https://testserver", mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        XPLANUNG_LIGHT_CONFIG={
            **settings.XPLANUNG_LIGHT_CONFIG,
            "mapfile_force_online_resource_https": True,
        },
    )
    def test_password_reset_links_use_https_when_forced(self):
        """
        Was wird geprüft:
            Der Versand der Reset-Mail, wenn die Konfiguration https-Links
            erzwingt.

        Warum:
            Das Protokoll der Links in der Mail wird pro Anfrage aus
            XPLANUNG_LIGHT_CONFIG aufgelöst; TÖB- und Bürger-Links sollen nie
            unverschlüsselt ausgespielt werden, wenn https verlangt ist.

        Erwartung:
            Der Reset-Link in der Mail beginnt auf https://testserver.
        """
        url = reverse("password_reset")
        response = self.client.post(url, data={
            "username": "profil_tester",
            "email": "test@xplanung-light.de",
        })
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://testserver", mail.outbox[0].body)
        self.assertNotIn("http://testserver", mail.outbox[0].body)
