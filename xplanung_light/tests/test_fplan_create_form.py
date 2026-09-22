from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization, FPlan
from xplanung_light.forms import FPlanCreateForm

class FPlanCreateFormTests(TestCase):

    def setUp(self):
        # 1. Erstelle eine Beispiel-Kommune (ls, ks, gs einzeln wegen des ags-properties)
        self.gemeinde_a = AdministrativeOrganization.objects.create(
            name="Verbandsgemeinde Schilda",
            ls="07",
            ks="111",
            gs="000"
        )
        
        # 2. Definiere typische Datumsstufen
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.vor_einem_jahr = self.heute - timedelta(days=365)

    def test_fplan_create_form_happy_path(self):
        """Das Formular muss valide sein, wenn korrekte FPlan-Daten und eine Geometrie übergeben werden."""
        form_data = {
            "name": "Flächennutzungsplan 2026 Gesamtstadt",
            "nummer": "FP-2026-001",
            "public": True,
            "planart": "1000",  # 'FPlan' gemäß FPLAN_TYPE_CHOICES in models.py
            "massstab": 5000,
            "beschreibung": "Fortschreibung des gemeinsamen Flächennutzungsplans.",
            "gemeinde": [self.gemeinde_a.id],  # DAL-Autocomplete ID-Array
            "geltungsbereich": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",  # WKT-Geometrie
            
            # FPlan-spezifische Datumsstufen mitschicken
            "aufstellungsbeschluss_datum": self.vor_einem_jahr,
            "planbeschluss_datum": self.gestern,
            "wirksamkeits_datum": self.heute
        }
        
        form = FPlanCreateForm(data=form_data)
        
        # Verifiziert, dass die DAL- und GeoDjango-Feldtypen fehlerfrei validieren
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # Speichern und Datenbank-Integrität prüfen
        saved_fplan = form.save()
        self.assertEqual(saved_fplan.name, "Flächennutzungsplan 2026 Gesamtstadt")
        self.assertEqual(saved_fplan.nummer, "FP-2026-001")
        self.assertEqual(saved_fplan.gemeinde.count(), 1)
        self.assertIsInstance(saved_fplan.geltungsbereich, GEOSGeometry)

    def test_fplan_create_form_fails_without_required_fields(self):
        """Das Formular ist ungültig, wenn Name oder Geltungsbereich fehlen."""
        form_data = {
            "name": "",  # Fehler: Pflichtfeld fehlt
            "nummer": "FP-123",
            "public": False,
            "planart": "1000",
            "gemeinde": [self.gemeinde_a.id],
            "geltungsbereich": ""  # Fehler: Pflichtfeld fehlt
        }
        
        form = FPlanCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("geltungsbereich", form.errors)
