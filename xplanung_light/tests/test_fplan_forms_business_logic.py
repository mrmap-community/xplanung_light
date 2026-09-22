from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import FPlan, FPlanBeteiligung, FPlanBeteiligungBeitrag
from xplanung_light.forms import FPlanBeteiligungForm

class FPlanFormsBusinessLogicTests(TestCase):

    def setUp(self):
        # Basis-Geometrie für NOT NULL Constraints
        self.dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        # Test-FPlan anlegen
        self.fplan = FPlan.objects.create(
            name="Test-FPlan Logik",
            geltungsbereich=self.dummy_polygon
        )
        
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.gestern = self.heute - timedelta(days=1)

    def test_fplan_beteiligung_form_fails_when_start_after_end_date(self):
        """Das FPlan-Formular muss fehlschlagen, wenn das Startdatum nach dem Enddatum liegt."""
        form_data = {
            'typ': '1000',
            'bekanntmachung_datum': self.heute,
            'start_datum': self.morgen,   # Start morgen
            'end_datum': self.gestern,     # Ende gestern (Logikfehler!)
            'allow_online_beitrag': True,
            'publikation_internet': 'http://example.com'
        }
        
        form = FPlanBeteiligungForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('end_datum', form.errors)
        self.assertIn("Das Enddatum darf nicht vor dem Startdatum liegen.", form.errors['end_datum'])

    def test_fplan_beteiligung_form_prevents_type_change_on_update(self):
        """Djangos disabled=True ignoriert manipulierte Typänderungen beim FPlan und behält den alten Wert bei."""
        # 1. Bestehende Instanz in der DB anlegen (Typ 1000)
        beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            typ='1000',
            bekanntmachung_datum=self.heute,
            start_datum=self.heute,
            end_datum=self.morgen
        )
        
        # 2. Formular mit geänderten Daten füttern (Wechsel auf Typ 2000 erzwungen)
        form_data = {
            'typ': '2000',  # Manipulierter Typwechsel via POST
            'bekanntmachung_datum': self.heute,
            'start_datum': self.heute,
            'end_datum': self.morgen,
            'allow_online_beitrag': True
        }
        
        form = FPlanBeteiligungForm(data=form_data, instance=beteiligung)
        
        # Das Formular bleibt valide, weil disabled=True den manipulierten POST-Wert ignoriert...
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # ...und stattdessen die Instanz mit dem ursprünglichen Typ sichert!
        saved_instance = form.save(commit=False)
        self.assertEqual(saved_instance.typ, '1000', "Sicherheitsfehler: Der gesperrte Typ wurde beim FPlan überschrieben!")

    def test_fplan_form_prevents_modification_when_contributions_exist(self):
        """Wenn beim FPlan bereits Beiträge eingegangen sind, darf das Verfahren nicht mehr geändert werden."""
        beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            typ='1000',
            bekanntmachung_datum=self.heute,
            start_datum=self.heute,
            end_datum=self.morgen
        )
        
        # Künstlich einen FPlan-Beitrag für dieses Verfahren in der DB hinterlegen
        FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=beteiligung,
            titel="Stellungnahme FPlan",
            beschreibung="Inhalt",
            eingangsdatum=self.heute,
            typ=1000
        )
        
        form_data = {
            'typ': '1000',
            'beschreibung': 'Nachträgliche Änderung der Beschreibung',
            'bekanntmachung_datum': self.heute,
            'start_datum': self.heute,
            'end_datum': self.morgen
        }
        
        form = FPlanBeteiligungForm(data=form_data, instance=beteiligung)
        self.assertFalse(form.is_valid())
        # Da der Fehler im Code an None gebunden ist, liegt er in den non_field_errors
        self.assertIn(
            "Es gibt schon Beiträge zum Verfahren - das Verfahren darf daher nicht mehr verändert werden!",
            form.non_field_errors()
        )
