from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import AdministrativeOrganization, FPlan


XPLAN_NS = 'http://www.xplanung.de/xplangml/6/0'
GML_NS = 'http://www.opengis.net/gml/3.2'

# Passend zur Fixture-Organisation (ls=07, ks=316, gs=000)
GUELTIGE_AGS = '07316000'
GUELTIGER_GEMEINDE_NAME = 'Neustadt an der Weinstraße, kreisfreie Stadt'

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>"""

# Bewusst mit xplan:FP_Plan als Wurzel-Feature - so, wie ein echter,
# gültiger FPlan-Export aussieht.
FPLAN_GML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<xplan:XPlanAuszug xmlns:xplan="{xplan_ns}" xmlns:gml="{gml_ns}"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    gml:id="GML_testauszug">
  <gml:featureMember>
    <xplan:FP_Plan gml:id="GML_testplan">
      <xplan:name>Testplan FPlan get_orgas</xplan:name>
      <xplan:nummer>2099</xplan:nummer>
      <xplan:raeumlicherGeltungsbereich>{geometrie}</xplan:raeumlicherGeltungsbereich>
      <xplan:gemeinde>
        <xplan:XP_Gemeinde>
          <xplan:ags>{ags}</xplan:ags>
          <xplan:gemeindeName>{gemeinde_name}</xplan:gemeindeName>
        </xplan:XP_Gemeinde>
      </xplan:gemeinde>
      <xplan:planArt>1000</xplan:planArt>
    </xplan:FP_Plan>
  </gml:featureMember>
</xplan:XPlanAuszug>
""".format(xplan_ns=XPLAN_NS, gml_ns=GML_NS, geometrie=GEOMETRIE,
           ags=GUELTIGE_AGS, gemeinde_name=GUELTIGER_GEMEINDE_NAME)


def upload(content_type='application/gml'):
    return SimpleUploadedFile(
        'fplan_test.gml', FPLAN_GML.encode('utf-8'), content_type=content_type,
    )


class XPlanungGetOrgasFPlanBug(TestCase):
    """
    Regressionstests für einen Bug in XPlanung.get_orgas(): die Methode
    durchsuchte das GML mit einem fest auf xplan:BP_Plan verdrahteten XPath,
    unabhängig vom tatsächlichen Plantyp. Für ein valides FPlan-Dokument
    (Wurzel-Feature xplan:FP_Plan) lieferte sie deshalb immer eine leere
    Liste zurück - auch wenn eine gültige, real existierende Gemeinde
    korrekt angegeben war.

    Das traf direkt die Autorisierungsprüfung in views.fplan_import():

        orgas = xplanung.get_orgas()          # war: [] für jeden FPlan-Import
        user_orga_admin = []
        for gemeinde in orgas:                # lief nie
            ...
        if all(user_orga_admin) == False:     # all([]) ist True in Python!
            # Sperre wurde NICHT ausgelöst

    all([]) ist in Python True - die Sperre griff nur, wenn mindestens eine
    Gemeinde als "nicht Admin" markiert wurde. Bei leerer Liste lief der
    Import durch, unabhängig von der Identität des Nutzers - fplan_import()
    hat zusätzlich kein LoginRequiredMixin/@login_required, das traf im
    schlimmsten Fall auch anonyme Requests.

    Mittlerweile behoben - diese Tests sichern das Verhalten gegen eine
    Regression ab.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)
        # Ein Nutzer ganz ohne AdminOrgaUser-Eintrag für irgendeine
        # Gemeinde - darf laut Fachlogik keinen Plan importieren dürfen.
        cls.fremder_user = User.objects.create_user(
            username='fremder_user_fplan_import', password='nicht-relevant',
        )

    def setUp(self):
        self.client = Client()

    # --- Kern des Bugs: direkter, low-level Test von get_orgas() -----------

    def test_get_orgas_finds_the_gemeinde_for_a_valid_fplan_document(self):
        """
        Regressionstest für den Fix: get_orgas() muss für ein valides
        FPlan-GML mit korrekt referenzierter Gemeinde genau diese Gemeinde
        zurückliefern - vorher lieferte der auf xplan:BP_Plan verdrahtete
        XPath hier fälschlich eine leere Liste.
        """
        xplanung = XPlanung(upload())
        orgas = xplanung.get_orgas()

        self.assertEqual(len(orgas), 1)
        self.assertEqual(orgas[0].pk, self.gemeinde.pk)

    def test_get_orgas_would_find_the_gemeinde_if_root_element_were_bp_plan(self):
        """
        Kontrollprobe: dasselbe GML, nur mit xplan:BP_Plan statt xplan:FP_Plan
        als Element-Namen, findet die Gemeinde korrekt. Das belegt, dass die
        Gemeinde-Daten im GML an sich in Ordnung sind - das Problem liegt
        einzig am hartcodierten Element-Namen im XPath, nicht an fehlenden
        oder falschen Gemeinde-Angaben.
        """
        bplan_variante = FPLAN_GML.replace('xplan:FP_Plan', 'xplan:BP_Plan')
        bplan_upload = SimpleUploadedFile(
            'als_bplan_getarnt.gml', bplan_variante.encode('utf-8'),
            content_type='application/gml',
        )
        xplanung = XPlanung(bplan_upload)
        orgas = xplanung.get_orgas()

        self.assertEqual(len(orgas), 1)
        self.assertEqual(orgas[0].pk, self.gemeinde.pk)

    # --- Auswirkung auf fplan_import(): Autorisierung umgangen -------------

    def test_user_without_any_admin_role_cannot_import_fplan(self):
        """
        Regressionstest für den Fix: ein Nutzer ganz ohne AdminOrgaUser-
        Eintrag für irgendeine Gemeinde darf keinen FPlan importieren.
        Vorher lief der Import durch, weil get_orgas() -> [] die Sperre
        all(user_orga_admin) == False nie auslöste (all([]) ist True).
        """
        self.client.force_login(self.fremder_user)

        response = self.client.post(reverse('fplan-import'), data={
            'file': upload(),
            'confirm': False,
        })

        self.assertEqual(response.status_code, 200)  # Formular mit Fehlermeldung, kein Redirect
        self.assertFalse(FPlan.objects.filter(name='Testplan FPlan get_orgas').exists())

    def test_anonymous_user_cannot_import_fplan(self):
        """
        Wie oben, aber ganz ohne Login. fplan_import() hat weiterhin kein
        LoginRequiredMixin/@login_required - der Schutz kommt hier
        ausschließlich aus der jetzt korrekt funktionierenden
        Admin-Prüfung, nicht aus einer Anmeldepflicht. Ein AnonymousUser
        erfüllt user.user == request.user für keinen echten Admin-Eintrag,
        landet also ebenfalls in der Sperre.
        """
        response = self.client.post(reverse('fplan-import'), data={
            'file': upload(),
            'confirm': False,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FPlan.objects.filter(name='Testplan FPlan get_orgas').exists())
