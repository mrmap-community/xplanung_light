"""Tests der Validierung im Formular für TÖB-Einheiten."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from xplanung_light.forms import ToebUnitCreateForm
from xplanung_light.models import AdministrativeOrganization, AdminOrgaUser, ToebUnit

User = get_user_model()


class ToebUnitFormValidationTests(TestCase):
    """Editoren einer TÖB-Einheit müssen zur selben Organisation gehören und TÖB-Reporter sein."""

    def setUp(self):
        # Zwei getrennte Organisationen (Kommunen)
        self.orga_a = AdministrativeOrganization.objects.create(name="Kommune A")
        self.orga_b = AdministrativeOrganization.objects.create(name="Kommune B")

        self.user_valid = User.objects.create_user(
            username="reporter_a", password="password123")
        self.user_wrong_orga = User.objects.create_user(
            username="reporter_b", password="password123")
        self.user_no_role = User.objects.create_user(
            username="sachbearbeiter_a", password="password123")

        # Rollen und Organisationen über das AdminOrgaUser-Zwischenmodell.
        # editors ist eine ManyToMany-Beziehung auf AdminOrgaUser, nicht auf User -
        # im Formular wird also die Nummer dieses Eintrags übermittelt. Wer hier die
        # User-Nummer postet, läuft nur auf Spatialite durch, wo beide Tabellen
        # zufällig dieselben Nummern vergeben; auf PostgreSQL driften die Zähler über
        # die Suite hinweg (Sequenzen werden nicht zurückgerollt) und der Eintrag
        # fehlt oder gehört jemand anderem.
        self.eintrag_valid = AdminOrgaUser.objects.create(
            organization=self.orga_a, user=self.user_valid, is_toeb_reporter=True)
        self.eintrag_fremde_orga = AdminOrgaUser.objects.create(
            organization=self.orga_b, user=self.user_wrong_orga, is_toeb_reporter=True)
        self.eintrag_ohne_rolle = AdminOrgaUser.objects.create(
            organization=self.orga_a, user=self.user_no_role, is_toeb_reporter=False)

    def daten(self, **anderungen):
        """Formulardaten mit gültigen Werten; im Test gezielt zu verändern."""
        daten = {
            "organization": self.orga_a.pk,
            "name": "Umweltamt Kommune A",
            "theme": ToebUnit.OTH,
            "editors": [self.eintrag_valid.pk],
            "public": True,
        }
        daten.update(anderungen)
        return daten

    def test_toeb_unit_form_happy_path(self):
        """
        Was wird geprüft:
            Das Formular mit einem Sachbearbeiter aus derselben Organisation,
            der TÖB-Reporter ist.

        Erwartung:
            Das Formular ist gültig.
        """
        form = ToebUnitCreateForm(data=self.daten())
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_toeb_unit_form_fails_with_editor_from_different_organization(self):
        """
        Was wird geprüft:
            Ein Sachbearbeiter aus einer anderen Organisation.

        Erwartung:
            Ungültig, mit der Meldung aus clean() als Fehler übers Feld. Wäre der
            Editor nur auf User-Ebene falsch gesetzt, erschiene eine
            Auswahlmeldung am Feld selbst statt dieser Meldung - deshalb wird hier
            die Nummer des AdminOrgaUser-Eintrags übermittelt.
        """
        form = ToebUnitCreateForm(data=self.daten(
            name="Klima-Stelle", editors=[self.eintrag_fremde_orga.pk]))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Alle Sachbearbeiter müssen zur gleichen Organisation gehören.",
            form.non_field_errors())

    def test_toeb_unit_form_fails_when_editor_is_not_toeb_reporter(self):
        """
        Was wird geprüft:
            Ein Sachbearbeiter aus derselben Organisation, aber ohne
            Reporter-Rolle.

        Erwartung:
            Ungültig mit der Reporter-Meldung übers Feld.
        """
        form = ToebUnitCreateForm(data=self.daten(
            name="Forstverwaltung", editors=[self.eintrag_ohne_rolle.pk]))
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Alle Sachbearbeiter müssen TOEB-Reporter sein.",
            form.non_field_errors())

    def test_theme_aus_der_auswahlliste_des_formulars_wird_accepted(self):
        """
        Was wird geprüft:
            Das theme aus der Auswahlliste des leeren Formularfelds - der erste
            Eintrag ist der leere Platzhalter, danach kommt ein echter Code.

        Warum:
            theme ist ein CharField mit choices und max_length=5. Die ganze Liste
            der Auswahlmöglichkeiten (kein Wert) geht nur auf Spatialite in die
            Spalte; hier wird geprüft, dass ein echter Code aus der Liste akzeptiert
            wird, wie es die anderen Tests auch halten.

        Erwartung:
            Mit einem Code aus der Liste ist das Formular gültig; mit der Liste
            selbst scheitert die Feldprüfung.
        """
        auswahl = ToebUnitCreateForm().fields["theme"].choices
        codes = [wert for wert, _ in auswahl if wert]
        self.assertTrue(codes, "das theme-Feld muss mindestens einen Code führen")

        self.assertTrue(ToebUnitCreateForm(
            data=self.daten(theme=codes[0])).is_valid())
        form = ToebUnitCreateForm(data=self.daten(theme=auswahl))
        self.assertFalse(form.is_valid())
        self.assertIn("theme", form.errors)
