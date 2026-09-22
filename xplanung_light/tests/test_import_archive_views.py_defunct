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

        # KORREKTUR: Namespace-URI, geschlossene Tags und die fehlende Ziffer in der Koordinate präzise repariert
        self.valid_gml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<xplan:XPlanAuszug xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:xsi="http://w3.org" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://gdi-de.org" gml:id="GML_4f156414-9dff-404f-bb29-c053df45b384">'
            b'  <gml:boundedBy>'
            b'    <gml:Envelope srsName="EPSG:25832">'
            b'      <gml:lowerCorner>567015.8040 5937951.7580</gml:lowerCorner>'
            b'      <gml:upperCorner>567582.8240 5938562.2710</gml:upperCorner>'
            b'    </gml:Envelope>'
            b'  </gml:boundedBy>'
            b'  <gml:featureMember>'
            b'    <xplan:BP_Plan gml:id="GML_5b2f5374-fbe6-4ffd-be95-06a257dc5c91">'
            b'      <gml:boundedBy>'
            b'        <gml:Envelope srsName="EPSG:25832">'
            b'          <gml:lowerCorner>436104.85390563804 5463436.092545369</gml:lowerCorner>'
            b'          <gml:upperCorner>436570.32736793294 5463774.156689</gml:upperCorner>'
            b'        </gml:Envelope>'
            b'      </gml:boundedBy>'
            b'      <xplan:name>Andergasse - Kaesgasse</xplan:name>'
            b'      <xplan:nummer>156</xplan:nummer><xplan:beschreibung>BPlan</xplan:beschreibung><xplan:erstellungsMassstab>1000</xplan:erstellungsMassstab>'
            b'      <xplan:raeumlicherGeltungsbereich>'
            b'        <gml:MultiSurface srsName="EPSG:25832" gml:id="GML_6fbf9832-2278-4d9e-a56f-d2924037fdb3"><gml:surfaceMember><gml:Polygon gml:id="GML_4df93d64-dc65-40a4-9ba1-ff9b88fb020a"><gml:exterior><gml:LinearRing><gml:posList srsDimension="2">436104.85390564 5463751.69231124 436124.64358817 5463681.09740405 436133.33921193 5463682.98919936 436135.10324988 5463670.59415875 436148.39968108 5463668.56555334 436158.57548066 5463668.04754797 436164.15107753 5463668.30466303 436164.09651466 5463641.16034437 436174.67509012 5463641.04858482 436171.56533962 5463599.39210373 436185.15352156 5463600.24093389 436187.43524357 5463583.54988306 436139.81618399 5463562.49166355 436118.45960927 5463558.29973327 436117.78046611 5463551.54920908 436116.80077779 5463541.82299631 436111.38175025 5463520.17145336 436112.22600232 5463482.14871958 436105.26343582 5463456.39765689 436132.59997112 5463455.67391332 436163.00393645 5463452.34408309 436182.37471746 5463447.63768409 436198.00197537 5463442.89329095 436215.99354395 5463438.50414026 436230.5136713 5463436.09254537 436261.30503207 5463439.1583995 436276.08510526 5463444.48142878 436290.61739622 5463452.2874615 436301.04477183 5463458.35470509 436334.36900581 5463466.78858209 436386.60824782 5463478.79569887 436435.00116248 5463483.39430583 436541.01156276 5463500.95914129 436541.39348144 5463590.95028364 436528.78395455 5463617.3605229 436526.9978058 5463677.75388437 436565.41458792 5463695.18497288 436564.000048 5463700.40154664 436563.39274228 5463705.23816404 436569.51930235 5463730.10648139 436570.32736793 5463755.90985207 436527.69123462 5463774.156689 436524.52527055 5463747.54787208 436483.68123252 5463753.00626386 436483.06742595 5463748.91725026 436450.70552493 5463754.31648402 436446.12700003 5463720.83136379 436410.21123791 5463726.52947855 436409.3815246 5463720.73177325 43649.40533313 5463735.67547517 436344.17889868 5463725.15525269 436301.71233247 5463742.49837144 436265.04674148 5463755.50938665 436263.91718185 5463754.72970464 436211.45381849 5463746.01661066 436219.88641383 5463734.25318301 436189.0495555 5463734.25318301 436130.83064019 5463748.88619006 436118.102687 5463752.8147507 436104.85390564 5463751.69231124</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>'
            b'      </xplan:raeumlicherGeltungsbereich>'
            b'      <xplan:gemeinde>'
            b'        <xplan:XP_Gemeinde>'
            b'          <xplan:ags>07316000</xplan:ags>'
            b'          <xplan:gemeindeName>Neustadt an der Weinstra\xc3\x9fe, kreisfreie Stadt</xplan:gemeindeName>'
            b'        </xplan:XP_Gemeinde>'
            b'      </xplan:gemeinde>'
            b'      <xplan:planArt>10000</xplan:planArt>'
            b'      <xplan:rechtsstand>5000</xplan:rechtsstand>'
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

