import io
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import BPlan


XPLAN_NS = 'http://www.xplanung.de/xplangml/6/0'
GML_NS = 'http://www.opengis.net/gml/3.2'

# Passend zur Fixture-Organisation (ls=07, ks=316, gs=000)
AGS = '07316000'
GEMEINDE_NAME = 'Neustadt an der Weinstraße, kreisfreie Stadt'

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
  <gml:exterior>
    <gml:LinearRing>
      <gml:posList>430000.000 5470000.000 430200.000 5470000.000 430200.000 5470200.000 430000.000 5470200.000 430000.000 5470000.000</gml:posList>
    </gml:LinearRing>
  </gml:exterior>
</gml:Polygon>"""


def make_bplan_gml(name, nummer='2099'):
    return f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<xplan:XPlanAuszug xmlns:xplan="{XPLAN_NS}" xmlns:gml="{GML_NS}"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    gml:id="GML_testauszug">
  <gml:featureMember>
    <xplan:BP_Plan gml:id="GML_testplan">
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
    </xplan:BP_Plan>
  </gml:featureMember>
</xplan:XPlanAuszug>
"""


def make_zip_bytes(files):
    """files: dict {dateiname_im_zip: inhalt_als_str_oder_bytes}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for filename, content in files.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            zf.writestr(filename, content)
    return buf.getvalue()


def zip_upload(files, filename='archiv.zip', content_type='application/zip'):
    return SimpleUploadedFile(filename, make_zip_bytes(files), content_type=content_type)


class XPlanungImportPlanArchiv(TestCase):
    """
    Tests direkt auf Klassenebene (XPlanung.__init__/get_orgas()/
    import_plan_archiv()) - bypasst bewusst Formular/View-Schicht, um
    unabhängig von bplan_upload_file_validator (validators.py, dessen
    aktuellen Stand ich nicht geprüft habe) belastbare Aussagen über den
    ZIP-Handling-Code selbst treffen zu können.

    bplan_import_archiv()/fplan_import_archiv() (views.py) waren bisher
    komplett ungetestet - anders als der einzelne-GML-Import
    (bplan_import()/fplan_import(), siehe test_import_export.py und
    test_xplanung_get_orgas_fplan_bug.py).
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    def setUp(self):
        self.client = Client()

    # --- ZIP-Entpacken in XPlanung.__init__ ---------------------------

    def test_zip_without_any_gml_file_raises_attributeerror(self):
        """
        Enthält das ZIP keine Datei, die auf '.gml' endet UND einen der
        akzeptierten MimeTypes hat, wird self.xml_string in __init__() nie
        gesetzt. Jeder nachfolgende Zugriff (get_orgas(), import_plan_archiv())
        crasht dann mit AttributeError statt einer sprechenden Fehlermeldung.
        """
        upload = zip_upload({'liesmich.txt': 'Kein GML hier drin.'})
        xplanung = XPlanung(upload)

        with self.assertRaises(AttributeError):
            xplanung.get_orgas()

    def test_zip_with_uppercase_gml_extension_is_not_recognized(self):
        """
        __init__() prüft file.filename.endswith('.gml') - case-sensitiv.
        Ein ZIP mit PLAN.GML (Großschreibung, wie sie manche GIS-Tools beim
        Export erzeugen) wird deshalb nicht als GML erkannt, obwohl der
        Inhalt vollkommen valide ist.
        """
        upload = zip_upload({'PLAN.GML': make_bplan_gml('Großschreibungs-Testplan')})
        xplanung = XPlanung(upload)

        with self.assertRaises(AttributeError):
            xplanung.get_orgas()

    def test_zip_with_valid_lowercase_gml_is_extracted_and_parsed(self):
        """
        Positiv-Gegenprobe zu den beiden Tests oben: ein korrekt benanntes
        .gml im ZIP wird gefunden, entpackt und von get_orgas() korrekt
        ausgewertet.
        """
        upload = zip_upload({'plan.gml': make_bplan_gml('Testplan aus ZIP')})
        xplanung = XPlanung(upload)

        orgas = xplanung.get_orgas()

        self.assertEqual(len(orgas), 1)
        self.assertEqual(orgas[0].ags, AGS)

    # --- import_plan_archiv(): bisher komplett ungetestete Kernfunktion ----

    def test_import_plan_archiv_creates_bplan_with_core_fields(self):
        name = 'Archiv-Import-Test BPlan'
        upload = zip_upload({'plan.gml': make_bplan_gml(name, nummer='777')})

        created = XPlanung(upload).import_plan_archiv(overwrite=False, plan_typ='bplan')

        self.assertTrue(created, 'Import aus dem ZIP-Archiv ist fehlgeschlagen')
        plan = BPlan.objects.get(name=name)
        self.assertEqual(plan.nummer, '777')
        self.assertEqual(
            list(plan.gemeinde.values_list('ls', 'ks', 'gs')),
            [('07', '316', '000')],
        )

    def test_import_plan_archiv_without_overwrite_does_not_duplicate(self):
        name = 'Archiv-Import-Test Duplicate'
        content = make_bplan_gml(name)

        erster = XPlanung(zip_upload({'plan.gml': content})).import_plan_archiv(
            overwrite=False, plan_typ='bplan',
        )
        self.assertTrue(erster)
        self.assertEqual(BPlan.objects.filter(name=name).count(), 1)

        zweiter = XPlanung(zip_upload({'plan.gml': content})).import_plan_archiv(
            overwrite=False, plan_typ='bplan',
        )
        self.assertFalse(
            zweiter,
            'import_plan_archiv() sollte False liefern, wenn der Plan schon '
            'existiert und overwrite=False gesetzt ist.',
        )
        self.assertEqual(BPlan.objects.filter(name=name).count(), 1)


class ImportArchivViewFormAndTemplate(TestCase):
    """
    HINWEIS: dieser Test hängt vom aktuellen Stand von
    bplan_upload_file_validator (validators.py) ab, den ich nicht geprüft
    habe - falls er an einem Formularfehler statt am erwarteten Verhalten
    scheitert, liegt das voraussichtlich daran, nicht an einer falschen
    Diagnose des unten beschriebenen Bugs.

    BEFUND: in bplan_import_archiv() (views.py) wird im
    "Nutzer ist nicht Administrator aller Gemeinden"-Zweig
    `form = BPlanImportForm()` (statt BPlanImportArchivForm) gesetzt und
    "xplanung_light/bplan_import.html" (statt .../bplan_import_archiv.html)
    gerendert - ein Copy-Paste-Rest aus bplan_import(). Analog bei
    fplan_import_archiv() mit FPlanImportForm/fplan_import.html.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    def setUp(self):
        self.client = Client()
        self.fremder_user = User.objects.create_user(
            username='fremder_user_archiv_import', password='nicht-relevant',
        )
        self.client.force_login(self.fremder_user)

    def test_permission_denied_branch_uses_wrong_form_and_template(self):
        upload = zip_upload({'plan.gml': make_bplan_gml('Archiv Permission Test')})

        response = self.client.post(reverse('bplan-import-archiv'), data={
            'file': upload, 'confirm': False,
        })

        self.assertEqual(response.status_code, 200)  # kein Redirect, Formular wird neu gezeigt
        self.assertFalse(BPlan.objects.filter(name='Archiv Permission Test').exists())

        # Erwartetes (fehlerhaftes) Verhalten: form/Template gehören zur
        # Einzel-GML-Import-Variante statt zur Archiv-Variante.
        self.assertEqual(type(response.context['form']).__name__, 'BPlanImportForm')
        self.assertIn('xplanung_light/bplan_import.html', [t.name for t in response.templates])
