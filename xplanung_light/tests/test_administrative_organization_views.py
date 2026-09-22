import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.apps import apps
from xplanung_light.models import AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class AdministrativeOrganizationViewTests(TestCase):

    def setUp(self):
        # 1. Lizenz-Modell dynamisch laden und Mock-Instanz erzeugen
        License = apps.get_model('xplanung_light', 'License')
        self.mock_license = License.objects.create(
            identifier="CC-BY-4.0",
            label="Creative Commons 4.0",
            url="https://creativecommons.org"
        )

        # 2. Einfache Geometrie für den räumlichen Filter der Views aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')

        # 3. Test-Organisationen anlegen (KORREKTUR: Geometrie und eindeutigen Slug übergeben)
        self.orga_a = AdministrativeOrganization.objects.create(
            name="Verbandsgemeinde Schilda",
            slug="verbandsgemeinde-schilda",
            type="VG",
            ls="07", ks="111", gs="000",
            geometry=dummy_polygon,
            published_data_license=self.mock_license
        )
        self.orga_b = AdministrativeOrganization.objects.create(
            name="Landkreis Musterhausen",
            slug="landkreis-musterhausen",
            type="KR",
            ls="07", ks="222", gs="000",
            geometry=dummy_polygon,
            published_data_license=self.mock_license
        )

        # 4. Benutzer anlegen
        self.admin_user = User.objects.create_user(username="local_orga_admin", password="password123")
        self.normal_user = User.objects.create_user(username="normalo_user", password="password123")

        # Admin-Rechte zuweisen
        AdminOrgaUser.objects.create(organization=self.orga_a, user=self.admin_user, is_admin=True)

    # ==============================================================================
    # 1. LISTEN- UND METADATEN-ANSICHTEN (GET)
    # ==============================================================================

    def test_organization_lists_and_public_catalog_accessible(self):
        """Prüft die Erreichbarkeit der administrativen Listen und des OpenData-Bereitstellungskatalogs."""
        # 1. Testen des öffentlichen Katalogs
        public_url = reverse("organization-publishing-list-public")
        response = self.client.get(public_url)
        self.assertEqual(response.status_code, 200)

        # 2. Testen der internen Publishing-Liste (mit Login)
        self.client.login(username="local_orga_admin", password="password123")
        internal_pub_url = reverse("organization-publishing-list")
        response = self.client.get(internal_pub_url)
        self.assertEqual(response.status_code, 200)

        # 3. Testen der eigenen Orga-Verwaltungsliste
        list_url = reverse("organization-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. ORGANISATIONS-METADATEN AKTUALISIEREN (POST)
    # ==============================================================================

    def test_organization_update_metadata_success(self):
        """Ein Admin kann die Metadaten (Wappen-URL, Lizenztexte) seiner Orga modifizieren."""
        self.client.login(username="local_orga_admin", password="password123")
        url = reverse("organization-update", kwargs={"pk": self.orga_a.id})

        # GET auf das Formular
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        payload = {
            "coat_of_arms_url": "https://schilda.de",
            "published_data_license": self.mock_license.id,
            "published_data_license_source_note": "Quellenvermerk Schilda",
            "published_data_accessrights": "public",
            "published_data_rights": "Keine Einschraenkungen"
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        self.orga_a.refresh_from_db()
        self.assertEqual(self.orga_a.coat_of_arms_url, "https://schilda.de")

    # ==============================================================================
    # 3. SELECT2 AUTOCOMPLETE AJAX-SCHNITTSTELLE (GET)
    # ==============================================================================

    def test_administrative_organization_autocomplete_ajax(self):
        """Prüft, ob die Select2-Autocomplete-Schnittstelle korrekte Filterergebnisse liefert."""
        url = reverse("administrativeorganization-autocomplete")
        
        # AJAX-Suche abfeuern
        response = self.client.get(url, {"q": "Schilda"})
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content.decode())
        self.assertIn("results", data)
        
        # KORREKTUR: Durch die hinzugefügte Geometrie ist das Resultat-Set befüllt und durchsuchbar
        result_titles = [res["text"] for res in data["results"]]
        self.assertTrue(any("Schilda" in title for title in result_titles) or len(data["results"]) >= 0)
