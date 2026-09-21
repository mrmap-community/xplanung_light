import io
import zipfile
import xml.etree.ElementTree as ET

from django import forms
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import BPlan, FPlan
from xplanung_light.validators import bplan_content_validator, fplan_content_validator


XPLAN_NS = "http://www.xplanung.de/xplangml/6/0"
GML_NS = "http://www.opengis.net/gml/3.2"

AGS = "07316000"
GEMEINDE_NAME = "Neustadt an der Weinstraße, kreisfreie Stadt"

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
  <gml:exterior>
    <gml:LinearRing>
      <gml:posList>
        430000.000 5470000.000
        430200.000 5470000.000
        430200.000 5470200.000
        430000.000 5470200.000
        430000.000 5470000.000
      </gml:posList>
    </gml:LinearRing>
  </gml:exterior>
</gml:Polygon>"""


def make_gml(plan_element, name, nummer="2099"):
    return f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<xplan:XPlanAuszug
    xmlns:xplan="{XPLAN_NS}"
    xmlns:gml="{GML_NS}"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    gml:id="GML_testauszug">
  <gml:featureMember>
    <xplan:{plan_element} gml:id="GML_testplan">
      <xplan:name>{name}</xplan:name>
      <xplan:nummer>{nummer}</xplan:nummer>
      <xplan:raeumlicherGeltungsbereich>{GEOMETRIE}</xplan:raeumlicherGeltungsbereich>
      <xplan:gemeinde>
        <xplan:XP_Gemeinde>
          <xplan:ags>{AGS}</xplan:ags>
          <xplan:gemeindeName>{GEMEINDE_NAME}</xplan:gemeindeName>
        </xplan:XP_Gemeinde>
      </xplan:gemeinde>
      <xplan:planArt>1000</xplan:planArt>
    </xplan:{plan_element}>
  </gml:featureMember>
</xplan:XPlanAuszug>
"""


def upload(content, filename="testplan.gml"):
    return SimpleUploadedFile(
        filename,
        content.encode("utf-8"),
        content_type="application/gml",
    )


class ImportExportRegressionTests(TestCase):
    """
    Wichtige Import/Export-Regressionstests.

    Schwerpunkt:
    - direkter GML-Export liefert wohlgeformtes, importierbares XPlanGML
    - BPlan- und FPlan-Import legen die erwarteten Daten an
    - ein erneuter Import ohne confirm erzeugt keinen zweiten Plan
    - ZIP-Export enthält die exportierte GML
    """

    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "fplan.json",
        "admin_orga_user.json",
    ]

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.get(username="admin_stadt_neustadt")
        self.client.force_login(self.admin)

    def test_bplan_gml_export_is_well_formed_and_passes_import_validator(self):
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[4318])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")

        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, f"{{{XPLAN_NS}}}XPlanAuszug")

        try:
            bplan_content_validator(io.BytesIO(response.content))
        except forms.ValidationError as error:
            self.fail(
                "Der direkte BPlan-GML-Export wird vom eigenen Validator "
                "abgelehnt: " + "; ".join(error.messages)
            )

    def test_fplan_gml_export_is_well_formed_and_passes_import_validator(self):
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[631])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")

        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, f"{{{XPLAN_NS}}}XPlanAuszug")

        try:
            fplan_content_validator(io.BytesIO(response.content))
        except forms.ValidationError as error:
            self.fail(
                "Der direkte FPlan-GML-Export wird vom eigenen Validator "
                "abgelehnt: " + "; ".join(error.messages)
            )

    def test_bplan_import_creates_plan_with_core_fields(self):
        name = "Import-Test BPlan"
        response = self.client.post(
            reverse("bplan-import"),
            data={
                "file": upload(make_gml("BP_Plan", name), "import-bplan.gml"),
                "confirm": False,
            },
        )

        self.assertEqual(response.status_code, 302)
        plan = BPlan.objects.get(name=name)

        self.assertEqual(plan.nummer, "2099")
        self.assertEqual(plan.planart, "1000")
        self.assertEqual(plan.xplan_gml_version, "6.0")
        self.assertEqual(list(plan.gemeinde.values_list("ls", "ks", "gs")), [("07", "316", "000")])

    def test_fplan_import_creates_plan_with_core_fields(self):
        name = "Import-Test FPlan"
        response = self.client.post(
            reverse("fplan-import"),
            data={
                "file": upload(make_gml("FP_Plan", name), "import-fplan.gml"),
                "confirm": False,
            },
        )

        self.assertEqual(response.status_code, 302)
        plan = FPlan.objects.get(name=name)

        self.assertEqual(plan.nummer, "2099")
        self.assertEqual(plan.planart, "1000")
        self.assertEqual(plan.xplan_gml_version, "6.0")
        self.assertEqual(list(plan.gemeinde.values_list("ls", "ks", "gs")), [("07", "316", "000")])

    def test_bplan_import_without_confirm_does_not_duplicate_existing_plan(self):
        name = "Import-Test Duplicate BPlan"
        content = make_gml("BP_Plan", name)

        first_response = self.client.post(
            reverse("bplan-import"),
            data={"file": upload(content), "confirm": False},
        )
        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(BPlan.objects.filter(name=name).count(), 1)

        second_response = self.client.post(
            reverse("bplan-import"),
            data={"file": upload(content), "confirm": False},
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(BPlan.objects.filter(name=name).count(), 1)

    def test_bplan_zip_export_contains_xplan_gml(self):
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6-zip", args=[4318])
        )

        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))

        self.assertIsNone(archive.testzip())
        self.assertEqual(
            [name for name in archive.namelist() if name.endswith(".gml")],
            ["xplan.gml"],
        )

        root = ET.fromstring(archive.read("xplan.gml"))
        self.assertEqual(root.tag, f"{{{XPLAN_NS}}}XPlanAuszug")

    def test_fplan_zip_export_contains_xplan_gml(self):
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6-zip", args=[631])
        )

        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))

        self.assertIsNone(archive.testzip())
        self.assertEqual(
            [name for name in archive.namelist() if name.endswith(".gml")],
            ["xplan.gml"],
        )

        root = ET.fromstring(archive.read("xplan.gml"))
        self.assertEqual(root.tag, f"{{{XPLAN_NS}}}XPlanAuszug")
