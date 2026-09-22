from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag, BPlanSpezExterneReferenz
from xplanung_light.forms import BPlanBeteiligungForm, BPlanSpezExterneReferenzForm

class BPlanFormsBusinessLogicTests(TestCase):

    def setUp(self):
        # Basis-Geometrie für NOT NULL Constraints
        self.dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        
        # Test-BPlan anlegen
        self.bplan = BPlan.objects.create(
            name="Testplan Logik",
            geltungsbereich=self.dummy_polygon
        )
        
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.gestern = self.heute - timedelta(days=1)

    # ==============================================================================
    # 1. TESTS FÜR BPlanBeteiligungForm (Datum, Typen, Beitragssperren)
    # ==============================================================================

    def test_beteiligung_form_fails_when_start_after_end_date(self):
        """Das Formular muss fehlschlagen, wenn das Startdatum nach dem Enddatum liegt."""
        form_data = {
            'typ': '1000',
            'bekanntmachung_datum': self.heute,
            'start_datum': self.morgen,   # Start morgen
            'end_datum': self.gestern,     # Ende gestern (Logikfehler!)
            'allow_online_beitrag': True,
            'publikation_internet': 'http://example.com'
        }
        
        form = BPlanBeteiligungForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('end_datum', form.errors)
        self.assertIn("Das Enddatum darf nicht vor dem Startdatum liegen.", form.errors['end_datum'])

    def test_beteiligung_form_prevents_type_change_on_update(self):
        """Djangos disabled=True ignoriert manipulierte Typänderungen und behält den alten Wert bei."""
        # 1. Bestehende Instanz in der DB anlegen (Typ 1000)
        beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
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
        
        form = BPlanBeteiligungForm(data=form_data, instance=beteiligung)
        
        # KORREKTUR: Das Formular bleibt valide, weil disabled=True den manipulierten POST-Wert ignoriert...
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # ...und stattdessen die Instanz mit dem ursprünglichen Typ sichert!
        saved_instance = form.save(commit=False)
        self.assertEqual(saved_instance.typ, '1000', "Sicherheitsfehler: Der gesperrte Typ wurde überschrieben!")

    def test_form_prevents_modification_when_contributions_exist(self):
        """Wenn bereits Beiträge eingegangen sind, darf das Verfahren nicht mehr geändert werden."""
        beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            typ='1000',
            bekanntmachung_datum=self.heute,
            start_datum=self.heute,
            end_datum=self.morgen
        )
        
        # Künstlich einen Beitrag für dieses Verfahren in der DB hinterlegen
        BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=beteiligung,
            titel="Stellungnahme",
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
        
        form = BPlanBeteiligungForm(data=form_data, instance=beteiligung)
        self.assertFalse(form.is_valid())
        # Da der Fehler im Code an None gebunden ist, liegt er in den non_field_errors
        self.assertIn(
            "Es gibt schon Beiträge zum Verfahren - das Verfahren darf daher nicht mehr verändert werden!",
            form.non_field_errors()
        )

    # ==============================================================================
    # 2. TESTS FÜR BPlanSpezExterneReferenzForm (Rasterkarten-Kopplung)
    # ==============================================================================

    def test_spez_externe_referenz_form_triggers_raster_validator_on_type_1070(self):
        """Wenn Typ '1070' (Karte) gewählt ist, muss die angehängte Datei auf Bildintegrität geprüft werden."""
        # Wir übergeben eine korrupte Bilddatei
        corrupted_img = SimpleUploadedFile("karte.tif", b"Plain-Text-statt-Bilddaten", content_type="image/tiff")
        
        form_data = {
            "public": True,
            "typ": "1070",  # Triggert laut clean() den geotiff_raster_validator
            "name": "Planungskarte",
        }
        file_data = {
            "attachment": corrupted_img
        }
        
        form = BPlanSpezExterneReferenzForm(data=form_data, files=file_data)
        # Da das Bild korrupt ist, muss der im clean() aufgerufene geotiff_raster_validator fehlschlagen
        # und eine ValidationError werfen, die das Formular invalid macht.
        self.assertFalse(form.is_valid())

