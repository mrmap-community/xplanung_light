from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import ConsentOption

User = get_user_model()

class ConsentOptionViewTests(TestCase):

    def setUp(self):
        # 1. Fristendaten aufsetzen
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)

        # 2. Superuser anlegen, da ConsentOptions fundamentale globale App-Einstellungen sind
        self.superuser = User.objects.create_superuser(username="super_admin", password="password123")

        # 3. Eine bestehende Einwilligung als Testbasis erzeugen
        self.consent_opt = ConsentOption.objects.create(
            type="commentator",  # Für Bürger/Stellungnehmende laut models.py
            title="Datenschutzerklärung Version 1.0",
            description="<p>Hier steht der gesetzliche Einwilligungstext für das Portal.</p>",
            valid_from=self.heute,
            valid_until=self.heute + timedelta(days=180),
            mandatory=True,
            opt_out=False,
            obsolete=False
        )

    # ==============================================================================
    # 1. LISTEN- UND FORMULAR-ANSICHTEN (GET)
    # ==============================================================================

    def test_consent_option_list_and_forms_get(self):
        """Ein Administrator kann die Einwilligungsliste sowie die Create/Update-Seiten per GET laden."""
        self.client.login(username="super_admin", password="password123")
        
        # 1. Testen des List-Views
        list_url = reverse("consentoption-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Datenschutzerklärung Version 1.0")

        # 2. Testen des Create-Views (Formular-GET)
        create_url = reverse("consentoption-create")
        response_create = self.client.get(create_url)
        self.assertEqual(response_create.status_code, 200)

        # 3. Testen des Update-Views (Formular-GET)
        update_url = reverse("consentoption-update", kwargs={"pk": self.consent_opt.id})
        response_update = self.client.get(update_url)
        self.assertEqual(response_update.status_code, 200)

    # ==============================================================================
    # 2. EINWILLIGUNG ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_consent_option_delete_success(self):
        """Ein Admin kann eine Einwilligung erfolgreich über den DeleteView entfernen."""
        self.client.login(username="super_admin", password="password123")
        url = reverse("consentoption-delete", kwargs={"pk": self.consent_opt.id})

        # GET auf Bestätigungsseite abrufen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST Absenden mitsamt Bestätigungs-Key
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz gelöscht?
        self.assertFalse(ConsentOption.objects.filter(id=self.consent_opt.id).exists())






