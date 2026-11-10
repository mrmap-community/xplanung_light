"""
Integrationstests für die OGC-Dienste (WMS und WFS) mit echtem MapServer: Das Mapfile wird
erzeugt und der Dienst über die Views real aufgerufen.
"""

import re

from django.core.cache import cache
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse

from xplanung_light.helper.mapfile import MapfileGenerator
from xplanung_light.models import AdministrativeOrganization, BPlan, FPlan
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
        """Legt einen Test-Client an."""
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
        self.assertIn('text/xml', response.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)

    # -------------------------------------------------------------------------
    # 2. Test: WMS GetMap (Kartenerzeugung aus Mapfile)
    # -------------------------------------------------------------------------

    # Testet GetMap, um zu prüfen, ob das erzeugte Mapfile ein Bild rendern kann.
    # Fehler nicht nachvollziehbar - siehe test_initial_data - da klappt das!

    def test_wms_get_map(self):
        """
        Was wird geprüft:
            Ein WMS-GetMap-Aufruf für die Organisation 1531 (Layer BPlan und FPlan,
            EPSG:4326).

        Warum:
            Das Kartenbild muss tatsächlich erzeugt werden; das prüft den ganzen Weg von
            Datenbank über Mapfile bis MapServer.

        Erwartung:
            Status 200 und Content-Type image/png.
        """
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetMap',
            'VERSION': '1.3.0',
            'LAYERS': 'BPlan.07316000.0,FPlan.07316000.0',
            'STYLES': ',',
            'CRS': 'EPSG:4326',
            # 'BBOX': '8.1,49.30,8.25,49.39',
            'BBOX': '49.342322,8.148906,49.343462,8.150873',
            'WIDTH': '200',
            'HEIGHT': '200',
            'FORMAT': 'image/png',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'image/png')

    # -------------------------------------------------------------------------
    # 3. Test: WFS GetCapabilities & GetFeature OWS pro Orga
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
        self.assertIn('text/xml', response.get('Content-Type', ''))
        self.assertIn(b'wfs:WFS_Capabilities', response.content)

    # Testet GetFeature auf dem WFS Service.
    def test_wfs_get_feature(self):
        """
        Was wird geprüft:
            Ein WFS-GetFeature-Aufruf für den Layer BPlan der Organisation.

        Warum:
            Auch die Vektordaten müssen über den Dienst abrufbar sein.

        Erwartung:
            Status 200 und ein XML-Inhaltstyp.
        """
        url = reverse('ows', kwargs={'pk': 1531})
        response = self.client.get(url, {
            'SERVICE': 'WFS',
            'REQUEST': 'GetFeature',
            'VERSION': '2.0.0',
            'TYPENAME': 'ms:BPlan.07316000.0'
        })
        self.assertEqual(response.status_code, 200)
        # print(response.content)
        self.assertIn('xml', response.get('Content-Type', ''))

    # -------------------------------------------------------------------------
    # 4. Test BPlan Aggregat
    # -------------------------------------------------------------------------
    """
    # Testet den WMS GetCapabilities-Request über den View.
    # Deaktiviert weil er auf github nicht durchgelaufen ist -
    # lokal läuft der Test auf spatialite problemlos durch
    # Meldung auf github ubuntu 24.04:
    File "/home/runner/work/xplanung_light/xplanung_light/.venv/lib/python3.12/site-packages/mapscript/mapscript.py", line 1612, in OWSDispatch
    return _mapscript.mapObj_OWSDispatch(self, req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    _mapscript.MapServerError: msWMSGetCapabilities(): WMS server error. WMS request not enabled. Check wms/ows_enable_request settings.
    """
    """
    def test_wms_get_capabilities_bplan(self):
        url = reverse('plan-map', kwargs={'plantyp': 'bplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '1.3.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)

    def test_wms_get_map_bplan(self):
        url = reverse('plan-map', kwargs={'plantyp': 'bplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetMap',
            'VERSION': '1.3.0',
            'LAYERS': 'bplan,bplan_cluster',
            'STYLES': ',',
            'CRS': 'EPSG:4326',
            # 'BBOX': '8.1,49.30,8.25,49.39',
            'BBOX': '49.342322,8.148906,49.343462,8.150873',
            'WIDTH': '200',
            'HEIGHT': '200',
            'FORMAT': 'image/png',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'image/png')
    """
    # -------------------------------------------------------------------------
    # 5. Test: FPlan Aggregat
    # -------------------------------------------------------------------------

    def test_wms_get_capabilities_fplan(self):
        """Testet den WMS GetCapabilities-Request über den View."""
        url = reverse('plan-map', kwargs={'plantyp': 'fplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetCapabilities',
            'VERSION': '1.3.0'
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/xml', response.get('Content-Type', ''))
        self.assertIn(b'WMS_Capabilities', response.content)

    def test_wms_get_map_fplan(self):
        """
        Was wird geprüft:
            Ein WMS-GetMap-Aufruf des globalen FPlan-Dienstes (Layer fplan und
            fplan_cluster).

        Warum:
            Der globale Dienst nutzt ein anderes Mapfile als der pro Organisation.

        Erwartung:
            Status 200 und Content-Type image/png.
        """
        url = reverse('plan-map', kwargs={'plantyp': 'fplan'})
        response = self.client.get(url, {
            'SERVICE': 'WMS',
            'REQUEST': 'GetMap',
            'VERSION': '1.3.0',
            'LAYERS': 'fplan,fplan_cluster',
            'STYLES': ',',
            'CRS': 'EPSG:4326',
            # 'BBOX': '8.1,49.30,8.25,49.39',
            'BBOX': '49.342322,8.148906,49.343462,8.150873',
            'WIDTH': '200',
            'HEIGHT': '200',
            'FORMAT': 'image/png',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'image/png')


class MapfileOhneBPlaeneTestCase(TransactionTestCase):
    """
    Mapfile und OWS-Dienst einer Gebietskörperschaft ohne Bebauungspläne.

    Die Rückgabe der Mapdatei lag im Generator innerhalb der Bedingung "es gibt
    Bebauungspläne". Eine Gemeinde, die nur ihren Flächennutzungsplan
    veröffentlicht, bekam deshalb kein Mapfile - der OWS-View antwortete mit
    einer 500er-Seite (msLoadMapFromString(): No buffer to load). Ebenso lief
    eine Gebietskörperschaft ohne öffentliche Pläne in eine GDAL-Ausnahme, weil
    ST_Union über einer leeren Ebene NULL liefert und der Text "None" kein
    lesbares geometrieobjekt ist.
    """
    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    ORGA_PK = 1531

    def setUp(self):
        """Client anlegen und das Mapfile-Zwischenspeicher leeren."""
        self.client = Client()
        cache.clear()
        self.orga = AdministrativeOrganization.objects.get(pk=self.ORGA_PK)

    def tearDown(self):
        cache.clear()

    def _ows_abfrage(self, request='GetCapabilities'):
        """Ein WMS-Request gegen den Dienst der Test-Gebietskörperschaft."""
        return self.client.get(
            reverse('ows', kwargs={'pk': self.ORGA_PK}),
            {'SERVICE': 'WMS', 'REQUEST': request, 'VERSION': '1.3.0'})

    def _mapfile(self):
        """Mapfile-Text der Test-Gebietskörperschaft, wie ihn der View erzeugt."""
        return MapfileGenerator().generate_mapfile(
            self.ORGA_PK,
            'http://localhost/organization/{0}/ows/'.format(self.ORGA_PK),
            'http://localhost/xplanung_light/bplan/1000000/metadata/')

    def _setze_bplaene_nicht_oeffentlich(self):
        BPlan.objects.filter(gemeinde=self.orga).update(public=False)

    def _setze_alle_plaene_nicht_oeffentlich(self):
        self._setze_bplaene_nicht_oeffentlich()
        FPlan.objects.filter(gemeinde=self.orga).update(public=False)

    def test_mapfile_nur_mit_fplaenen_wird_erzeugt(self):
        """
        Was wird geprüft:
            Die Mapfile-Erzeugung für eine Gebietskörperschaft, deren einzige
            öffentliche Pläne Flächennutzungspläne sind.

        Warum:
            Die Rückgabe des Mapfile-Textes gehörte in den Block "es gibt
            Bebauungspläne". Ohne Bebauungspläne fiel die Funktion am Ende ohne
            Wert zurück, und der OWS-View scheiterte danach an None.

        Erwartung:
            Ein Mapfile-Text, in dem die Flächennutzungsplan-Ebenen enthalten
            und keine Bebauungsplan-Ebenen enthalten sind.
        """
        self._setze_bplaene_nicht_oeffentlich()

        mapfile = self._mapfile()

        self.assertIsInstance(mapfile, str)
        self.assertIn('FPlan.' + self.orga.ags, mapfile)
        self.assertNotIn('BPlan.' + self.orga.ags, mapfile)

    def test_ows_get_capabilities_ohne_bplaene(self):
        """
        Was wird geprüft:
            Der WMS GetCapabilities einer Gebietskörperschaft ohne öffentliche
            Bebauungspläne.

        Warum:
            Vor dem Fix antwortete der Dienst in dieser Konstellation mit HTTP
            500, weil kein Mapfile erzeugt wurde.

        Erwartung:
            Status 200 mit Capabilities-Text und der Flächennutzungsplan-Ebene.
        """
        self._setze_bplaene_nicht_oeffentlich()

        response = self._ows_abfrage()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'WMS_Capabilities', response.content)
        self.assertIn(('FPlan.' + self.orga.ags).encode(), response.content)

    def test_mapfile_ohne_oeffentliche_plaene_wird_erzeugt(self):
        """
        Was wird geprüft:
            Die Mapfile-Erzeugung für eine Gebietskörperschaft ohne öffentliche
            Pläne überhaupt.

        Warum:
            Über einer leeren Planebene liefert ST_Union NULL. Der Code nahm das
            Ergebnis als Text "None" und GDAL antwortete mit "Invalid geometry
            pointer returned from OGR_G_CreateGeometry" - ein 500er auf jede
            OWS-Abfrage einer Gemeinde ohne veröffentlichte Pläne.

        Erwartung:
            Ein Mapfile-Text, dessen Service-Extent dem Gebiet der
            Gebietskörperschaft entspricht.
        """
        self._setze_alle_plaene_nicht_oeffentlich()

        mapfile = self._mapfile()

        self.assertIsInstance(mapfile, str)
        # ohne Plaene entstehen keine Ebenen - aber auch kein Fehler
        self.assertNotIn('LAYER', mapfile)
        erwartet = self.orga.geometry.extent
        gefunden = [float(zahl) for zahl in
                    re.search(r"'ows_extent'\s+'([^']+)'", mapfile).group(1).split()]
        for ist, soll in zip(gefunden, erwartet):
            self.assertAlmostEqual(ist, soll, places=6)

    def test_ows_get_capabilities_ohne_oeffentliche_plaene(self):
        """
        Was wird geprüft:
            Der WMS GetCapabilities einer Gebietskörperschaft ohne öffentliche
            Pläne.

        Warum:
            Der Fall kommt in jeder Installation vor, deren Datenbestand noch
            nicht online gestellt ist; er darf keine Fehlerseite liefern.

        Erwartung:
            Status 200 mit Capabilities-Text - ohne Pläne ohne Ebene, aber als
            gültige Antwort statt als Fehler.
        """
        self._setze_alle_plaene_nicht_oeffentlich()

        response = self._ows_abfrage()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'WMS_Capabilities', response.content)

    def test_extent_ohneGebietDerOrga_nutzt_extentDerVorlage(self):
        """
        Was wird geprüft:
            Die Extents-Ermittlung ohne Pläne und ohne Gebiet der
            Gebietskörperschaft.

        Warum:
            Beide Grundlagen können fehlen - ein Ort ohne veröffentlichte Pläne
            und ohne gepflegte Gebietsgeometrie. Der Ausweg darf wieder keine
            GDAL-Ausnahme sein.

        Erwartung:
            Der EXTENT-Wert aus der Vorlage bleibt stehen und wird als
            Service-Extent übernommen.
        """
        self._setze_alle_plaene_nicht_oeffentlich()
        AdministrativeOrganization.objects.filter(pk=self.ORGA_PK).update(geometry=None)
        self.orga.refresh_from_db()
        self.assertIsNone(self.orga.geometry)

        mapfile = self._mapfile()

        extent = re.search(r'^\s*EXTENT\s+([0-9.eE+-]+ [0-9.eE+-]+ [0-9.eE+-]+ [0-9.eE+-]+)',
                           mapfile, re.MULTILINE).group(1)
        ows_extent = re.search(r"'ows_extent'\s+'([^']+)'", mapfile).group(1)
        self.assertEqual(ows_extent, extent)
        # ohne Pläne und ohne Gebiet ist das der Wert aus der Vorlage
        self.assertEqual(MapfileGenerator()._ows_extent(self.orga, None, extent), extent)

    def test_plan_map_ohne_oeffentliche_plaene(self):
        """
        Was wird geprüft:
            Der globale WMS-Dienst über alle Organisationen (plan-map) ohne
            öffentliche Pläne.

        Warum:
            Der globale Dienst bestimmt sein Extent auf dieselbe Weise aus der
            Vereinigungsmenge aller Pläne und lieferte in derselben Konstellation
            eine unlesbare NULL-Angabe an GDAL.

        Erwartung:
            Status 200 mit Capabilities-Text, für beide Planschläge.
        """
        self._setze_alle_plaene_nicht_oeffentlich()

        for plantyp in ('bplan', 'fplan'):
            with self.subTest(plantyp=plantyp):
                response = self.client.get(
                    reverse('plan-map', kwargs={'plantyp': plantyp}),
                    {'SERVICE': 'WMS', 'REQUEST': 'GetCapabilities', 'VERSION': '1.3.0'})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'WMS_Capabilities', response.content)

    def test_mapfile_mit_bplaenen_unveraendert(self):
        """
        Was wird geprüft:
            Die Mapfile-Erzeugung einer Gebietskörperschaft mit beiden
            Planschlägen.

        Warum:
            Die Verschiebung der Rückgabe aus dem Bedingungsblock darf den
            bisherigen Weg nicht verändern.

        Erwartung:
            Mapfile-Text mit Bebauungsplan- und Flächennutzungsplan-Ebenen und
            mit dem aus den Plänen berechneten Extent.
        """
        mapfile = self._mapfile()

        self.assertIn('BPlan.' + self.orga.ags, mapfile)
        self.assertIn('FPlan.' + self.orga.ags, mapfile)
        ows_extent = re.search(r"'ows_extent'\s+'([^']+)'", mapfile).group(1)
        self.assertEqual(re.search(
            r'^\s*EXTENT\s+([0-9.eE+-]+ [0-9.eE+-]+ [0-9.eE+-]+ [0-9.eE+-]+)',
            mapfile, re.MULTILINE).group(1), ows_extent)
        # das berechnete Extent liegt innerhalb des Gebiets, ist aber nicht die
        # Vorlage: die Plangeometrien sind enger als das Organgebiet
        gebiet = self.orga.geometry.extent
        for ist, klein, gross in zip([float(z) for z in ows_extent.split()],
                                     [min(gebiet[0], gebiet[2]), min(gebiet[1], gebiet[3])],
                                     [max(gebiet[0], gebiet[2]), max(gebiet[1], gebiet[3])]):
            self.assertGreaterEqual(ist, klein - 0.01)
            self.assertLessEqual(ist, gross + 0.01)
