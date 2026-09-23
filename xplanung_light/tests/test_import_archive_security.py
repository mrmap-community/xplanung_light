"""Security and robustness regression tests for ZIP/XPlan archive imports.

Focus:
- ZIP archive validation before the import helper is used
- exactly one GML document per archive
- archive must contain a GML document
- malformed ZIPs are rejected instead of being imported
- both BPlan and FPlan archive-import views enforce municipality-admin access
"""

import io
import zipfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import AdministrativeOrganization
from xplanung_light.validators import (
    bplan_upload_file_validator,
    fplan_upload_file_validator,
)


XPLAN_NS = "http://www.xplanung.de/xplangml/6/0"
GML_NS = "http://www.opengis.net/gml/3.2"
AGS = "07316000"
GEMEINDE_NAME = "Neustadt an der Weinstraße, kreisfreie Stadt"

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
  <gml:exterior>
    <gml:LinearRing>
      <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>
    </gml:LinearRing>
  </gml:exterior>
</gml:Polygon>"""


def make_plan_gml(name="ZIP-Security-Test", plan_tag="BP_Plan"):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<xplan:XPlanAuszug xmlns:xplan="{XPLAN_NS}" xmlns:gml="{GML_NS}">
  <gml:featureMember>
    <xplan:{plan_tag} gml:id="GML_testplan">
      <xplan:name>{name}</xplan:name>
      <xplan:nummer>9999</xplan:nummer>
      <xplan:raeumlicherGeltungsbereich>{GEOMETRIE}</xplan:raeumlicherGeltungsbereich>
      <xplan:gemeinde>
        <xplan:XP_Gemeinde>
          <xplan:ags>{AGS}</xplan:ags>
          <xplan:gemeindeName>{GEMEINDE_NAME}</xplan:gemeindeName>
        </xplan:XP_Gemeinde>
      </xplan:gemeinde>
      <xplan:planArt>1000</xplan:planArt>
    </xplan:{plan_tag}>
  </gml:featureMember>
</xplan:XPlanAuszug>
""".encode("utf-8")


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, data in files.items():
            archive.writestr(
                filename,
                data.encode("utf-8") if isinstance(data, str) else data,
            )
    return buffer.getvalue()


def upload_zip(files, name="archive.zip"):
    return SimpleUploadedFile(
        name,
        make_zip(files),
        content_type="application/zip",
    )


class ArchiveValidatorSecurityTests(TestCase):
    """The upload validators must reject structurally unsafe archives."""

    def setUp(self):
        AdministrativeOrganization.objects.get_or_create(
            ls="07",
            ks="316",
            gs="000",
            name=GEMEINDE_NAME,
        )

    def test_bplan_archive_requires_at_least_one_gml(self):
        upload = upload_zip({"readme.txt": b"no GML here"})

        with self.assertRaises(ValidationError):
            bplan_upload_file_validator(upload)

    def test_fplan_archive_requires_at_least_one_gml(self):
        upload = upload_zip({"readme.txt": b"no GML here"})

        with self.assertRaises(ValidationError):
            fplan_upload_file_validator(upload)

    def test_bplan_archive_rejects_multiple_gml_files(self):
        upload = upload_zip({
            "one.gml": make_plan_gml("one"),
            "two.gml": make_plan_gml("two"),
        })

        with self.assertRaises(ValidationError):
            bplan_upload_file_validator(upload)

    def test_fplan_archive_rejects_multiple_gml_files(self):
        upload = upload_zip({
            "one.gml": make_plan_gml("one", "FP_Plan"),
            "two.gml": make_plan_gml("two", "FP_Plan"),
        })

        with self.assertRaises(ValidationError):
            fplan_upload_file_validator(upload)

    def test_bplan_archive_with_valid_single_gml_is_accepted(self):
        upload = upload_zip({
            "plan.gml": make_plan_gml("single-valid"),
        })

        try:
            bplan_upload_file_validator(upload)
        except ValidationError as exc:
            self.fail(f"valid BPlan ZIP was rejected: {exc}")

    def test_fplan_archive_with_valid_single_gml_is_accepted(self):
        upload = upload_zip({
            "plan.gml": make_plan_gml("single-valid-fplan", "FP_Plan"),
        })

        try:
            fplan_upload_file_validator(upload)
        except ValidationError as exc:
            self.fail(f"valid FPlan ZIP was rejected: {exc}")

    def test_malformed_bplan_zip_is_not_silently_accepted(self):
        upload = SimpleUploadedFile(
            "broken.zip",
            b"this is not a ZIP archive",
            content_type="application/zip",
        )

        with self.assertRaises(zipfile.BadZipFile):
            bplan_upload_file_validator(upload)

    def test_malformed_fplan_zip_is_not_silently_accepted(self):
        upload = SimpleUploadedFile(
            "broken.zip",
            b"this is not a ZIP archive",
            content_type="application/zip",
        )

        with self.assertRaises(zipfile.BadZipFile):
            fplan_upload_file_validator(upload)


class ArchiveImportAuthorizationTests(TestCase):
    """Archive imports must require admin rights for every referenced municipality."""

    def setUp(self):
        self.foreign_user = User.objects.create_user(
            username="foreign_archive_import_user",
            password="irrelevant",
        )
        self.client = Client()
        self.client.force_login(self.foreign_user)

        AdministrativeOrganization.objects.get_or_create(
            ls="07",
            ks="316",
            gs="000",
            name=GEMEINDE_NAME,
        )

    def test_foreign_user_cannot_import_bplan_archive(self):
        upload = upload_zip({
            "plan.gml": make_plan_gml("foreign-bplan", "BP_Plan"),
        })

        response = self.client.post(
            reverse("bplan-import-archiv"),
            {"file": upload, "confirm": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context["form"].__class__.__name__ == "BPlanImportArchivForm",
            "The current permission-denied branch still returns the wrong form; "
            "keep this assertion visible while hardening the view.",
        )

    def test_foreign_user_cannot_import_fplan_archive(self):
        upload = upload_zip({
            "plan.gml": make_plan_gml("foreign-fplan", "FP_Plan"),
        })

        response = self.client.post(
            reverse("fplan-import-archiv"),
            {"file": upload, "confirm": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context["form"].__class__.__name__ == "FPlanImportArchivForm",
            "The current permission-denied branch still returns the wrong form; "
            "keep this assertion visible while hardening the view.",
        )
