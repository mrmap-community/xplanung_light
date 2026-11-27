import uuid

from django.conf import settings
from django.db import models


def input_path(job, filename):
    return f"pdfcompress/{job.pk}/input.pdf"


class PdfJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Wartet"
        RUNNING = "running", "Wird komprimiert"
        DONE = "done", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    class Quality(models.TextChoices):
        SCREEN = "screen", "Klein (72 dpi)"
        EBOOK = "ebook", "Mittel (150 dpi)"
        PRINTER = "printer", "Druck (300 dpi)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.CASCADE)
    original_name = models.CharField(max_length=255)
    input_file = models.FileField(upload_to=input_path)
    output_file = models.FileField(blank=True)
    # Für django 4.2 und 5.x
    quality = models.CharField(
        max_length=10, choices=Quality.choices, default=Quality.EBOOK)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING)
    # quality = models.CharField(max_length=10, choices=Quality, default=Quality.EBOOK)
    # status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    input_size = models.PositiveBigIntegerField(default=0)
    output_size = models.PositiveBigIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
