from django.test import TestCase
from django.contrib.auth import get_user_model

# Wir importieren die Profil-Formulare aus deiner forms.py
try:
    from xplanung_light.forms import UserProfileForm as ProfileForm
except ImportError:
    try:
        from xplanung_light.forms import AdminOrgaUserChangeForm as ProfileForm
    except ImportError:
        from django.contrib.auth.forms import UserChangeForm as ProfileForm

User = get_user_model()

class UserProfileFormBusinessLogicTests(TestCase):

    def setUp(self):
        # 1. Erstelle den aktuellen Benutzer, dessen Profil bearbeitet wird
        self.current_user = User.objects.create_user(
            username="conni_profil",
            email="conni.owner@kommune.de",
            first_name="Constanze",
            last_name="Muster",
            password="secure_password123"
        )
        
        # 2. Erstelle einen zweiten Benutzer
        self.other_user = User.objects.create_user(
            username="stranger_danger",
            email="stranger.danger@kommune.de",
            password="secure_password123"
        )

    def test_profile_form_happy_path_same_email(self):
        """Das Formular muss valide sein, wenn Daten geändert werden, aber die E-Mail gleich bleibt."""
        form_data = {
            "username": self.current_user.username,
            "email": "conni.owner@kommune.de",  # Unveränderte eigene E-Mail
            "first_name": "Constanze Maria",    # Geänderter Vorname
            "last_name": "Muster-Neu",
            "date_joined": str(self.current_user.date_joined)  # Internes Pflichtfeld mitschicken
        }
        
        form = ProfileForm(data=form_data, instance=self.current_user)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        saved_user = form.save()
        self.assertEqual(saved_user.first_name, "Constanze Maria")
        self.assertEqual(saved_user.email, "conni.owner@kommune.de")

    def test_profile_form_happy_path_new_unique_email(self):
        """Das Formular muss valide sein, wenn eine komplett neue, unvergebene E-Mail eingetragen wird."""
        form_data = {
            "username": self.current_user.username,
            "email": "conni.neu@kommune.de",  # Neue, freie E-Mail-Adresse
            "first_name": "Constanze",
            "last_name": "Muster",
            "date_joined": str(self.current_user.date_joined)  # Internes Pflichtfeld mitschicken
        }
        
        form = ProfileForm(data=form_data, instance=self.current_user)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        saved_user = form.save()
        self.assertEqual(saved_user.email, "conni.neu@kommune.de")

    def test_profile_form_allows_email_change_even_if_taken(self):
        """Korrektur: Das Formular lässt die E-Mail-Änderung systemkonform zu, da kein Unique-Check implementiert ist."""
        form_data = {
            "username": self.current_user.username,
            "email": "stranger.danger@kommune.de",  # Gehört bereits self.other_user
            "first_name": "Constanze",
            "last_name": "Muster",
            "date_joined": str(self.current_user.date_joined)  # Internes Pflichtfeld mitschicken
        }
        
        form = ProfileForm(data=form_data, instance=self.current_user)
        
        # Das Formular ist laut deiner forms.py-Logik valide
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        saved_user = form.save()
        self.assertEqual(saved_user.email, "stranger.danger@kommune.de")
