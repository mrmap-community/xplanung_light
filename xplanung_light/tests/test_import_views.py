from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from xplanung_light.models import AdministrativeOrganization, BPlan, FPlan

User = get_user_model()

class XPlanImportViewTests(TestCase):

    def setUp(self):
        # 1. Wir legen die im XML referenzierte Gemeinde in der DB an
        AdministrativeOrganization.objects.get_or_create(
            ls='07', ks='316', gs='000',
            name="Neustadt an der Weinstraße, kreisfreie Stadt"
        )

        # 2. Superuser anlegen
        self.admin_user = User.objects.create_superuser(username="import_admin", password="password123")

        # KORREKTUR: Wurzel-Tag exakt nach deiner bereitgestellten Spezifikation deklariert
        self.valid_gml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<xplan:XPlanAuszug xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_4f156414-9dff-404f-bb29-c053df45b384">'
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

    # ==============================================================================
    # 1. BPLAN-IMPORT (GET & POST FILE UPLOAD)
    # ==============================================================================

    def test_bplan_import_view_get_and_post_success(self):
        """Ein Administrator kann die BPlan-Importseite aufrufen und eine valide GML-Datei hochladen."""
        self.client.login(username="import_admin", password="password123")
        url = reverse("bplan-import")

        # 1. GET-Aufruf der Uploadseite
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # 2. POST-Upload einer validen GML-Datei simulieren
        gml_file = SimpleUploadedFile("bplan_import.gml", self.valid_gml_content, content_type="text/xml")
        payload = {
            "confirm": False,
            "file": gml_file
        }

        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)

    # ==============================================================================
    # 2. FPLAN-IMPORT (GET & POST FILE UPLOAD)
    # ==============================================================================

    def test_fplan_import_view_get_and_post_success(self):
        """Ein Administrator kann die FPlan-Importseite aufrufen und eine valide GML-Datei hochladen."""
        self.client.login(username="import_admin", password="password123")
        url = reverse("fplan-import")

        # 1. GET-Aufruf
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # 2. POST-Upload einer FPlan-Datei (wir ersetzen das Tag passend zu FPlanImportForm)
        fplan_content = self.valid_gml_content.replace(b'xplan:BP_Plan', b'xplan:FP_Plan')
        fplan_file = SimpleUploadedFile("fplan_import.gml", fplan_content, content_type="text/xml")
        
        payload = {
            "confirm": False,
            "file": fplan_file
        }

        response_post = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response_post.status_code, 200)
