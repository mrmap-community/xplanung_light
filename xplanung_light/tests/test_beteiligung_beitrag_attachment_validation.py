"""
Tests der Formulare für Anlagen zu Beteiligungsbeiträgen (BPlan und FPlan): unbedenkliche
Dateien, Virenfund, Pflichtfeld und Höchstzahl der Anlagen.
"""

from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from xplanung_light.forms import (
    BPlanBeteiligungBeitragAnhangCollection,
    BPlanBeteiligungBeitragAnhangForm,
    FPlanBeteiligungBeitragAnhangCollection,
    FPlanBeteiligungBeitragAnhangForm,
)


class BeteiligungBeitragAttachmentValidation(SimpleTestCase):
    """Tests für die als Anlage zu einem Beteiligungsbeitrag möglichen Dateien."""

    def _force_infected_validator(self, form):
        """Ersetzt den bereits am Attachment-Feld registrierten
        Infektions-Validator durch einen kontrolliert fehlschlagenden
        Validator. Damit ist der Test unabhängig von einem lokalen
        ClamAV/clamd-Dienst.
        """
        validators = list(form.fields["attachment"].validators)
        infection_validator_index = next(
            index
            for index, validator in enumerate(validators)
            if getattr(validator, "__name__", "") == "validate_file_infection"
        )
        validators[infection_validator_index] = Mock(
            side_effect=ValidationError("Datei ist infiziert")
        )
        form.fields["attachment"].validators = validators

    def _form_data(self, name="Anlage"):
        """Liefert die Textfelder des Anlagenformulars: Name und Typ 1000."""
        return {
            "name": name,
            "typ": "1000",
        }

    def test_bplan_attachment_accepts_clean_file(self):
        """
        Was wird geprüft:
            Eine unbedenkliche Textdatei im BPlan-Anlagenformular.

        Warum:
            Der Normalfall muss das Formular bestehen.

        Erwartung:
            Das Formular ist gültig und der Dateiname bleibt erhalten.
        """
        upload = SimpleUploadedFile(
            "stellungnahme.txt",
            b"Unbedenklicher Inhalt",
            content_type="text/plain",
        )
        form = BPlanBeteiligungBeitragAnhangForm(
            data=self._form_data(),
            files={"attachment": upload},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["attachment"].name, "stellungnahme.txt")

    def test_bplan_attachment_rejects_infected_file(self):
        """
        Was wird geprüft:
            Eine Datei mit EICAR-Testmuster im BPlan-Formular; der Infektions-Validator wird
            gezielt durch einen ersetzt, der immer meldet, die Datei sei infiziert.

        Warum:
            Infizierte Dateien dürfen nicht angenommen werden. Der Test braucht dadurch
            keinen laufenden Virenscanner.

        Erwartung:
            Das Formular ist ungültig und der Fehler hängt am Feld attachment.
        """
        upload = SimpleUploadedFile(
            "eicar_test.txt",
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-TEST",
            content_type="text/plain",
        )
        form = BPlanBeteiligungBeitragAnhangForm(
            data=self._form_data("Infizierte BPlan-Anlage"),
            files={"attachment": upload},
        )
        self._force_infected_validator(form)

        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_fplan_attachment_accepts_clean_file(self):
        """
        Was wird geprüft:
            Dieselbe unbedenkliche Datei im FPlan-Formular.

        Erwartung:
            Das Formular ist gültig und der Dateiname bleibt erhalten.
        """
        upload = SimpleUploadedFile(
            "karte.txt",
            b"Unbedenklicher Inhalt",
            content_type="text/plain",
        )
        form = FPlanBeteiligungBeitragAnhangForm(
            data=self._form_data(),
            files={"attachment": upload},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["attachment"].name, "karte.txt")

    def test_fplan_attachment_rejects_infected_file(self):
        """
        Was wird geprüft:
            Der Virenfund im FPlan-Formular.

        Erwartung:
            Das Formular ist ungültig und der Fehler hängt am Feld attachment.
        """
        upload = SimpleUploadedFile(
            "eicar_test.txt",
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-TEST",
            content_type="text/plain",
        )
        form = FPlanBeteiligungBeitragAnhangForm(
            data=self._form_data("Infizierte FPlan-Anlage"),
            files={"attachment": upload},
        )
        self._force_infected_validator(form)

        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_bplan_attachment_requires_a_file(self):
        """
        Was wird geprüft:
            Das BPlan-Formular ohne Datei.

        Warum:
            Eine Anlage ohne Datei ergibt keinen Sinn.

        Erwartung:
            Das Formular ist ungültig; der Fehler hängt am Feld attachment.
        """
        form = BPlanBeteiligungBeitragAnhangForm(data=self._form_data())
        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_fplan_attachment_requires_a_file(self):
        """
        Was wird geprüft:
            Das FPlan-Formular ohne Datei.

        Erwartung:
            Das Formular ist ungültig; der Fehler hängt am Feld attachment.
        """
        form = FPlanBeteiligungBeitragAnhangForm(data=self._form_data())
        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_bplan_attachment_collection_allows_at_most_four_attachments(self):
        """
        Was wird geprüft:
            Die Anlagen-Sammlung des BPlan-Beitragsformulars.

        Warum:
            Die Zahl der Anlagen pro Beitrag ist auf vier begrenzt.

        Erwartung:
            max_siblings ist 4 und min_siblings ist 0.
        """
        self.assertEqual(BPlanBeteiligungBeitragAnhangCollection.max_siblings, 4)
        self.assertEqual(BPlanBeteiligungBeitragAnhangCollection.min_siblings, 0)

    def test_fplan_attachment_collection_allows_at_most_four_attachments(self):
        """
        Was wird geprüft:
            Dieselbe Grenze für das FPlan-Formular.

        Erwartung:
            max_siblings ist 4 und min_siblings ist 0.
        """
        self.assertEqual(FPlanBeteiligungBeitragAnhangCollection.max_siblings, 4)
        self.assertEqual(FPlanBeteiligungBeitragAnhangCollection.min_siblings, 0)
