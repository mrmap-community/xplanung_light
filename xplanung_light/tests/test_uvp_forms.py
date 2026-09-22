from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import BPlan, FPlan, Uvp, FPlanUvp
from xplanung_light.forms import UvpForm, FPlanUvpForm

class UvpFormsBusinessLogicTests(TestCase):

    def setUp(self):
        # Basis-Geometrie für NOT NULL Constraints der Pläne
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        # Test-Pläne anlegen, da die UVP-Modelle ForeignKeys darauf verlangen
        self.bplan = BPlan.objects.create(name="BPlan mit UVP", geltungsbereich=dummy_polygon)
        self.fplan = FPlan.objects.create(name="FPlan mit SUP", geltungsbereich=dummy_polygon)
        
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.gestern = self.heute - timedelta(days=1)

    # ==============================================================================
    # 1. TESTS FÜR UvpForm (BPlan-Kontext)
    # ==============================================================================

    def test_uvp_form_happy_path(self):
        """Das UvpForm muss valide sein, wenn korrekte Daten übergeben werden."""
        form_data = {
            "uvp": True,
            "uvp_vp": False,
            "typ": "18_7_1",  # BPlan Außenbereich gemäß deinen Choices in models.py
            "uvp_beginn_datum": self.gestern,
            "uvp_ende_datum": self.heute
        }
        
        form = UvpForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # KORREKTUR: Da bplan nicht im Formular ist, binden wir es wie die Views via commit=False
        saved_uvp = form.save(commit=False)
        saved_uvp.bplan = self.bplan
        saved_uvp.save()
        
        self.assertEqual(saved_uvp.bplan.id, self.bplan.id)
        self.assertEqual(saved_uvp.typ, "18_7_1")

    def test_uvp_form_invalid_date_format(self):
        """Das Formular muss fehlschlagen, wenn ein ungültiges Datumsformat übergeben wird."""
        form_data = {
            "uvp": True,
            "typ": "18_7_1",
            "uvp_beginn_datum": "kein-datum",  # Ungültiger Wert
            "uvp_ende_datum": self.heute
        }
        
        form = UvpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("uvp_beginn_datum", form.errors)

    # ==============================================================================
    # 2. TESTS FÜR FPlanUvpForm (FPlan-Kontext / Strategische Umweltprüfung)
    # ==============================================================================

    def test_fplan_uvp_form_happy_path(self):
        """Das FPlanUvpForm muss valide sein und die angepassten Labels/Hilfetexte nutzen."""
        form_data = {
            "uvp": True,
            "typ": "1000",  # Strategische Umweltprüfung (SUP) gemäß models.py
            "uvp_beginn_datum": self.gestern,
            "uvp_ende_datum": self.heute
        }
        
        form = FPlanUvpForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # Labels- und Help-Text-Checks zur Absicherung der __init__-Anpassungen in forms.py
        self.assertEqual(form.fields['uvp_beginn_datum'].label, "Beginns UP")
        self.assertEqual(form.fields['uvp_ende_datum'].label, "Ende UP")
        
        # KORREKTUR: Da fplan nicht im Formular ist, binden wir es wie die Views via commit=False
        saved_fplan_uvp = form.save(commit=False)
        saved_fplan_uvp.fplan = self.fplan
        saved_fplan_uvp.save()
        
        self.assertEqual(saved_fplan_uvp.fplan.id, self.fplan.id)
        self.assertEqual(saved_fplan_uvp.typ, "1000")

    def test_fplan_uvp_form_invalid_typ_choice(self):
        """Das Formular muss fehlschlagen, wenn ein ungültiger Choice-Wert übergeben wird."""
        form_data = {
            "uvp": True,
            "typ": "99999",  # Ungültiger Typ
            "uvp_beginn_datum": self.gestern,
            "uvp_ende_datum": self.heute
        }
        
        form = FPlanUvpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("typ", form.errors)

