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
        return {
            "name": name,
            "typ": "1000",
        }

    def test_bplan_attachment_accepts_clean_file(self):
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
        form = BPlanBeteiligungBeitragAnhangForm(data=self._form_data())
        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_fplan_attachment_requires_a_file(self):
        form = FPlanBeteiligungBeitragAnhangForm(data=self._form_data())
        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_bplan_attachment_collection_allows_at_most_four_attachments(self):
        self.assertEqual(BPlanBeteiligungBeitragAnhangCollection.max_siblings, 4)
        self.assertEqual(BPlanBeteiligungBeitragAnhangCollection.min_siblings, 0)

    def test_fplan_attachment_collection_allows_at_most_four_attachments(self):
        self.assertEqual(FPlanBeteiligungBeitragAnhangCollection.max_siblings, 4)
        self.assertEqual(FPlanBeteiligungBeitragAnhangCollection.min_siblings, 0)
