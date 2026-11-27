from django.urls import path

from . import views

app_name = "pdfcompress"

urlpatterns = [
    path("", views.CompressView.as_view(), name="compress"),
    path("<uuid:pk>/status/", views.StatusView.as_view(), name="status"),
    path("<uuid:pk>/download/", views.DownloadView.as_view(), name="download"),
]
