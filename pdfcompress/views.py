from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import FormView
from django_q.tasks import async_task

from .forms import PdfUploadForm
from .models import PdfJob


class OwnJobMixin(LoginRequiredMixin):
    def get_job(self, pk):
        # Fremde Jobs -> 404
        return get_object_or_404(PdfJob, pk=pk, owner=self.request.user)


class CompressView(LoginRequiredMixin, FormView):
    template_name = "pdfcompress/compress.html"
    form_class = PdfUploadForm

    def form_valid(self, form):
        f = form.cleaned_data["file"]
        job = PdfJob.objects.create(
            owner=self.request.user,
            original_name=Path(f.name).name[:255],
            input_file=f,
            input_size=f.size,
            quality=form.cleaned_data["quality"],
        )
        timeout = getattr(settings, "PDFCOMPRESS_TIMEOUT", 600)
        # on_commit: Worker sieht den Job auch bei ATOMIC_REQUESTS=True
        transaction.on_commit(
            lambda: async_task(
                "pdfcompress.tasks.compress_pdf",
                str(job.pk),
                timeout=timeout + 30,  # unser Watchdog greift zuerst
            )
        )
        return JsonResponse(
            {"status_url": reverse("pdfcompress:status", args=[job.pk])}, status=202
        )

    def form_invalid(self, form):
        errors = [e for field in form.errors.values() for e in field]
        return JsonResponse({"errors": errors}, status=400)


class StatusView(OwnJobMixin, View):
    def get(self, request, pk):
        job = self.get_job(pk)
        data = {
            "status": job.status,
            "label": job.get_status_display(),
            "progress": job.progress,
            "error": job.error,
        }
        if job.status == PdfJob.Status.DONE:
            data |= {
                "input_size": job.input_size,
                "output_size": job.output_size,
                "download_url": reverse("pdfcompress:download", args=[job.pk]),
            }
        response = JsonResponse(data)
        response["Cache-Control"] = "no-store"
        return response


class DownloadView(OwnJobMixin, View):
    def get(self, request, pk):
        job = self.get_job(pk)
        if job.status != PdfJob.Status.DONE:
            raise Http404
        name = f"{Path(job.original_name).stem}_komprimiert.pdf"
        return FileResponse(
            job.output_file.open("rb"), as_attachment=True, filename=name
        )
