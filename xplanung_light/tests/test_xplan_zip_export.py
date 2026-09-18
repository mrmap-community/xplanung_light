import io
import zipfile
import xml.etree.ElementTree as ET

from django import forms
from django.test import TestCase, Client
from django.urls import reverse

from xplanung_light.validators import bplan_content_validator


class BPlanZipExport(TestCase):
    """
    Test des ZIP-Exports (XPlanDetailXPlanLightZipView).

    Ergänzt den vorhandenen Round-Trip-Test um die Verpackungsschicht: das ZIP
    muss lesbar sein, genau eine GML-Datei ('xplan.gml') enthalten, und diese
    GML muss den eigenen Import-Validator ohne Fehler durchlaufen.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    PLAN_PK = 4318

    def setUp(self):
        self.client = Client()

    def _get_zip(self):
        response = self.client.get(
            reverse('bplan-export-xplan-raster-6-zip', args=[self.PLAN_PK])
        )
        self.assertEqual(response.status_code, 200)
        # FileResponse -> streaming_content einsammeln
        content = b"".join(response.streaming_content)
        return zipfile.ZipFile(io.BytesIO(content))

    def test_zip_is_readable_and_contains_exactly_one_gml(self):
        # ZIP muss unbeschädigt sein und darf genau eine .gml-Datei enthalten.
        zip_file = self._get_zip()
        # testzip() liefert den Namen der ersten defekten Datei, sonst None
        self.assertIsNone(zip_file.testzip())
        gml_files = [name for name in zip_file.namelist() if name.endswith('.gml')]
        self.assertEqual(gml_files, ['xplan.gml'])

    def test_exported_gml_has_supported_root_element(self):
        # Wurzelelement muss im XPlan-6.0-Namespace liegen.
        zip_file = self._get_zip()
        root = ET.fromstring(zip_file.read('xplan.gml').decode('utf-8'))
        self.assertEqual(
            root.tag,
            '{http://www.xplanung.de/xplangml/6/0}XPlanAuszug',
        )

    def test_exported_gml_passes_import_validator(self):
        """
        Export und Import-Validierung müssen zusammenpassen - ein Export, den der
        eigene Validator ablehnt, wäre für den Datenaustausch unbrauchbar.
        """
        zip_file = self._get_zip()
        gml_file = io.BytesIO(zip_file.read('xplan.gml'))
        try:
            bplan_content_validator(gml_file)
        except forms.ValidationError as error:
            self.fail(
                "Exportiertes XPlan-GML wird vom eigenen Validator abgelehnt: "
                + "; ".join(error.messages)
            )