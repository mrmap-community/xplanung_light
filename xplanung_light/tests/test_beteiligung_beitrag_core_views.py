from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanBeteiligung, 
    FPlanBeteiligung, 
    BPlanBeteiligungBeitrag,
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class BeteiligungBeitragCoreViewTests(TestCase):

    def setUp(self):
        # 1. Geometrie & Fristen aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisationen & Benutzer deklarieren
        self.orga = AdministrativeOrganization.objects.create(name="Zentrales Planungsamt", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="beitrag_core_admin", password="password123")
        self.normal_user = User.objects.create_user(username="buerger_online", password="password123")
        
        # Admin-Rechte zuweisen
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan & aktives Beteiligungsverfahren anlegen
        self.bplan = BPlan.objects.create(name="BPlan Wohngebiet", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat
        )

        # 4. FPlan & aktives Beteiligungsverfahren anlegen
        self.fplan = FPlan.objects.create(name="FPlan Regional", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat
        )

        # 5. Einen bestehenden Bürgerbeitrag erzeugen
        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="Bürger-Einwand Lärm",
            beschreibung="<p>Bitte um Prüfung.</p>",
            name="Heinz Meier",
            approved=False,
            eingangsdatum=self.heute,
            typ="1000"
        )

    # ==============================================================================
    # 1. BPLAN: CORE-VIEWS (ONLINE-FORMULAR GET & INTERNE LISTE)
    # ==============================================================================

    def test_bplan_online_contribution_form_and_admin_list_get(self):
        """Prüft das Laden des Online-Formulars (Bürger) und der internen Beitragsliste (Admin)."""
        # KORREKTUR: 'pk' anstelle von 'beteiligungid' übergeben, um dem django-Routing zu entsprechen
        url_create = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id
        })
        response_create = self.client.get(url_create)
        self.assertEqual(response_create.status_code, 200)

        # Die interne Beitragsliste aufrufen
        url_list = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        self.client.login(username="beitrag_core_admin", password="password123")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, 200)

    # ==============================================================================
    # 2. FPLAN: CORE-VIEWS (ONLINE-FORMULAR GET & INTERNE LISTE)
    # ==============================================================================

    def test_fplan_online_contribution_form_and_admin_list_get(self):
        """Prüft das Laden des FPlan-Online-Formulars und der internen Beitragsliste."""
        # KORREKTUR: 'pk' anstelle von 'beteiligungid' übergeben
        url_create = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id
        })
        response_create = self.client.get(url_create)
        self.assertEqual(response_create.status_code, 200)

        # Admin-Beitragsliste für FPlan
        url_list = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "beteiligungid": self.fplan_beteiligung.id
        })
        self.client.login(username="beitrag_core_admin", password="password123")
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, 200)

    # ==============================================================================
    # 3. ABSICHERUNG DER ZUGRIFFSCONSTRAINTS (PERMISSION DENIED PRÜFUNG)
    # ==============================================================================

    def test_admin_list_denied_for_unauthorized_user(self):
        """Ein normaler Bürger darf die behördliche Beitragsliste niemals einsehen."""
        self.client.login(username="buerger_online", password="password123")
        url_list = reverse("beteiligungbeitrag-list", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url_list)
        self.assertEqual(response.status_code, 403)
