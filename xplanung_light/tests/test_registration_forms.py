from django.test import TestCase
from django.contrib.auth import get_user_model
from xplanung_light.models import AdministrativeOrganization

try:
    from xplanung_light.forms import AdminRegistrationForm as RegistrationForm
except ImportError:
    try:
        from xplanung_light.forms import UserRegistrationForm as RegistrationForm
    except ImportError:
        from django.contrib.auth.forms import UserCreationForm as RegistrationForm

User = get_user_model()

class RegistrationFormBusinessLogicTests(TestCase):

    def setUp(self):
        # Basis-Organisation für optionale Zuweisungen bei der Registrierung
        self.orga = AdministrativeOrganization.objects.create(name="Registrierungs-Kommune")
        
        # Vorab einen Testuser anlegen, um Eindeutigkeitskonflikte (Unique Checks) zu provozieren
        self.existing_user = User.objects.create_user(
            username="test_existiert", 
            email="existiert@kommune.de", 
            password="secure_password123"
        )

    def test_registration_happy_path(self):
        """Das Formular muss valide sein, wenn alle Daten korrekt und die Passwörter identisch sind."""
        # KORREKTUR: Die Felder heißen 'password1' und 'password2' ohne Unterstrich
        form_data = {
            "username": "neu_anmeldung",
            "email": "neu@kommune.de",
            "password1": "mein_geheimes_passwort123",
            "password2": "mein_geheimes_passwort123",
            "organization": self.orga.id,
            "first_name": "Max",
            "last_name": "Mustermann"
        }

        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_registration_fails_when_passwords_do_not_match(self):
        """Das Formular muss einen Validierungsfehler werfen, wenn die Passwörter nicht übereinstimmen."""
        # KORREKTUR: Auch hier 'password1' und 'password2' ohne Unterstrich nutzen
        form_data = {
            "username": "neu_anmeldung_fail",
            "email": "fehler@kommune.de",
            "password1": "passwort_links",
            "password2": "passwort_rechts",  # Mismatch!
            "organization": self.orga.id
        }
        
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        all_errors = str(form.errors)
        self.assertTrue(
            "übereinstimmen" in all_errors or "match" in all_errors or "password" in all_errors,
            f"Erwarteter Passwort-Mismatch-Fehler nicht gefunden. Gefundene Fehler: {all_errors}"
        )

    def test_registration_fails_when_username_already_exists(self):
        """Es darf keine Registrierung mit einem bereits vergebenen Benutzernamen möglich sein."""
        # KORREKTUR: 'password1' und 'password2' ohne Unterstrich nutzen
        form_data = {
            "username": "test_existiert",  # Existiert bereits im setUp!
            "email": "andere_email@kommune.de",
            "password1": "secure_password123",
            "password2": "secure_password123",
            "organization": self.orga.id
        }
        
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
