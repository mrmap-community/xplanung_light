"""Tests der Benachrichtigung von TÖBs (Träger öffentlicher Belange) per Massen-E-Mail."""

from django.conf import settings
from django.test import TestCase, override_settings
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
    """Liste, Formular und Versand der TÖB-Benachrichtigungen für BPlan und FPlan."""

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

    # ==============================================================================
    # 3. LISTE: BERECHTIGUNG, SUPERUSER- UND STATUS-ANZEIGE
    # ==============================================================================

    def _list_url(self, plantyp, plan, beteiligung):
        return reverse("beteiligungnotification-list", kwargs={
            "plantyp": plantyp, "planid": plan.id, "beteiligungid": beteiligung.id})

    def test_list_view_denies_user_without_gemeinde_admin_role(self):
        """
        Was wird geprüft:
            Der Aufruf der Benachrichtigungsliste durch einen angemeldeten Nutzer
            ohne Admin-Rolle in der Gemeinde des Plans.

        Warum:
            Die Liste zeigt internen Schriftverkehr zu einem Verfahren; nur
            Gemeinde-Administratoren (oder Superuser) dürfen sie sehen.

        Erwartung:
            Status 403 (Zugriff verweigert).
        """
        User.objects.create_user(username="nur_zuschauer", password="password123")
        self.client.login(username="nur_zuschauer", password="password123")
        response = self.client.get(
            self._list_url("bplan", self.bplan, self.bplan_beteiligung))
        self.assertEqual(response.status_code, 403)

    def test_superuser_opens_notification_list_for_both_plantyps(self):
        """
        Was wird geprüft:
            Der Aufruf der Benachrichtigungsliste durch einen Superuser für
            BPlan- und FPlan-Verfahren.

        Warum:
            Die Liste verzweigt den Zugriff je Plantyp - Superuser dürfen ohne
            Admin-Rolle in jede Gemeinde sehen.

        Erwartung:
            In beiden Listen Status 200.
        """
        User.objects.create_superuser(
            username="notification_boss", email="boss@example.com",
            password="password123")
        self.client.login(username="notification_boss", password="password123")
        self.assertEqual(self.client.get(
            self._list_url("bplan", self.bplan, self.bplan_beteiligung)
        ).status_code, 200)
        self.assertEqual(self.client.get(
            self._list_url("fplan", self.fplan, self.fplan_beteiligung)
        ).status_code, 200)

    def test_list_view_shows_inactive_status_for_closed_procedure(self):
        """
        Was wird geprüft:
            Die Statusanzeige der Liste, wenn das Beteiligungsverfahren bereits
            abgelaufen ist.

        Warum:
            Die Liste berechnet den Status aus Bekanntmachungs- und Enddatum;
            abgelaufene Verfahren müssen als inaktiv dargestellt werden.

        Erwartung:
            Status 200 und context["status"] gleich 0.
        """
        self.client.login(username="orga_admin", password="password123")
        beendete_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, typ="1000",
            bekanntmachung_datum=self.gestern, start_datum=self.gestern,
            end_datum=self.gestern)
        response = self.client.get(
            self._list_url("bplan", self.bplan, beendete_beteiligung))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["status"], 0)

    # ==============================================================================
    # 4. FORMULARVARIANTEN DES VERSANDS
    # ==============================================================================

    def test_submit_without_message_still_notifies_editors(self):
        """
        Was wird geprüft:
            Das Absenden der Benachrichtigung ohne Begleitnachricht.

        Warum:
            Die Nachricht ist freiwillig - auch ohne Text muss eine
            Standard-Benachrichtigung an die Sachbearbeiter der TÖB-Stellen
            gehen und das Protokoll geschrieben werden.

        Erwartung:
            Benachrichtigung in der Datenbank, mindestens eine E-Mail an die
            Reporterin, Protokoll ohne Kommentar-Text.
        """
        self.client.login(username="orga_admin", password="password123")
        url = reverse("beteiligungnotification-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id})
        response = self.client.post(
            url, data={"selected_toebs": [self.toeb_unit.id]}, follow=True)
        self.assertEqual(response.status_code, 200)

        notification = BPlanBeteiligungToebNotification.objects.get(
            bplanbeteiligung=self.bplan_beteiligung)
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn("reporter@behoerde.de", mail.outbox[0].to)
        self.assertEqual(notification.message, None)

    @override_settings(XPLANUNG_LIGHT_CONFIG={
        **settings.XPLANUNG_LIGHT_CONFIG,
        "mapfile_force_online_resource_https": True,
    })
    def test_links_are_forced_to_https_when_configured(self):
        """
        Was wird geprüft:
            Der Versand, wenn die Konfiguration erzwingt, Links auf https
            umzustellen.

        Warum:
            Die Permalink- und Listen-Links in der E-Mail müssen dem in
            XPLANUNG_LIGHT_CONFIG konfigurierten Schema folgen, damit
            TÖB-Stellen nicht über unverschlüsselte Adressen geleitet werden.

        Erwartung:
            In Text- und HTML-Fassung der E-Mail erscheinen ausschließlich
            https-Links auf die Beteiligung.
        """
        self.client.login(username="orga_admin", password="password123")
        url = reverse("beteiligungnotification-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id})
        self.client.post(
            url,
            data={"message": "Bitte bis Fristende rückmelden.",
                  "selected_toebs": [self.toeb_unit.id]},
            follow=True)

        self.assertTrue(len(mail.outbox) >= 1)
        email = mail.outbox[0]
        volltext = email.body + email.alternatives[0][0]
        self.assertIn("https://testserver/bplan", volltext)
        self.assertNotIn("http://testserver/bplan", volltext)
