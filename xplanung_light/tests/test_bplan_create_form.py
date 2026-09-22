from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization, BPlan
from xplanung_light.forms import BPlanCreateForm

class BPlanCreateFormTests(TestCase):

    def setUp(self):
        # 1. Erstelle eine Beispiel-Kommune für das ManyToMany-Feld 'gemeinde'
        # Wir befüllen die Felder ls, ks, gs einzeln wegen des schreibgeschützten properties 'ags'
        self.gemeinde_a = AdministrativeOrganization.objects.create(
            name="Ortsgemeinde Schilda",
            ls="07",
            ks="111",
            gs="000"
        )
        
        # 2. Definiere typische Datumsstufen
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.vor_einem_jahr = self.heute - timedelta(days=365)

    def test_bplan_create_form_happy_path(self):
        """Das Formular muss valide sein, wenn alle Pflichtdaten und eine gültige Geometrie übergeben werden."""
        form_data = {
            "name": "Bebauungsplan Am Sonnenhang",
            "nummer": "BP-2026-001",
            "public": True,
            "planart": "10000",  # 'EinfacherBPlan' gemäß BPLAN_TYPE_CHOICES in models.py
            "massstab": 1000,
            "beschreibung": "Manuelle Erstellung eines einfachen BPlans für ein Wohngebiet.",
            "gemeinde": [self.gemeinde_a.id],  # Primärschlüssel-Array für das GemeindeSelect2-Widget
            "geltungsbereich": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",  # WKT-String für das GIS-Feld
            
            # Datumsfelder mitschicken
            "aufstellungsbeschluss_datum": self.vor_einem_jahr,
            "satzungsbeschluss_datum": self.gestern,
            "inkrafttretens_datum": self.heute
        }
        
        form = BPlanCreateForm(data=form_data)
        
        # Verifiziert, dass die GIS- und Autocomplete-Widgets fehlerfrei validieren
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # In DB speichern und Attribute validieren
        saved_bplan = form.save()
        self.assertEqual(saved_bplan.name, "Bebauungsplan Am Sonnenhang")
        self.assertEqual(saved_bplan.nummer, "BP-2026-001")
        self.assertEqual(saved_bplan.gemeinde.count(), 1)
        
        # Prüfen, ob die Geometrie korrekt verarbeitet wurde
        self.assertIsInstance(saved_bplan.geltungsbereich, GEOSGeometry)

    def test_bplan_create_form_fails_without_required_fields(self):
        """Das Formular ist invalid und blockiert das Speichern, wenn zwingende Felder fehlen."""
        form_data = {
            "name": "",  # Fehler: Name ist ein Pflichtfeld
            "nummer": "BP-123",
            "public": False,
            "planart": "1000",
            "gemeinde": [self.gemeinde_a.id],
            "geltungsbereich": ""  # Fehler: Geltungsbereich/Geometrie darf nicht leer sein
        }
        
        form = BPlanCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("geltungsbereich", form.errors)
