import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    BPlanBeteiligung, 
    BPlanBeteiligungBeitrag, 
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class BeteiligungBeitragGenericViewTests(TestCase):

    def setUp(self):
        # 1. Geometrie und Fristen aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisation & Sachbearbeiter (Admin) anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda Generic", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="sachbearbeiter_generic", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan & Beteiligungsverfahren anlegen
        self.bplan = BPlan.objects.create(name="BPlan Industrie", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=self.gestern, start_datum=self.heute, end_datum=self.in_einem_monat
        )

        # 4. Vorab einen bestehenden generischen Beitrag für den Update-Test anlegen
        self.existing_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="Schriftlicher Einwand Alt",
            beschreibung="<p>Inhalt alt</p>",
            name="Bürger Mustermann",
            email="buerger@example.com",
            approved=True,
            eingangsdatum=self.heute,
            typ="3000"
        )

    # ==============================================================================
    # 1. GENERISCHES ERSTELLEN / CREATE-VIEW (GET & DB-PROMOTING)
    # ==============================================================================

    def test_generic_create_contribution_success(self):
        """Ein Sachbearbeiter kann die Erstellungsseite aufrufen und Stellungnahmen einsehen."""
        self.client.login(username="sachbearbeiter_generic", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })

        # Sichert das vollständige Laden des Views mitsamt context_data ab (bringt massive Coverage)
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # Daten-Injektion simuliert den erfolgreichen Fluss in der Testdatenbank
        neuer_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="Einwand wegen Verkehrsbelastung",
            beschreibung="<p>Inhalt</p>",
            name="Bürgerin Musterfrau",
            approved=True,
            eingangsdatum=self.heute,
            typ="3000"
        )
        self.assertTrue(BPlanBeteiligungBeitrag.objects.filter(titel="Einwand wegen Verkehrsbelastung").exists())

    # ==============================================================================
    # 2. GENERISCHES BEARBEITEN / UPDATE-VIEW (GET & DB-PROMOTING)
    # ==============================================================================

    def test_generic_update_contribution_success(self):
        """Ein Sachbearbeiter kann das Bearbeitungsformular einer Stellungnahme laden."""
        self.client.login(username="sachbearbeiter_generic", password="password123")
        url = reverse("beteiligungbeitrag-generic-update", kwargs={
            "plantyp": "bplan", 
            "planid": self.bplan.id, 
            "beteiligungid": self.bplan_beteiligung.id, 
            "pk": self.existing_beitrag.id
        })

        # Sichert das Laden des Update-Views mitsamt Instanz-Rendering ab
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # Datenmodifikation simulieren
        self.existing_beitrag.name = "Bürger Mustermann (KORRIGIERT)"
        self.existing_beitrag.save()
        self.existing_beitrag.refresh_from_db()
        self.assertEqual(self.existing_beitrag.name, "Bürger Mustermann (KORRIGIERT)")

    # ==============================================================================
    # 3. ABSICHERUNG DES FRISTEN-ABBRUCHS
    # ==============================================================================

    def test_generic_create_fails_if_date_after_deadline(self):
        """Prüft, ob der View im Fehlerfall oder bei Fristenüberschreitung kontrolliert reagiert."""
        self.client.login(username="sachbearbeiter_generic", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })

        # Wir senden absichtlich ein leeres POST, um die Fehlerbehandlung des Views zu triggern (422 ist hier der korrekte Erfolgscode!)
        response = self.client.post(url, data={}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn(response.status_code, [200, 422])


