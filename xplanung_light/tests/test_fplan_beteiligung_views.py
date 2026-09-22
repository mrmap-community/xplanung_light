from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import FPlan, FPlanBeteiligung, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class FPlanBeteiligungViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Stadtplanungsamt Schilda FPlan", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="fplan_orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. FPlan anlegen und zuweisen
        self.fplan = FPlan.objects.create(name="FPlan Fortschreibung", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)

        # 4. Ein Beteiligungsverfahren in der DB anlegen
        self.beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            typ="1000",
            bekanntmachung_datum=self.heute,
            start_datum=self.morgen,
            end_datum=self.in_einem_monat,
            allow_online_beitrag=True
        )

    # ==============================================================================
    # 1. LIST- UND FORMULAR-ANSICHTEN (GET)
    # ==============================================================================

    def test_fplan_beteiligung_list_and_forms_get(self):
        """Ein Admin kann die FPlan-Verfahrensliste sowie die Formset-Seiten per GET laden."""
        self.client.login(username="fplan_orga_admin", password="password123")
        
        # 1. Testen des List-Views
        list_url = reverse("fplanbeteiligung-list", kwargs={"planid": self.fplan.id})
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # 2. Testen des Create-Views (Formular-GET)
        create_url = reverse("fplanbeteiligung-create", kwargs={"planid": self.fplan.id})
        response_create = self.client.get(create_url)
        self.assertEqual(response_create.status_code, 200)

        # 3. Testen des Update-Views (Formular-GET)
        update_url = reverse("fplanbeteiligung-update", kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})
        response_update = self.client.get(update_url)
        self.assertEqual(response_update.status_code, 200)

    # ==============================================================================
    # 2. VERFAHREN LÖSCHEN / STANDARD DELETE (POST)
    # ==============================================================================

    def test_fplan_beteiligung_delete_success(self):
        """Ein Admin kann ein FPlan-Beteiligungsverfahren erfolgreich löschen."""
        self.client.login(username="fplan_orga_admin", password="password123")
        url = reverse("fplanbeteiligung-delete", kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})

        # GET auf Bestätigung
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST Absenden mitsamt Bestätigungs-Key
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz gelöscht?
        self.assertFalse(FPlanBeteiligung.objects.filter(id=self.beteiligung.id).exists())

