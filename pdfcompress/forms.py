from django import forms
from django.conf import settings
from django_clamd.validators import validate_file_infection

from .models import PdfJob


class PdfUploadForm(forms.Form):
    file = forms.FileField(
        label="PDF-Datei",
        validators=[validate_file_infection],  # wirkt bei CLAMD_ENABLED = True
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )
    quality = forms.ChoiceField(
        label="Qualität", choices=PdfJob.Quality.choices, initial=PdfJob.Quality.EBOOK
    )

    def clean_file(self):
        f = self.cleaned_data["file"]
        max_size = getattr(settings, "PDFCOMPRESS_MAX_SIZE", 100 * 1024 * 1024)
        if f.size > max_size:
            raise forms.ValidationError(f"Datei ist größer als {max_size // 1024**2} MB.")
        f.seek(0)
        header = f.read(5)
        f.seek(0)
        if header != b"%PDF-":
            raise forms.ValidationError("Das ist keine PDF-Datei.")
        return f
