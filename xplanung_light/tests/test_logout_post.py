"""Tests der Abmeldung aus dem Navigationsbereich (POST statt Link)."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class LogoutPostTests(TestCase):
    """Der Abmeldeknopf muss ein POST-Formular sein und wirklich abmelden."""

    def setUp(self):
        self.test_user = User.objects.create_user(
            username="abmelderin",
            email="abmelden@kommune.de",
            password="s1cheres Passwort123",
        )
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.test_user)

    def test_navigationsbereich_bietet_logout_als_post_formular_an(self):
        """Was wird geprüft: Ob der Navigationsbereich den Abmeldeknopf mit einem
        POST-Formular auf die Logout-URL samt CSRF-Token ausliefert.
        Warum: ``LogoutView`` lehnt seit Django 5 GET-Anfragen mit 405 ab; der alte
        Link (``href``) meldete auf Debian 13 (Django 5.2) nicht mehr ab.
        Erwartung: Ausgeliefertes ``method="post"`` auf die Logout-URL und ein
        CSRF-Eingabefeld; kein ``href``-Link mehr auf die Logout-URL.
        """
        antwort = self.client.get(reverse("home"))
        self.assertEqual(antwort.status_code, 200)
        inhalt = antwort.content.decode()
        logout_url = reverse("logout")
        self.assertIn('method="post"', inhalt)
        self.assertIn(f'action="{logout_url}"', inhalt)
        self.assertIn("csrfmiddlewaretoken", inhalt)
        self.assertNotIn(f'href="{logout_url}"', inhalt)

    def test_post_auf_logout_meldet_ab_und_leitet_zur_startseite(self):
        """Was wird geprüft: Ob ein POST auf die Logout-URL die Sitzung leert und
        auf die Startseite weiterleitet.
        Warum: Die URL-Registrierung trägt ``next_page="home"``; nach dem
        Rollenwechsel auf POST muss dieser Weg weiter funktionieren.
        Erwartung: 302 auf die Startseite; danach erscheint im Navigationsbereich
        der Anmeldeknopf statt des Abmeldeknopfs.
        """
        antwort = self.client.post(reverse("logout"))
        self.assertEqual(antwort.status_code, 302)
        self.assertEqual(antwort.headers["Location"], reverse("home"))
        antwort = self.client.get(reverse("home"))
        inhalt = antwort.content.decode()
        self.assertNotIn("Abmelden", inhalt)
        self.assertIn("Anmelden", inhalt)
