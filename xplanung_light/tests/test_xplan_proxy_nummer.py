import xml.etree.ElementTree as ET

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import BPlan


XPLAN_NS = 'http://www.xplanung.de/xplangml/6/0'
GML_NS = 'http://www.opengis.net/gml/3.2'
NS = {'xplan': XPLAN_NS, 'gml': GML_NS}

# XPath auf das Element, um das es geht
NUMMER_XPATH = 'gml:featureMember/xplan:BP_Plan/xplan:nummer'

# AGS und Name müssen zur Fixture-Organisation passen, sonst schlägt schon
# der Import fehl (AdministrativeOrganization wird über beides gesucht).
AGS = '07316000'
GEMEINDE_NAME = 'Neustadt an der Weinstraße, kreisfreie Stadt'

GML_TEMPLATE = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<xplan:XPlanAuszug xmlns:xplan="{xplan_ns}" xmlns:gml="{gml_ns}"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    gml:id="GML_testauszug">
  <gml:featureMember>
    <xplan:BP_Plan gml:id="GML_testplan">
      <xplan:name>{name}</xplan:name>
      {nummer_element}
      <xplan:raeumlicherGeltungsbereich>
        <gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </xplan:raeumlicherGeltungsbereich>
      <xplan:gemeinde>
        <xplan:XP_Gemeinde>
          <xplan:ags>{ags}</xplan:ags>
          <xplan:gemeindeName>{gemeinde_name}</xplan:gemeindeName>
        </xplan:XP_Gemeinde>
      </xplan:gemeinde>
      <xplan:planArt>1000</xplan:planArt>
    </xplan:BP_Plan>
  </gml:featureMember>
</xplan:XPlanAuszug>
"""


class XPlanProxyNummerUeberschreiben(TestCase):
    """
    Ein per GML hochgeladener Plan wird beim Export nicht neu erzeugt, sondern
    das gespeicherte Original-GML wird von XPlanung.proxy_bplan_gml() mit den
    aktuellen Datenbankinhalten überschrieben (bplan_attribute_array,
    'nummer' ist dort overwrite=True).

    Getestet wird, dass eine in der Datenbank geänderte Plannummer im
    ausgelieferten GML unter dem XPath
    gml:featureMember/xplan:BP_Plan/xplan:nummer landet - und zwar genau dort,
    nicht im BP_Bereich und nicht doppelt.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    def setUp(self):
        self.client = Client()
        # Die importierten Testpläne sind standardmäßig privat. Verwende den
        # in den Fixtures angelegten Gemeinde-Admin direkt, damit der Test
        # nicht von der konfigurierten Passwort-Hashing-/Auth-Backend-
        # Konfiguration abhängt.
        user = get_user_model().objects.get(username='admin_stadt_neustadt')
        self.client.force_login(user)

    # --- Hilfsfunktionen --------------------------------------------------

    def _build_gml(self, plan_name, nummer=None):
        if nummer is None:
            nummer_element = '<!-- keine nummer angegeben -->'
        else:
            nummer_element = '<xplan:nummer>%s</xplan:nummer>' % nummer
        return GML_TEMPLATE.format(
            xplan_ns=XPLAN_NS,
            gml_ns=GML_NS,
            name=plan_name,
            nummer_element=nummer_element,
            ags=AGS,
            gemeinde_name=GEMEINDE_NAME,
        )

    def _import_gml(self, plan_name, nummer=None):
        """Simuliert den Upload einer GML-Datei über das Import-Formular."""
        upload = SimpleUploadedFile(
            'testplan.gml',
            self._build_gml(plan_name, nummer).encode('utf-8'),
            content_type='application/gml',
        )
        created = XPlanung(upload).import_plan(overwrite=False, plan_typ='bplan')
        self.assertTrue(created, "Import der GML-Datei ist fehlgeschlagen")
        plan = BPlan.objects.get(name=plan_name)
        self.assertTrue(plan.xplan_gml, "Original-GML wurde nicht am Plan gespeichert")
        return plan

    def _export_root(self, plan):
        """Liefert den geparsten Wurzelknoten des ausgelieferten GML."""
        response = self.client.get(
            reverse('bplan-export-xplan-raster-6', args=[plan.pk])
        )
        self.assertEqual(response.status_code, 200)
        return ET.fromstring(response.content.decode('utf-8'))

    # --- Tests ------------------------------------------------------------

    def test_geaenderte_nummer_wird_im_gml_ausgeliefert(self):
        # Kernfall: DB-Nummer ändern, Original-GML muss beim Export
        # mit der neuen Nummer überschrieben werden.
        plan = self._import_gml('Testplan Proxy Nummer', nummer='100')
        self.assertEqual(plan.nummer, '100')

        plan.nummer = '999'
        plan.save()

        root = self._export_root(plan)
        nummer_elemente = root.findall(NUMMER_XPATH, NS)
        self.assertEqual(
            len(nummer_elemente), 1,
            "Es muss genau ein xplan:nummer unterhalb von BP_Plan geben, gefunden: %d"
            % len(nummer_elemente),
        )
        self.assertEqual(nummer_elemente[0].text, '999')

    def test_nummer_wird_ergaenzt_wenn_im_original_gml_nicht_vorhanden(self):
        """
        Ohne xplan:nummer im Original muss der Proxy das Element einfügen -
        laut XSD-Sequence direkt hinter xplan:name.
        """
        plan = self._import_gml('Testplan ohne Nummer')
        self.assertFalse(plan.nummer)  # CharField ohne null -> ''

        plan.nummer = '42'
        plan.save()

        root = self._export_root(plan)
        bplan_element = root.find('gml:featureMember/xplan:BP_Plan', NS)
        kinder = [child.tag for child in bplan_element]

        nummer_tag = '{%s}nummer' % XPLAN_NS
        name_tag = '{%s}name' % XPLAN_NS
        self.assertIn(nummer_tag, kinder, "xplan:nummer wurde nicht eingefügt")
        self.assertEqual(
            kinder.index(nummer_tag), kinder.index(name_tag) + 1,
            "xplan:nummer steht nicht direkt hinter xplan:name",
        )
        self.assertEqual(bplan_element.find('xplan:nummer', NS).text, '42')

    def test_nummer_im_bereich_wird_nicht_veraendert(self):
        """
        Der XPath muss trennscharf sein: xplan:nummer gibt es auch im
        BP_Bereich - das ist die Bereichsnummer und darf nicht mit der
        Plannummer überschrieben werden.
        """
        plan = self._import_gml('Testplan Proxy Bereich', nummer='100')
        plan.nummer = '999'
        plan.save()

        root = self._export_root(plan)
        bereich_nummern = root.findall(
            'gml:featureMember/xplan:BP_Bereich/xplan:nummer', NS
        )
        for element in bereich_nummern:
            self.assertNotEqual(
                element.text, '999',
                "Die Plannummer wurde fälschlich in den BP_Bereich geschrieben",
            )

    def test_original_gml_in_der_db_bleibt_unveraendert(self):
        """Der Proxy arbeitet auf einer Kopie - das Original bleibt erhalten."""
        plan = self._import_gml('Testplan Original unveraendert', nummer='100')
        original = plan.xplan_gml

        plan.nummer = '999'
        plan.save()
        self._export_root(plan)

        gespeichert = BPlan.objects.get(pk=plan.pk).xplan_gml
        self.assertEqual(gespeichert, original)
        self.assertIn('<xplan:nummer>100</xplan:nummer>', gespeichert)

    def test_name_wird_bewusst_nicht_ueberschrieben(self):
        """
        Im bplan_attribute_array steht 'name' auf overwrite=False - der Name
        aus dem Original-GML bleibt also stehen, auch wenn er in der Datenbank
        geändert wurde. Dieser Test dokumentiert das gewollte Verhalten.
        """
        plan = self._import_gml('Testplan Name Original', nummer='100')

        plan.name = 'Testplan Name Geaendert'
        plan.save()

        root = self._export_root(plan)
        name_element = root.find('gml:featureMember/xplan:BP_Plan/xplan:name', NS)
        self.assertEqual(name_element.text, 'Testplan Name Original')
