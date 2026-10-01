from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
# Importieren Sie hier Ihre relevanten Models (z. B. BPlan, Bereich, etc.)
# from xplanung_light.models import BPlan


class OGCServiceViewsTestCase(TransactionTestCase):
    """
    Integrationstests für die 3 OGC WMS/WFS Views.
    Prüft die Erzeugung der Mapfiles und das OGC-Interface durch reale Aufrufe.
    """
    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    @classmethod
    def setUpTestData(cls):
        # 1. Erstellen Sie hier Mindest-Testdaten in der DB (z. B. einen BPlan mit Geometrie)
        # damit die Mapfile-Generierung Daten vorfindet und valides XML/Image zurückgeben kann.
        # cls.bplan = BPlan.objects.create(name="Testplan", ...)
        # Hier gibt es schon einen  BPlan und einen FPlan in den Fixtures
        pass

    def setUp(self):
        self.client = Client()

    """
    Dienst für organization
    """
    # -------------------------------------------------------------------------
    # 1. Test: WMS GetCapabilities
    # -------------------------------------------------------------------------

    def test_wms_get_capabilities(self):
        """Testet den WMS GetCapabilities-Request über den View."""
        # Ersetzen Sie 'wms_view_name' durch Ihren tatsächlichen URL-Namen
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '1.3.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.headers.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)

    # -------------------------------------------------------------------------
    # 2. Test: WMS GetMap (Kartenerzeugung aus Mapfile)
    # -------------------------------------------------------------------------

    # Testet GetMap, um zu prüfen, ob das erzeugte Mapfile ein Bild rendern kann.
    # Fehler nicht nachvollziehbar - siehe test_initial_data - da klappt das!

    def test_wms_get_map(self):
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetMap',
            'VERSION': '1.3.0',
            'LAYERS': 'BPlan.07316000.0',
            'STYLES': '',
            'CRS': 'EPSG:4326',
            # 'BBOX': '8.1,49.30,8.25,49.39',
            'BBOX': '49.342322,8.148906,49.343462,8.150873',
            'WIDTH': '200',
            'HEIGHT': '200',
            'FORMAT': 'image/png',
            'EXCEPTIONS': 'inimage',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'image/png')

    # -------------------------------------------------------------------------
    # 3. Test: WFS GetCapabilities & GetFeature
    # -------------------------------------------------------------------------

    def test_wfs_get_capabilities(self):
        """Testet den WFS GetCapabilities-Request."""
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WFS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '2.0.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.headers.get('Content-Type', ''))
        self.assertIn(b'wfs:WFS_Capabilities', response.content)

    # Testet GetFeature auf dem WFS Service.
    def test_wfs_get_feature(self):
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WFS',
            'REQUEST': 'GetFeature',
            'VERSION': '2.0.0',
            'TYPENAME': 'ms:BPlan.07316000.0'
        })
        self.assertEqual(response.status_code, 200)
        # print(response.content)
        self.assertIn('xml', response.headers.get('Content-Type', ''))

    """
    Dienst für bplan
    """
    # -------------------------------------------------------------------------
    # 4. Test: WMS GetCapabilities
    # -------------------------------------------------------------------------

    def test_wms_get_capabilities_bplan(self):
        """Testet den WMS GetCapabilities-Request über den View."""
        # Ersetzen Sie 'wms_view_name' durch Ihren tatsächlichen URL-Namen
        url = reverse('plan-map', kwargs={'plantyp': 'bplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '1.3.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.headers.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)
    # -------------------------------------------------------------------------
    # 5. Test: WMS GetCapabilities
    # -------------------------------------------------------------------------

    def test_wms_get_capabilities_fplan(self):
        """Testet den WMS GetCapabilities-Request über den View."""
        # Ersetzen Sie 'wms_view_name' durch Ihren tatsächlichen URL-Namen
        url = reverse('plan-map', kwargs={'plantyp': 'fplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '1.3.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.headers.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)
