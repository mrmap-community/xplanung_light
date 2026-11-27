import logging
import re
import shutil
import subprocess
import threading
from collections import deque
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import PdfJob

logger = logging.getLogger(__name__)

# Ghostscript meldet ohne -q: "Processing pages 1 through 12." und dann "Page 1", ...
TOTAL_RE = re.compile(r"^Processing pages (\d+) through (\d+)\.")
PAGE_RE = re.compile(r"^Page \d+")


def compress_pdf(job_id):
    # Atomar von PENDING auf RUNNING: verhindert doppelte Ausführung bei Retries
    claimed = PdfJob.objects.filter(pk=job_id, status=PdfJob.Status.PENDING).update(
        status=PdfJob.Status.RUNNING
    )
    if not claimed:
        return
    job = PdfJob.objects.get(pk=job_id)
    qs = PdfJob.objects.filter(pk=job_id)
    src = Path(job.input_file.path)
    dst = src.with_name("output.pdf")

    try:
        _run_ghostscript(src, dst, job.quality, qs)
        output_name = str(Path(job.input_file.name).with_name("output.pdf"))
        # Schon optimierte PDFs können größer werden -> dann Original ausliefern
        if dst.stat().st_size >= job.input_size:
            dst.unlink()
            output_name = job.input_file.name
            output_size = job.input_size
        else:
            output_size = dst.stat().st_size
        qs.update(
            status=PdfJob.Status.DONE,
            progress=100,
            output_file=output_name,
            output_size=output_size,
        )
    except Exception as exc:
        logger.exception("PDF-Komprimierung fehlgeschlagen: %s", job_id)
        dst.unlink(missing_ok=True)
        # Dem Nutzer keine Serverpfade zeigen; Details stehen im Log
        message = str(exc) if isinstance(exc, CompressionError) else "Interner Fehler."
        qs.update(status=PdfJob.Status.FAILED, error=message)


class CompressionError(Exception):
    pass


def _run_ghostscript(src, dst, quality, qs):
    cmd = [
        getattr(settings, "GHOSTSCRIPT_BINARY", "gs"),
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS=/{quality}",
        f"-sOutputFile={dst}",
        str(src),
    ]
    timeout = getattr(settings, "PDFCOMPRESS_TIMEOUT", 600)
    timed_out = threading.Event()
    tail = deque(maxlen=20)  # letzte Zeilen fürs Log
    total = done = last = 0

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # eine Pipe -> kein Deadlock
        text=True,
        errors="replace",
        bufsize=1,
    ) as proc:

        def kill():
            timed_out.set()
            proc.kill()

        # Watchdog: greift auch, wenn gs hängt und nichts mehr ausgibt
        watchdog = threading.Timer(timeout, kill)
        watchdog.start()
        try:
            for line in proc.stdout:
                tail.append(line.rstrip())
                if match := TOTAL_RE.match(line):
                    total = int(match[2]) - int(match[1]) + 1
                elif total and PAGE_RE.match(line):
                    done += 1
                    # "Page n" kommt zu Beginn der Seite; 100 % erst nach Exit
                    percent = min(99, (done - 1) * 100 // total)
                    if percent > last:  # max. ~100 DB-Writes pro Job
                        last = percent
                        qs.update(progress=percent)
            returncode = proc.wait()
        finally:
            watchdog.cancel()
            if proc.poll() is None:
                proc.kill()

    if timed_out.is_set():
        raise CompressionError("Zeitlimit überschritten.")
    # gs liefert bei manchen kaputten/verschlüsselten PDFs trotzdem Exit-Code 0
    if returncode != 0 or not total or done < total or not dst.exists():
        logger.error("Ghostscript (rc=%s):\n%s", returncode, "\n".join(tail))
        raise CompressionError("Die PDF-Datei ist beschädigt oder passwortgeschützt.")


def cleanup_old_jobs(hours=24):
    """Als django-q2-Schedule einplanen (z. B. stündlich)."""
    limit = timezone.now() - timedelta(hours=hours)
    for job in PdfJob.objects.filter(created__lt=limit):
        # Jeder Job hat ein eigenes Verzeichnis: komplett entfernen, inklusive
        # Resten eines abgebrochenen Workers. Schlägt das fehl, bleibt der
        # Datensatz erhalten und der nächste Lauf versucht es erneut.
        directory = default_storage.path(f"pdfcompress/{job.pk}")
        try:
            shutil.rmtree(directory)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Aufräumen fehlgeschlagen: %s", directory)
            continue
        job.delete()
