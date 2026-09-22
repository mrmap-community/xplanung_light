from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization, ToebUnit, AdminOrgaUser
from xplanung_light.forms import ToebUnitCreateForm

User = get_user_model()

class ToebUnitViewTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie für den Zuständigkeitsbereich
        self.dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')

        # 2. Dynamisch eine gültige Thematik-Choice aus dem Formular ermitteln
        choices = ToebUnitCreateForm().fields['theme'].choices
        # Falls verschachtelte Gruppen existieren, flachklopfen oder erste Choice ziehen
        self.valid_theme = choices[0][0] if isinstance(choices[0][0], str) else choices[0][1][0][0]

        # 3. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(
            name="Kreisverwaltung Schilda",
            slug="kreisverwaltung-schilda",
            type="KR",
            ls="07", ks="111", gs="000",
            geometry=self.dummy_polygon
        )
        self.admin_user = User.objects.create_user(username="toeb_orga_admin", password="password123")
        self.orga_user_entry = AdminOrgaUser.objects.create(
            organization=self.orga, user=self.admin_user, is_admin=True, is_toeb_reporter=True
        )

        # 4. Eine bestehende TÖB-Einheit in der DB anlegen
        self.toeb_entry = ToebUnit.objects.create(
            organization=self.orga,
            name="Untere Wasserbehörde",
            theme=self.valid_theme,
            email="wasser@schilda.de",
            public=True,
            geometry=self.dummy_polygon
        )
        self.toeb_entry.editors.add(self.orga_user_entry)

    # ==============================================================================
    # 1. LISTEN-ANSICHTEN (GET)
    # ==============================================================================

    def test_toeb_unit_lists_accessible(self):
        """Prüft die Erreichbarkeit der internen und der öffentlichen Fachstellen-Listen."""
        public_url = reverse("toebunitpublic-list")
        response = self.client.get(public_url)
        self.assertEqual(response.status_code, 200)

        self.client.login(username="toeb_orga_admin", password="password123")
        list_url = reverse("toebunit-list")
        response_internal = self.client.get(list_url)
        self.assertEqual(response_internal.status_code, 200)
        self.assertContains(response_internal, "Untere Wasserbehörde")

    # ==============================================================================
    # 2. TÖB ANLEGEN / CREATE (POST)
    # ==============================================================================

    def test_toeb_unit_create_success(self):
        """Das Anlegen einer neuen TÖB-Fachstelle mitsamt Geometrie und Editor muss erfolgreich sein."""
        self.client.login(username="toeb_orga_admin", password="password123")
        url = reverse("toebunit-create")

        payload = {
            "organization": self.orga.id,
            "name": "Untere Naturschutzbehörde",
            "description": "Zuständig für Landschaftsschutzgebiete.",
            "theme": self.valid_theme,
            "email": "naturschutz@schilda.de",
            "public": True,
            "geometry": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
            "editors": [self.orga_user_entry.id]
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(organization=self.orga, name="Untere Naturschutzbehörde").exists())

    # ==============================================================================
    # 3. TÖB AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_toeb_unit_update_success(self):
        """Metadaten und Zuständigkeiten einer TÖB-Fachstelle können modifiziert werden."""
        self.client.login(username="toeb_orga_admin", password="password123")
        url = reverse("toebunit-update", kwargs={"pk": self.toeb_entry.id})

        payload = {
            "organization": self.orga.id,
            "name": "Untere Wasserbehörde (Zentral)",
            "description": "Zuständig für das gesamte Stadtgebiet.",
            "theme": self.valid_theme,
            "email": "wasser-neu@schilda.de",
            "public": False,
            "geometry": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
            "editors": [self.orga_user_entry.id]
        }

        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        self.toeb_entry.refresh_from_db()
        self.assertEqual(self.toeb_entry.name, "Untere Wasserbehörde (Zentral)")
        self.assertFalse(self.toeb_entry.public)

    # ==============================================================================
    # 4. TÖB ENTFERNEN / DELETE (POST)
    # ==============================================================================

    def test_toeb_unit_delete_success(self):
        """Ein Admin kann eine Fachstelle erfolgreich aus dem System löschen."""
        self.client.login(username="toeb_orga_admin", password="password123")
        url = reverse("toebunit-delete", kwargs={"pk": self.toeb_entry.id})

        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertFalse(ToebUnit.objects.filter(id=self.toeb_entry.id).exists())


