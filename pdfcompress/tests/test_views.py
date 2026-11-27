import uuid
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from pdfcompress.models import PdfJob

from .helpers import PDF_BYTES, PdfTestCase


class CompressViewTests(PdfTestCase):
    url = property(lambda self: reverse("pdfcompress:compress"))

    def upload(self, content=PDF_BYTES, name="Bebauungsplan.pdf"):
        return self.client.post(
            self.url,
            {"file": SimpleUploadedFile(name, content), "quality": "screen"},
        )

    def test_anonymous_is_redirected_and_creates_nothing(self):
        for response in (self.client.get(self.url), self.upload()):
            self.assertEqual(response.status_code, 302)
            self.assertIn("login", response.url)
        self.assertFalse(PdfJob.objects.exists())

    def test_get_renders_form_in_project_layout(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "pdfcompress/compress.html")
        self.assertTemplateUsed(response, "xplanung_light/layout.html")
        self.assertContains(response, 'id="pdf-form"')

    def test_menu_entry_is_below_tools_for_logged_in_users(self):
        self.client.force_login(self.user)  # ohne besondere Rolle
        html = self.client.get(self.url).content.decode()
        menu = html[html.index('aria-labelledby="navbarDropdownTools"') :]
        menu = menu[: menu.index("</ul>")]
        self.assertIn(f'href="{self.url}">PDF komprimieren</a>', menu)
        self.assertEqual(html.count(f'href="{self.url}"'), 1)

    def test_tools_menu_is_hidden_for_anonymous_users(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "navbarDropdownTools")
        self.assertNotContains(response, "PDF komprimieren")

    def test_upload_creates_job_and_queues_task_after_commit(self):
        self.client.force_login(self.user)
        with patch("pdfcompress.views.async_task") as task:
            with self.captureOnCommitCallbacks() as callbacks:
                response = self.upload()
            task.assert_not_called()  # erst nach dem Commit
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        job = PdfJob.objects.get()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json()["status_url"],
            reverse("pdfcompress:status", args=[job.pk]),
        )
        self.assertEqual(job.owner, self.user)
        self.assertEqual(job.original_name, "Bebauungsplan.pdf")
        self.assertEqual(job.input_size, len(PDF_BYTES))
        self.assertEqual(job.quality, "screen")
        self.assertEqual(job.status, PdfJob.Status.PENDING)
        # Nutzername der Datei darf nicht im Speicherpfad auftauchen
        self.assertEqual(job.input_file.name, f"pdfcompress/{job.pk}/input.pdf")
        self.assertEqual(Path(job.input_file.path).read_bytes(), PDF_BYTES)
        task.assert_called_once_with(
            "pdfcompress.tasks.compress_pdf", str(job.pk), timeout=630
        )

    @override_settings(PDFCOMPRESS_TIMEOUT=100)
    def test_task_timeout_exceeds_ghostscript_timeout(self):
        self.client.force_login(self.user)
        with patch("pdfcompress.views.async_task") as task:
            with self.captureOnCommitCallbacks(execute=True):
                self.upload()
        self.assertEqual(task.call_args.kwargs["timeout"], 130)

    def test_invalid_upload_returns_errors(self):
        self.client.force_login(self.user)
        with patch("pdfcompress.views.async_task") as task:
            response = self.upload(b"hallo")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"], ["Das ist keine PDF-Datei."])
        self.assertFalse(PdfJob.objects.exists())
        task.assert_not_called()

    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, {"quality": "ebook"})
        self.assertEqual(response.status_code, 403)


class StatusAndDownloadTests(PdfTestCase):
    def url(self, name, job):
        return reverse(f"pdfcompress:{name}", args=[job.pk])

    def done_job(self, **kwargs):
        job = self.make_job(
            status=PdfJob.Status.DONE, progress=100, output_size=7, **kwargs
        )
        output = Path(job.input_file.path).with_name("output.pdf")
        output.write_bytes(b"%PDF-ok")
        job.output_file = f"pdfcompress/{job.pk}/output.pdf"
        job.save()
        return job

    def test_running_status(self):
        job = self.make_job(status=PdfJob.Status.RUNNING, progress=42)
        self.client.force_login(self.user)
        response = self.client.get(self.url("status", job))
        self.assertEqual(
            response.json(),
            {
                "status": "running",
                "label": "Wird komprimiert",
                "progress": 42,
                "error": "",
            },
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_done_status_contains_sizes_and_link(self):
        job = self.done_job()
        self.client.force_login(self.user)
        data = self.client.get(self.url("status", job)).json()
        self.assertEqual(data["input_size"], job.input_size)
        self.assertEqual(data["output_size"], 7)
        self.assertEqual(data["download_url"], self.url("download", job))

    def test_download(self):
        job = self.done_job(original_name="Plan Süd.pdf")
        self.client.force_login(self.user)
        response = self.client.get(self.url("download", job))
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-ok")
        disposition = response["Content-Disposition"]
        self.assertTrue(disposition.startswith("attachment"))
        self.assertIn("Plan%20S%C3%BCd_komprimiert.pdf", disposition)

    def test_download_unavailable_unless_done(self):
        self.client.force_login(self.user)
        for status in ("pending", "running", "failed"):
            with self.subTest(status=status):
                job = self.make_job(status=status)
                response = self.client.get(self.url("download", job))
                self.assertEqual(response.status_code, 404)

    def test_other_users_get_404_even_superusers(self):
        job = self.done_job()
        users = get_user_model().objects
        for other in (
            users.create_user("bert"),
            users.create_superuser("admin", "a@example.com", "x"),
        ):
            self.client.force_login(other)
            for name in ("status", "download"):
                with self.subTest(user=other.username, view=name):
                    response = self.client.get(self.url(name, job))
                    self.assertEqual(response.status_code, 404)

    def test_anonymous_is_redirected(self):
        job = self.done_job()
        for name in ("status", "download"):
            self.assertEqual(self.client.get(self.url(name, job)).status_code, 302)

    def test_unknown_job(self):
        self.client.force_login(self.user)
        url = reverse("pdfcompress:status", args=[uuid.uuid4()])
        self.assertEqual(self.client.get(url).status_code, 404)
