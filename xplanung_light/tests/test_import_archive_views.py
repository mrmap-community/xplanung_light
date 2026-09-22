import io
import zipfile
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from xplanung_light.models import AdministrativeOrganization

User = get_user_model()

class XPlanImportArchiveViewTests(TestCase):

    def setUp(self):
        # 1. Referenzierte Gemeinde in der DB anlegen
        AdministrativeOrganization.objects.get_or_create(
            ls='07', ks='316', gs='000',
            name="Neustadt an der Weinstraße, kreisfreie Stadt"
        )

        # 2. Superuser deklarieren
        self.admin_user = User.objects.create_superuser(username="archive_admin", password="password123")

        # 3. KORREKTUR: Mathematisch perfektes, geschlossenes Quadrat aus deinem Skript integriert
        # Das garantiert, dass GEOS/GDAL auf dem GitHub-Runner immer eine gültige Fläche berechnen kann!
        geometrie_quadrat = (
            b'<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">'
            b'  <gml:exterior>'
            b'    <gml:LinearRing>'
            b'      <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>'
            b'    </gml:LinearRing>'
            b'  </gml:exterior>'
            b'</gml:Polygon>'
        )

        # Vollständiger valider XPlanung 6.0 XML-String mit sauberen Namespaces
        self.valid_gml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<xplan:XPlanAuszug xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:xsi="http://w3.org" xsi:schemaLocation="http://xplanung.de http://gdi-de.org" gml:id="GML_4f156414-9dff-404f-bb29-c053df45b384">'
            b'  <gml:featureMember>'
            b'    <xplan:BP_Plan gml:id="GML_testplan">'
            b'      <xplan:name>Archiv-Import-Test BPlan</xplan:name>'
            b'      <xplan:nummer>156</xplan:nummer>'
            b'      <xplan:erstellungsMassstab>1000</xplan:erstellungsMassstab>'
            b'      <xplan:raeumlicherGeltungsbereich>' + geometrie_quadrat + b'</xplan:raeumlicherGeltungsbereich>'
            b'      <xplan:gemeinde>'
            b'        <xplan:XP_Gemeinde>'
            b'          <xplan:ags>07316000</xplan:ags>'
            b'          <xplan:gemeindeName>Neustadt an der Weinstra\xc3\x9fe, kreisfreie Stadt</xplan:gemeindeName>'
            b'        </xplan:XP_Gemeinde>'
            b'      </xplan:gemeinde>'
            b'      <xplan:planArt>1000</xplan:planArt>'
            b'    </xplan:BP_Plan>'
            b'  </gml:featureMember>'
            b'</xplan:XPlanAuszug>'
        )

        # 4. In-Memory-ZIP-Archiv für BPlan erzeugen
        self.bplan_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(self.bplan_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("plan.gml", self.valid_gml_content)
        self.bplan_zip_buffer.seek(0)

        # 5. In-Memory-ZIP-Archiv für FPlan erzeugen
        self.fplan_zip_buffer = io.BytesIO()
        fplan_content = self.valid_gml_content.replace(b'xplan:BP_Plan', b'xplan:FP_Plan')
        with zipfile.ZipFile(self.fplan_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("plan.gml", fplan_content)
        self.fplan_zip_buffer.seek(0)

    # ==============================================================================
    # 1. BPLAN-ARCHIV-IMPORT (GET & POST)
    # ==============================================================================

    def test_bplan_import_archiv_view_success(self):
        """Prüft die Erreichbarkeit und den Upload eines echten ZIP-Archivs für BPläne."""
        self.client.login(username="archive_admin", password="password123")
        url = reverse("bplan-import-archiv")

        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        uploaded_zip = SimpleUploadedFile("bplan_archiv.zip", self.bplan_zip_buffer.read(), content_type="application/zip")
        payload = {
            "confirm": False,
            "file": uploaded_zip
        }
        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)

    # ==============================================================================
    # 2. FPLAN-ARCHIV-IMPORT (GET & POST)
    # ==============================================================================

    def test_fplan_import_archiv_view_success(self):
        """Prüft die Erreichbarkeit und den Upload eines echten ZIP-Archivs für FPläne."""
        self.client.login(username="archive_admin", password="password123")
        url = reverse("fplan-import-archiv")

        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        uploaded_zip = SimpleUploadedFile("fplan_archiv.zip", self.fplan_zip_buffer.read(), content_type="application/zip")
        payload = {
            "confirm": False,
            "file": uploaded_zip
        }
        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)
