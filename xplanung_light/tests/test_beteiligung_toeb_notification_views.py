from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from django.core import mail
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanBeteiligung, 
    FPlanBeteiligung, 
    AdministrativeOrganization,
    AdminOrgaUser,
    ToebUnit,
    BPlanBeteiligungToebNotification,
    FPlanBeteiligungToebNotification
)

User = get_user_model()

class BeteiligungToebNotificationViewTests(TestCase):

    def setUp(self):
        # 1. Geometrie & Fristen aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisationen (Kommune + Behörde)
        self.kommune = AdministrativeOrganization.objects.create(name="Stadt Schilda", ls="07", ks="111", gs="000")
        self.behoerde = AdministrativeOrganization.objects.create(name="Landkreis Umweltamt", ls="07", ks="111", gs="001")

        # 3. User anlegen (Admin für Kommune und ein Reporter für die TÖB-Behörde)
        self.admin_user = User.objects.create_user(username="orga_admin", password="password123")
        self.reporter_user = User.objects.create_user(username="toeb_reporter", email="reporter@behoerde.de", password="password123")

        # Rollen zuweisen
        AdminOrgaUser.objects.create(organization=self.kommune, user=self.admin_user, is_admin=True)
        self.toeb_editor = AdminOrgaUser.objects.create(organization=self.behoerde, user=self.reporter_user, is_toeb_reporter=True)

        # 4. TÖB-Einheit für das Kreis-Umweltamt erstellen (Theme 'NSLP' = Naturschutz)
        self.toeb_unit = ToebUnit.objects.create(
            organization=self.behoerde,
            name="Untere Naturschutzbehörde",
            theme="NSLP",
            public=True
        )
        self.toeb_unit.editors.add(self.toeb_editor)

        # 5. BPlan & Beteiligungsverfahren aufsetzen
        self.bplan = BPlan.objects.create(name="BPlan Windpark", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.kommune)
        
        # KORREKTUR: Fristenfenster so setzen, dass 'heute' vollkommen aktiv und gültig ist,
        # um die get_form_kwargs() PermissionDenied-Blockade (HTTP 403) im View aufzulösen!
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, 
            typ="1000",
            bekanntmachung_datum=self.gestern, 
            start_datum=self.gestern, 
            end_datum=self.in_einem_monat
        )
        self.bplan_beteiligung.assigned_toebs.add(self.toeb_unit)

        # 6. FPlan & Beteiligungsverfahren aufsetzen
        self.fplan = FPlan.objects.create(name="FPlan Windkraft", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.kommune)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, 
            typ="1000",
            bekanntmachung_datum=self.gestern, 
            start_datum=self.gestern, 
            end_datum=self.in_einem_monat
        )
        self.fplan_beteiligung.assigned_toebs.add(self.toeb_unit)

    # ==============================================================================
    # 1. BPLAN NOTIFICATION-VIEWS (GET, LIST & REINER FLRECHER POST)
    # ==============================================================================

    def test_bplan_notification_list_and_create_get(self):
        """Prüft die Erreichbarkeit der Listen- und Erstellungsformulare für den BPlan."""
        self.client.login(username="orga_admin", password="password123")
        
        # Test List-View
        list_url = reverse("beteiligungnotification-list", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # Test Create-View Formularseite (GET)
        create_url = reverse("beteiligungnotification-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        response_get = self.client.get(create_url)
        self.assertEqual(response_get.status_code, 200)

    def test_bplan_notification_submit_mass_email_success(self):
        """Das Absenden des nackten Crispy-Formulars muss die Mails absenden und das Protokoll erzeugen."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("beteiligungnotification-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })

        # KORREKTUR: Rein flacher Standard-POST-Payload passend zur crispy ModelForm
        payload = {
            "message": "Sehr geehrte Damen und Herren, wir bitten um Stellungnahme zum neuen BPlan Windpark.",
            "selected_toebs": [self.toeb_unit.id]
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # 1. VERIFIKATION: Wurde das Benachrichtigungsobjekt mitsamt Protokoll in der DB angelegt?
        self.assertTrue(BPlanBeteiligungToebNotification.objects.filter(bplanbeteiligung=self.bplan_beteiligung).exists())
        notification = BPlanBeteiligungToebNotification.objects.get(bplanbeteiligung=self.bplan_beteiligung)
        self.assertEqual(notification.message, payload["message"])
        
        # 2. EMAIL-VERIFIKATION: Hat der View form_valid() komplett durchlaufen und die Mails gefeuert?
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn("reporter@behoerde.de", mail.outbox[0].to)

    # ==============================================================================
    # 2. FPLAN NOTIFICATION-VIEWS (REINER FLACHER POST)
    # ==============================================================================

    def test_fplan_notification_submit_mass_email_success(self):
        """Das Absenden des Crispy-Formulars muss Benachrichtigungs-Mails für den FPlan abfeuern."""
        self.client.login(username="orga_admin", password="password123")
        url = reverse("beteiligungnotification-create", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "beteiligungid": self.fplan_beteiligung.id
        })

        payload = {
            "message": "Bitte um Stellungnahme zum FPlan.",
            "selected_toebs": [self.toeb_unit.id]
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # DB-Verifikation für FPlan
        self.assertTrue(FPlanBeteiligungToebNotification.objects.filter(fplanbeteiligung=self.fplan_beteiligung).exists())
