from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from xplanung_light.models import AdministrativeOrganization, AdminOrgaUser, ToebUnit
from xplanung_light.forms import ToebUnitCreateForm

User = get_user_model()

class ToebUnitFormValidationTests(TestCase):

    def setUp(self):
        # 1. Erstelle zwei getrennte Organisationen (Kommunen)
        self.orga_a = AdministrativeOrganization.objects.create(name="Kommune A")
        self.orga_b = AdministrativeOrganization.objects.create(name="Kommune B")

        # 2. Erstelle Benutzer
        self.user_valid = User.objects.create_user(username="reporter_a", password="password123")
        self.user_wrong_orga = User.objects.create_user(username="reporter_b", password="password123")
        self.user_no_role = User.objects.create_user(username="sachbearbeiter_a", password="password123")

        # 3. Weise Rollen und Organisationen über das AdminOrgaUser-Zwischenmodell zu
        # Gültiger TÖB-Reporter für Organisation A
        AdminOrgaUser.objects.create(
            organization=self.orga_a,
            user=self.user_valid,
            is_toeb_reporter=True
        )

        # TÖB-Reporter, aber für die falsche Organisation B
        AdminOrgaUser.objects.create(
            organization=self.orga_b,
            user=self.user_wrong_orga,
            is_toeb_reporter=True
        )

        # In Organisation A, aber KEIN TÖB-Reporter (z.B. nur normaler User oder Admin)
        AdminOrgaUser.objects.create(
            organization=self.orga_a,
            user=self.user_no_role,
            is_toeb_reporter=False
        )

        # KORREKTUR: Dynamisch die erste gültige Auswahlmöglichkeit für 'theme' ermitteln,
        # um 'invalid_choice' Fehler im Testlauf unabhängig vom Datenmodell zu verhindern.
        empty_form = ToebUnitCreateForm()
        theme_choices = empty_form.fields['theme'].choices
        # theme_choices ist eine Liste von (Wert, Label)-Tupeln. Wir nehmen den Wert des ersten echten Eintrags.
        # Falls der erste Eintrag ein leerer Platzhalter ('', '---------') ist, nehmen wir den zweiten.
        if theme_choices and theme_choices[0][0] == '':
            self.valid_theme = theme_choices[1][0] if len(theme_choices) > 1 else ''
        else:
            self.valid_theme = theme_choices[0][0] if theme_choices else ''

    def test_toeb_unit_form_happy_path(self):
        """Prüft, ob das Formular valide ist, wenn der User zur selben Orga gehört und TÖB-Reporter ist."""
        form_data = {
            "organization": self.orga_a.id,
            "name": "Umweltamt Kommune A",
            "theme": self.valid_theme,  # Dynamisch ermittelter, gültiger Choice-Wert
            "editors": [self.user_valid.id],
            "public": True
        }
        
        form = ToebUnitCreateForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_toeb_unit_form_fails_with_editor_from_different_organization(self):
        """Das Formular muss fehlschlagen, wenn ein Bearbeiter zu einer anderen Organisation gehört."""
        form_data = {
            "organization": self.orga_a.id,
            "name": "Klima-Stelle",
            "theme": self.valid_theme,
            "editors": [self.user_wrong_orga.id],  # Gehört zu orga_b!
            "public": True
        }
        
        form = ToebUnitCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Prüft, ob die spezifische Fehlermeldung aus deiner clean()-Methode im Formular auftaucht
        self.assertIn(
            "Alle Sachbearbeiter müssen zur gleichen Organisation gehören.", 
            form.non_field_errors()
        )

    def test_toeb_unit_form_fails_when_editor_is_not_toeb_reporter(self):
        """Das Formular muss fehlschlagen, wenn der User in der Orga ist, aber das Reporter-Flag fehlt."""
        form_data = {
            "organization": self.orga_a.id,
            "name": "Forstverwaltung",
            "theme": self.valid_theme,
            "editors": [self.user_no_role.id],  # In Orga A, aber is_toeb_reporter=False!
            "public": True
        }
        
        form = ToebUnitCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        self.assertIn(
            "Alle Sachbearbeiter müssen TOEB-Reporter sein.", 
            form.non_field_errors()
        )
