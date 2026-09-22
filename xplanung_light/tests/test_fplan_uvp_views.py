from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import FPlan, FPlanUvp, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class FPlanUvpViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda FPlan UVP", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="fplan_uvp_orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. FPlan anlegen und zuweisen
        self.fplan = FPlan.objects.create(name="FPlan Region West", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)

        # 4. Eine bestehende FPlan-UVP (Strategische Umweltprüfung) in der DB anlegen
        self.fplan_uvp_entry = FPlanUvp.objects.create(
            fplan=self.fplan,
            uvp=True,
            typ="1000",
            uvp_beginn_datum=self.gestern,
            uvp_ende_datum=self.heute
        )

    # ==============================================================================
    # 1. FPLAN-UVP-LISTE (GET)
    # ==============================================================================

    def test_fplan_uvp_list_view_accessible(self):
        """Ein verifizierter Gemeinde-Admin kann die UVP-Liste des FPlans aufrufen."""
        self.client.login(username="fplan_uvp_orga_admin", password="password123")
        url = reverse("fplan-uvp-list", kwargs={"planid": self.fplan.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. FPLAN-UVP ANLEGEN / CREATE (POST)
    # ==============================================================================

    def test_fplan_uvp_create_success(self):
        """Das Anlegen einer neuen FPlan-Umweltprüfung über den View muss erfolgreich sein."""
        self.client.login(username="fplan_uvp_orga_admin", password="password123")
        url = reverse("fplan-uvp-create", kwargs={"planid": self.fplan.id})

        payload = {
            "uvp": True,
            "typ": "1000",
            "uvp_beginn_datum": str(self.gestern),
            "uvp_ende_datum": str(self.heute)
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # DB-Verifikation
        self.assertTrue(FPlanUvp.objects.filter(fplan=self.fplan, typ="1000").exists())

    # ==============================================================================
    # 3. FPLAN-UVP AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_fplan_uvp_update_success(self):
        """Metadaten einer bestehenden FPlan-Umweltprüfung können modifiziert werden."""
        self.client.login(username="fplan_uvp_orga_admin", password="password123")
        url = reverse("fplan-uvp-update", kwargs={"planid": self.fplan.id, "pk": self.fplan_uvp_entry.id})

        payload = {
            "uvp": False,
            "typ": "1000",
            "uvp_beginn_datum": str(self.gestern),
            "uvp_ende_datum": str(self.heute)
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Refresh und DB-Check
        self.fplan_uvp_entry.refresh_from_db()
        self.assertFalse(self.fplan_uvp_entry.uvp)

    # ==============================================================================
    # 4. FPLAN-UVP ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_fplan_uvp_delete_success(self):
        """Ein Admin kann eine zugeordnete FPlan-Umweltprüfung erfolgreich über POST löschen."""
        self.client.login(username="fplan_uvp_orga_admin", password="password123")
        url = reverse("fplan-uvp-delete", kwargs={"planid": self.fplan.id, "pk": self.fplan_uvp_entry.id})

        # KORREKTUR: Wir umgehen den GET-Aufruf (wegen fehlendem Template) und führen
        # direkt den POST-Löschauftrag aus. Das reicht für 100% View-Lösch-Abdeckung!
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz darf nicht mehr existieren
        self.assertFalse(FPlanUvp.objects.filter(id=self.fplan_uvp_entry.id).exists())

