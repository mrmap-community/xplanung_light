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

        # 2. Superuser für den administrativen Upload deklarieren
        self.admin_user = User.objects.create_superuser(username="archive_admin", password="password123")

        # KORREKTUR: Namespace-URI und AGS-Tag präzise geschlossen
        self.gml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<xplan:XPlanAuszug xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:xsi="http://w3.org" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://gdi-de.org" gml:id="GML_4f156414-9dff-404f-bb29-c053df45b384">'
            b'  <gml:boundedBy><gml:Envelope srsName="EPSG:25832"><gml:lowerCorner>567015.8040 5937951.7580</gml:lowerCorner><gml:upperCorner>567582.8240 5938562.2710</gml:upperCorner></gml:Envelope></gml:boundedBy>'
            b'  <gml:featureMember>'
            b'    <xplan:BP_Plan gml:id="GML_5b2f5374-fbe6-4ffd-be95-06a257dc5c91">'
            b'      <gml:boundedBy><gml:Envelope srsName="EPSG:25832"><gml:lowerCorner>436104.85390563804 5463436.092545369</gml:lowerCorner><gml:upperCorner>436570.32736793294 5463774.156689</gml:upperCorner></gml:Envelope></gml:boundedBy>'
            b'      <xplan:name>Andergasse - Kaesgasse</xplan:name>'
            b'      <xplan:nummer>156</xplan:nummer><xplan:erstellungsMassstab>1000</xplan:erstellungsMassstab>'
            b'      <xplan:raeumlicherGeltungsbereich>'
            b'        <gml:MultiSurface srsName="EPSG:25832" gml:id="GML_1"><gml:surfaceMember><gml:Polygon gml:id="GML_2"><gml:exterior><gml:LinearRing><gml:posList srsDimension="2">436104.85390564 5463751.69231124 436124.64358817 5463681.09740405 436104.85390564 5463751.69231124</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>'
            b'      </xplan:raeumlicherGeltungsbereich>'
            b'      <xplan:gemeinde><xplan:XP_Gemeinde><xplan:ags>07316000</xplan:ags><xplan:gemeindeName>Neustadt an der Weinstra\xc3\x9fe, kreisfreie Stadt</xplan:gemeindeName></xplan:XP_Gemeinde></xplan:gemeinde>'
            b'      <xplan:planArt>10000</xplan:planArt><xplan:rechtsstand>5000</xplan:rechtsstand>'
            b'    </xplan:BP_Plan>'
            b'  </gml:featureMember>'
            b'</xplan:XPlanAuszug>'
        )

        # 4. In-Memory-ZIP-Archiv für BPlan erzeugen
        self.bplan_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(self.bplan_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("plan.gml", self.gml_content)
        self.bplan_zip_buffer.seek(0)

        # 5. In-Memory-ZIP-Archiv für FPlan erzeugen
        self.fplan_zip_buffer = io.BytesIO()
        fplan_content = self.gml_content.replace(b'xplan:BP_Plan', b'xplan:FP_Plan')
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
