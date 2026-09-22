from django.test import TestCase
from django.apps import apps
from xplanung_light.models import AdministrativeOrganization
from xplanung_light.forms import AdministrativeOrganizationUpdateForm as OrganizationForm

class OrganizationFormBusinessLogicTests(TestCase):

    def setUp(self):
        # Lizenz-Modell dynamisch laden
        License = apps.get_model('xplanung_light', 'License')
        
        # Erstellen der Lizenzen
        self.license_alt = License.objects.create(
            identifier="DL-DE-BY-2.0",
            label="Datenlizenz Deutschland - Namensnennung - Version 2.0",
            url="https://govdata.de"
        )
        self.license_neu = License.objects.create(
            identifier="CC-BY-4.0",
            label="Creative Commons Attribution 4.0 International",
            url="https://creativecommons.org"
        )

        # KORREKTUR: Wir splitten den AGS "07316000" in die echten DB-Felder ls, ks, gs auf,
        # um den AttributeError beim schreibgeschützten property 'ags' zu umschiffen.
        self.orga = AdministrativeOrganization.objects.create(
            name="Musterstadt an der Weinstraße",
            ls="07",
            ks="316",
            gs="000",
            coat_of_arms_url="http://example.com",
            published_data_license=self.license_alt
        )

    def test_organization_update_form_happy_path(self):
        """Das Formular muss gültige administrative Metadaten erfolgreich entgegennehmen und aktualisieren."""
        form_data = {
            "coat_of_arms_url": "https://neustadt.de",
            "published_data_license": self.license_neu.id,
            "published_data_license_source_note": "Quellenvermerk Stadt Neustadt",
            "published_data_accessrights": "public",
            "published_data_rights": "Keine Einschränkungen"
        }
        
        form = OrganizationForm(data=form_data, instance=self.orga)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        saved_orga = form.save()
        self.assertEqual(saved_orga.coat_of_arms_url, "https://neustadt.de")
        self.assertEqual(saved_orga.published_data_license.id, self.license_neu.id)

    def test_organization_update_form_fails_with_invalid_url(self):
        """Das Formular muss fehlschlagen, wenn eine ungültige URL für das Wappen übergeben wird."""
        form_data = {
            "coat_of_arms_url": "gar-keine-echte-url-adresse",  # Verletzt den URLField-Validator
            "published_data_license": self.license_neu.id
        }
        
        form = OrganizationForm(data=form_data, instance=self.orga)
        self.assertFalse(form.is_valid())
        self.assertIn("coat_of_arms_url", form.errors)


