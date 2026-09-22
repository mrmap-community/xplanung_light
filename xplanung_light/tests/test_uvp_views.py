from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import BPlan, Uvp, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class UvpViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda UVP", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="uvp_orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan anlegen und zuweisen
        self.bplan = BPlan.objects.create(name="BPlan Gewerbepark West", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)

        # 4. Eine bestehende UVP in der DB anlegen
        self.uvp_entry = Uvp.objects.create(
            bplan=self.bplan,
            uvp=True,
            uvp_vp=False,
            typ="18_7_1",  # 'BPlan Außenbereich' laut Choices in models.py
            uvp_beginn_datum=self.gestern,
            uvp_ende_datum=self.heute
        )

    # ==============================================================================
    # 1. UVP-LISTE (GET)
    # ==============================================================================

    def test_uvp_list_view_accessible(self):
        """Ein verifizierter Gemeinde-Admin kann die UVP-Liste des BPlans aufrufen."""
        self.client.login(username="uvp_orga_admin", password="password123")
        url = reverse("uvp-list", kwargs={"planid": self.bplan.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. UVP ANLEGEN / CREATE (POST)
    # ==============================================================================

    def test_uvp_create_success(self):
        """Das Anlegen einer neuen UVP-Einstufung über den View muss erfolgreich sein."""
        self.client.login(username="uvp_orga_admin", password="password123")
        url = reverse("uvp-create", kwargs={"planid": self.bplan.id})

        # Felder passend zur UvpForm (ohne bplan, da es über die URL-ID injiziert wird)
        payload = {
            "uvp": True,
            "uvp_vp": True,
            "typ": "18_7_2",
            "uvp_beginn_datum": str(self.gestern),
            "uvp_ende_datum": str(self.heute)
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # DB-Verifikation
        self.assertTrue(Uvp.objects.filter(bplan=self.bplan, typ="18_7_2").exists())

    # ==============================================================================
    # 3. UVP AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_uvp_update_success(self):
        """Metadaten einer bestehenden UVP können modifiziert werden."""
        self.client.login(username="uvp_orga_admin", password="password123")
        url = reverse("uvp-update", kwargs={"planid": self.bplan.id, "pk": self.uvp_entry.id})

        payload = {
            "uvp": True,
            "uvp_vp": False,
            "typ": "18_1_1",  # Umschalten auf Feriendorf Außenbereich
            "uvp_beginn_datum": str(self.gestern),
            "uvp_ende_datum": str(self.heute)
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Refresh und DB-Check
        self.uvp_entry.refresh_from_db()
        self.assertEqual(self.uvp_entry.typ, "18_1_1")

    # ==============================================================================
    # 4. UVP ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_uvp_delete_success(self):
        """Ein Admin kann eine zugeordnete UVP erfolgreich löschen."""
        self.client.login(username="uvp_orga_admin", password="password123")
        url = reverse("uvp-delete", kwargs={"planid": self.bplan.id, "pk": self.uvp_entry.id})

        # GET-Bestätigungsseite abrufen
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST-Löschauftrag ausführen mitsamt Bestätigungs-Key
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz darf nicht mehr existieren
        self.assertFalse(Uvp.objects.filter(id=self.uvp_entry.id).exists())
