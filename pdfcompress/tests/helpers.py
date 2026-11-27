import shutil
import sys
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from pdfcompress.models import PdfJob

PDF_BYTES = b"%PDF-1.4\n" + b"x" * 1000


class PdfTestCase(TestCase):
    """Eigenes MEDIA_ROOT je Test, damit nichts in uploads/ landet."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        overrides = override_settings(
            MEDIA_ROOT=str(self.tmp / "media"), CLAMD_ENABLED=False
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        self.user = get_user_model().objects.create_user("anna", password="geheim")

    def make_job(self, content=PDF_BYTES, **kwargs):
        kwargs.setdefault("owner", self.user)
        kwargs.setdefault("original_name", "plan.pdf")
        kwargs.setdefault("input_size", len(content))
        return PdfJob.objects.create(
            input_file=ContentFile(content, name="upload.pdf"), **kwargs
        )

    def fake_gs(self, body):
        """Ersetzt gs durch ein Python-Skript; `out` ist die Zieldatei."""
        script = self.tmp / "fake_gs"
        script.write_text(
            f"#!{sys.executable}\n"
            "import sys, time\n"
            "out = next(a.split('=', 1)[1] for a in sys.argv"
            " if a.startswith('-sOutputFile='))\n" + body
        )
        script.chmod(0o755)
        overrides = override_settings(GHOSTSCRIPT_BINARY=str(script))
        overrides.enable()
        self.addCleanup(overrides.disable)


def gs_output(pages=2, printed=None, size=10, returncode=0):
    """Skriptkörper für fake_gs im Ausgabeformat von Ghostscript."""
    printed = pages if printed is None else printed
    return (
        f"open(out, 'wb').write(b'y' * {size})\n"
        f"print('Processing pages 1 through {pages}.')\n"
        f"for n in range(1, {printed} + 1): print(f'Page {{n}}')\n"
        f"sys.exit({returncode})\n"
    )
