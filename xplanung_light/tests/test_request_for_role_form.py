from django.test import TestCase
from xplanung_light.models import AdministrativeOrganization, RequestForRole
from xplanung_light.forms import RequestForRoleCreateForm

class RequestForRoleCreateFormTests(TestCase):

    def setUp(self):
        # Wir legen zwei Gebietskörperschaften an, die im Formular ausgewählt werden können
        self.orga_a = AdministrativeOrganization.objects.create(
            name="Verbandsgemeinde Schilda",
            ls="07",
            ks="111",
            gs="000"
        )
        self.orga_b = AdministrativeOrganization.objects.create(
            name="Ortsgemeinde Fehlerhausen",
            ls="07",
            ks="111",
            gs="001"
        )

    def test_request_for_role_happy_path(self):
        """Das Formular muss valide sein, wenn eine erlaubte Rolle und Organisationen gewählt werden."""
        form_data = {
            "role": "OA",  # 'OA' steht für Organisationsadministrator laut ROLE_CHOICES in models.py
            "organizations": [self.orga_a.id, self.orga_b.id]  # Mehrfachauswahl via ManyToMany
        }
        
        form = RequestForRoleCreateForm(data=form_data)
        
        # Verifiziert, dass das Formular mitsamt dem GemeindeSelect3-Widget fehlerfrei validiert
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # Datensatz speichern und Relationen prüfen
        saved_request = form.save()
        self.assertEqual(saved_request.role, "OA")
        self.assertEqual(saved_request.organizations.count(), 2)
        self.assertIn(self.orga_a, saved_request.organizations.all())

    def test_request_for_role_fails_without_organizations(self):
        """Das Formular ist invalid und wirft einen Fehler, wenn keine Organisation ausgewählt wurde."""
        form_data = {
            "role": "TR",  # 'TR' = TOEB-Reporter
            "organizations": []  # Fehler: Leere Auswahl bei einem Pflichtfeld
        }
        
        form = RequestForRoleCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("organizations", form.errors)
