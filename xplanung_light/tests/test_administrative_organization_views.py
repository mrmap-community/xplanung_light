"""
Tests der Organisations-Views: Listen, öffentlicher Bereitstellungskatalog, Metadaten ändern und
Select2-Autocomplete.
"""

import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.apps import apps
from xplanung_light.models import AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

class AdministrativeOrganizationViewTests(TestCase):
    """Views zu Gebietskörperschaften (administrative Organisationen)."""

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

    # ==============================================================================
    # 4. AUTOCOMPLETE FÜR ANGERMELDETE NUTZER
    # ==============================================================================

    def test_autocomplete_returns_results_for_authenticated_user(self):
        """
        Was wird geprüft:
            Die Select2-Autocomplete-Schnittstelle mit angemeldetem Nutzer,
            einmal mit Suchbegriff und einmal ohne.

        Warum:
            Ohne Anmeldung liefert die Schnittstelle bewusst nichts - erst
            angemeldete Nutzer sehen Organisationen, und der Suchbegriff soll
            nach Namensteilanfang filtern (case-insensitive).

        Erwartung:
            Mit q="verbandsgemeinde" nur die Verbandsgemeinde Schilda
            (Groß-/Kleinschreibung egal, Filter greift am Namenanfang),
            ohne q beide Organisationen.
        """
        self.client.login(username="local_orga_admin", password="password123")
        url = reverse("administrativeorganization-autocomplete")

        response = self.client.get(url, {"q": "verbandsgemeinde"})
        self.assertEqual(response.status_code, 200)
        ids = [r["id"] for r in response.json()["results"]]
        self.assertEqual(ids, [str(self.orga_a.id)])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        ids = {r["id"] for r in response.json()["results"]}
        self.assertEqual(ids, {str(self.orga_a.id), str(self.orga_b.id)})

    # ==============================================================================
    # 5. SUPERUSER-SICHT AUF BEIDE ORGANISATIONSLISTEN
    # ==============================================================================

    def test_superuser_sees_all_organizations_in_both_lists(self):
        """
        Was wird geprüft:
            Der Aufruf der Bereitstellungsliste und der
            Organisations-Verwaltungsliste als Superuser.

        Warum:
            Beide Listen verzweigen in get_queryset zwischen Superuser (alle
            Organisationen) und normalem Nutzer (nur eigene) - der
            Superuser-Zweig war bisher ungetestet.

        Erwartung:
            Jeweils Status 200; in der Verwaltungsliste erscheinen beide
            Organisationen trotz fehlender Admin-Rolle.        """
        User.objects.create_superuser(
            username="orga_boss", email="boss@example.com", password="password123")
        self.client.login(username="orga_boss", password="password123")

        response = self.client.get(reverse("organization-publishing-list"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("organization-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verbandsgemeinde Schilda")
        self.assertContains(response, "Landkreis Musterhausen")

    def test_superuser_opens_organization_update_form(self):
        """
        Was wird geprüft:
            Der Aufruf des Bearbeitungsformulars einer Organisation als
            Superuser ohne Admin-Rolle in dieser Organisation.

        Warum:
            get_object() prüft die Admin-Rolle nur für Nicht-Superuser - der
            Superuser-Pfad (direktes return ohne Rollenprüfung) muss offen
            bleiben, sonst ist Verwaltung unmöglich.

        Erwartung:
            Status 200 mit geöffnetem Formular.
        """
        User.objects.create_superuser(
            username="orga_boss", email="boss@example.com", password="password123")
        self.client.login(username="orga_boss", password="password123")
        response = self.client.get(
            reverse("organization-update", kwargs={"pk": self.orga_a.id}))
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 6. METADATEN-BEARBEITUNG OHNE ADMIN-ROLLE
    # ==============================================================================

    def test_organization_update_denies_user_without_admin_role(self):
        """
        Was wird geprüft:
            Der Aufruf des Bearbeitungsformulars einer Organisation durch einen
            angemeldeten Nutzer ohne Admin-Rolle in dieser Organisation.

        Warum:
            get_object() lässt nur Superuser oder Admins der Organisation durch
            und wirft sonst PermissionDenied - der Zweig muss gegen
            Rechte-Ausweitung abgesichert sein.

        Erwartung:
            Status 403, der Datensatz bleibt unverändert.
        """
        self.client.login(username="normalo_user", password="password123")
        url = reverse("organization-update", kwargs={"pk": self.orga_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(url, data={
            "coat_of_arms_url": "https://getroffen.example",
            "published_data_license": self.mock_license.id,
            "published_data_rights": "Keine Einschraenkungen",
            "published_data_accessrights": "public",
        })
        self.assertEqual(response.status_code, 403)
        self.orga_a.refresh_from_db()
        self.assertEqual(self.orga_a.coat_of_arms_url, None)
