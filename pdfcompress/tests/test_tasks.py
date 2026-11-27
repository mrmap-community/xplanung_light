import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.test import override_settings
from django.utils import timezone
from django_q.models import Schedule

from pdfcompress import tasks
from pdfcompress.models import PdfJob

from .helpers import PdfTestCase, gs_output

LOGGER = "pdfcompress.tasks"


class CompressTaskTests(PdfTestCase):
    def run_task(self, job):
        tasks.compress_pdf(str(job.pk))
        job.refresh_from_db()
        return job

    def output_path(self, job):
        return Path(job.input_file.path).with_name("output.pdf")

    def assert_failed(self, job, message):
        with self.assertLogs(LOGGER, "ERROR"):
            self.run_task(job)
        self.assertEqual(job.status, PdfJob.Status.FAILED)
        self.assertIn(message, job.error)
        self.assertFalse(job.output_file)
        self.assertFalse(self.output_path(job).exists())

    def test_success(self):
        self.fake_gs(gs_output(size=10))
        job = self.run_task(self.make_job())
        self.assertEqual(job.status, PdfJob.Status.DONE)
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.output_size, 10)
        self.assertEqual(job.output_file.name, f"pdfcompress/{job.pk}/output.pdf")

    def test_larger_output_falls_back_to_original(self):
        self.fake_gs(gs_output(size=5000))
        job = self.run_task(self.make_job())
        self.assertEqual(job.status, PdfJob.Status.DONE)
        self.assertEqual(job.output_file.name, job.input_file.name)
        self.assertEqual(job.output_size, job.input_size)
        self.assertFalse(self.output_path(job).exists())

    def test_command_uses_safer_mode_and_quality(self):
        self.fake_gs(gs_output())
        job = self.make_job(quality="screen")
        with patch.object(tasks.subprocess, "Popen", wraps=subprocess.Popen) as popen:
            self.run_task(job)
        cmd = popen.call_args.args[0]
        self.assertIn("-dSAFER", cmd)
        self.assertIn("-dPDFSETTINGS=/screen", cmd)
        self.assertEqual(cmd[-1], job.input_file.path)

    def test_only_pending_jobs_are_processed(self):
        for status in ("running", "done", "failed"):
            with self.subTest(status=status):
                job = self.make_job(status=status)
                with patch.object(tasks, "_run_ghostscript") as run:
                    self.run_task(job)
                run.assert_not_called()
                self.assertEqual(job.status, status)

    def test_unknown_job_is_ignored(self):
        with patch.object(tasks, "_run_ghostscript") as run:
            tasks.compress_pdf("00000000-0000-0000-0000-000000000000")
        run.assert_not_called()

    def test_nonzero_exit_code(self):
        self.fake_gs(gs_output(returncode=1))
        self.assert_failed(self.make_job(), "beschädigt")

    def test_missing_pages_despite_exit_code_zero(self):
        self.fake_gs(gs_output(pages=3, printed=1))
        self.assert_failed(self.make_job(), "beschädigt")

    def test_no_page_information(self):
        self.fake_gs("open(out, 'wb').write(b'y')\n")
        self.assert_failed(self.make_job(), "beschädigt")

    def test_no_output_file(self):
        self.fake_gs("print('Processing pages 1 through 1.')\nprint('Page 1')\n")
        self.assert_failed(self.make_job(), "beschädigt")

    @override_settings(PDFCOMPRESS_TIMEOUT=0.5)
    def test_timeout_kills_hanging_process(self):
        self.fake_gs("open(out, 'wb').write(b'y')\ntime.sleep(30)\n")
        start = timezone.now()
        self.assert_failed(self.make_job(), "Zeitlimit")
        self.assertLess(timezone.now() - start, timedelta(seconds=10))

    @override_settings(GHOSTSCRIPT_BINARY="/gibt/es/nicht")
    def test_internal_errors_do_not_leak_paths(self):
        job = self.make_job()
        self.assert_failed(job, "Interner Fehler.")
        self.assertNotIn("/gibt", job.error)

    def test_process_is_killed_if_progress_update_fails(self):
        self.fake_gs(
            "print('Processing pages 1 through 2.')\n"
            "print('Page 1')\nprint('Page 2', flush=True)\ntime.sleep(30)\n"
        )
        qs = Mock()
        qs.update.side_effect = RuntimeError("DB weg")
        start = timezone.now()
        with self.assertRaisesMessage(RuntimeError, "DB weg"):
            tasks._run_ghostscript(
                self.tmp / "in.pdf", self.tmp / "out.pdf", "ebook", qs
            )
        self.assertLess(timezone.now() - start, timedelta(seconds=10))


class ProgressTests(PdfTestCase):
    def progress_for(self, body):
        self.fake_gs(body)
        qs = Mock()
        tasks._run_ghostscript(
            self.tmp / "in.pdf", self.tmp / "out.pdf", "ebook", qs
        )
        return [c.kwargs["progress"] for c in qs.update.call_args_list]

    def test_progress_per_page(self):
        self.assertEqual(self.progress_for(gs_output(pages=4)), [25, 50, 75])

    def test_database_writes_are_limited(self):
        values = self.progress_for(gs_output(pages=1000))
        self.assertEqual(values, list(range(1, 100)))

    def test_page_range_and_noise_in_output(self):
        body = (
            "open(out, 'wb').write(b'y')\n"
            "print('Page 99 vor dem Start wird ignoriert')\n"
            "print('Processing pages 3 through 4.')\n"
            "print('Page 3'); print('   **** Warning', file=sys.stderr)\n"
            "print('Page 4')\n"
        )
        self.assertEqual(self.progress_for(body), [50])


class CleanupTests(PdfTestCase):
    def age(self, job, hours):
        PdfJob.objects.filter(pk=job.pk).update(
            created=timezone.now() - timedelta(hours=hours)
        )

    def test_removes_only_old_jobs_and_their_files(self):
        old, new = self.make_job(), self.make_job()
        output = Path(old.input_file.path).with_name("output.pdf")
        output.write_bytes(b"y")
        old.output_file = f"pdfcompress/{old.pk}/output.pdf"
        old.save()
        self.age(old, 25)
        self.age(new, 23)

        tasks.cleanup_old_jobs()

        self.assertEqual(list(PdfJob.objects.all()), [new])
        self.assertFalse(output.exists())
        self.assertFalse(os.path.exists(old.input_file.path))
        self.assertTrue(os.path.exists(new.input_file.path))

    def test_original_used_as_output(self):
        job = self.make_job()
        job.output_file = job.input_file.name
        job.save()
        self.age(job, 25)
        tasks.cleanup_old_jobs()
        self.assertFalse(PdfJob.objects.exists())

    def test_custom_age_and_missing_file(self):
        job = self.make_job()
        os.remove(job.input_file.path)
        self.age(job, 2)
        tasks.cleanup_old_jobs(hours=1)
        self.assertFalse(PdfJob.objects.exists())

    def test_removes_job_directory_including_leftovers(self):
        old, new = self.make_job(), self.make_job()
        old_dir = Path(old.input_file.path).parent
        # Rest eines abgebrochenen Workers, in keinem Feld vermerkt
        (old_dir / "output.pdf").write_bytes(b"y")
        self.age(old, 25)

        tasks.cleanup_old_jobs()

        self.assertFalse(old_dir.exists())
        self.assertTrue(Path(new.input_file.path).exists())
        self.assertTrue(old_dir.parent.exists())

    def test_missing_directory(self):
        job = self.make_job()
        shutil.rmtree(Path(job.input_file.path).parent)
        self.age(job, 25)
        tasks.cleanup_old_jobs()
        self.assertFalse(PdfJob.objects.exists())

    def test_keeps_job_if_directory_cannot_be_removed(self):
        job = self.make_job()
        self.age(job, 25)
        with patch.object(tasks.shutil, "rmtree", side_effect=PermissionError):
            with self.assertLogs(LOGGER, "ERROR"):
                tasks.cleanup_old_jobs()
        self.assertTrue(PdfJob.objects.filter(pk=job.pk).exists())

    def test_migration_creates_hourly_schedule(self):
        schedule = Schedule.objects.get(name="pdfcompress-cleanup")
        self.assertEqual(schedule.func, "pdfcompress.tasks.cleanup_old_jobs")
        self.assertEqual(schedule.schedule_type, Schedule.HOURLY)
        self.assertEqual(schedule.repeats, -1)


@skipUnless(shutil.which("gs"), "Ghostscript ist nicht installiert")
class RealGhostscriptTests(PdfTestCase):
    """Sichert das Ausgabeformat der installierten Ghostscript-Version ab."""

    def make_pdf(self, *extra):
        path = self.tmp / "echt.pdf"
        subprocess.run(
            ["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite", *extra,
             "-o", str(path), "-c", "1 1 4 { pop showpage } for"],
            check=True,
        )
        return path.read_bytes()

    def test_compresses_valid_pdf(self):
        job = self.make_job(self.make_pdf())
        tasks.compress_pdf(str(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, PdfJob.Status.DONE, job.error)
        with job.output_file.open("rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")

    def test_reports_progress(self):
        src = self.tmp / "in.pdf"
        src.write_bytes(self.make_pdf())
        qs = Mock()
        tasks._run_ghostscript(src, self.tmp / "out.pdf", "ebook", qs)
        values = [c.kwargs["progress"] for c in qs.update.call_args_list]
        self.assertEqual(values, [25, 50, 75])

    def assert_rejected(self, content):
        job = self.make_job(content)
        with self.assertLogs(LOGGER, "ERROR"):
            tasks.compress_pdf(str(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, PdfJob.Status.FAILED)

    def test_rejects_broken_pdf(self):
        self.assert_rejected(b"%PDF-1.4\nkaputt")

    def test_rejects_password_protected_pdf(self):
        self.assert_rejected(self.make_pdf(
            "-sOwnerPassword=o", "-sUserPassword=u",
            "-dEncryptionR=3", "-dKeyLength=128",
        ))
