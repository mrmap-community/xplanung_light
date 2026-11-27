from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from pdfcompress.forms import PdfUploadForm

from .helpers import PDF_BYTES


@override_settings(CLAMD_ENABLED=False)
class PdfUploadFormTests(SimpleTestCase):
    def form(self, content=PDF_BYTES, quality="ebook"):
        upload = SimpleUploadedFile("a.pdf", content, "application/pdf")
        return PdfUploadForm({"quality": quality}, {"file": upload})

    def test_valid_pdf_is_rewound(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["file"].read(), PDF_BYTES)

    def test_rejects_non_pdf(self):
        form = self.form(b"PK\x03\x04 kein pdf")
        self.assertFalse(form.is_valid())
        self.assertIn("keine PDF-Datei", form.errors["file"][0])

    def test_rejects_empty_file(self):
        self.assertIn("file", self.form(b"").errors)

    def test_rejects_unknown_quality(self):
        # Der Wert landet im gs-Aufruf: nur die Auswahlwerte sind erlaubt
        self.assertIn("quality", self.form(quality="ebook -dNOSAFER").errors)

    @override_settings(PDFCOMPRESS_MAX_SIZE=len(PDF_BYTES))
    def test_size_limit_is_inclusive(self):
        self.assertTrue(self.form().is_valid())

    @override_settings(PDFCOMPRESS_MAX_SIZE=len(PDF_BYTES) - 1)
    def test_rejects_too_large_file(self):
        self.assertIn("größer", self.form().errors["file"][0])

    def test_virus_scanner_rejects_file(self):
        field = PdfUploadForm.base_fields["file"]

        def infected(value):
            raise ValidationError("infiziert")

        with patch.object(field, "validators", [infected]):
            self.assertEqual(self.form().errors["file"], ["infiziert"])

    def test_virus_scanner_is_configured(self):
        from django_clamd.validators import validate_file_infection

        self.assertIn(
            validate_file_infection, PdfUploadForm.base_fields["file"].validators
        )
