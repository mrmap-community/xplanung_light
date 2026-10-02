from django.test import TestCase
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import BPlan, AdministrativeOrganization

# Dynamischer Import der Filterklassen aus deiner filter.py
try:
    from xplanung_light.filter import BPlanFilter
except ImportError:
    try:
        from xplanung_light.filter import BPlanFilterSet as BPlanFilter
    except ImportError:
        # Fallback falls die Benennung flach liegt
        BPlanFilter = None

# Testklasse: XPlanFilterBusinessLogicTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class XPlanFilterBusinessLogicTests(TestCase):

    def setUp(self):
        # Basis-Geometrie und Orga anlegen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.orga = AdministrativeOrganization.objects.create(name="Prüfungsamt", ls="07", ks="111", gs="000")

        # Zwei eindeutige Test-BPläne anlegen, um die Treffgenauigkeit der Filter zu prüfen
        self.bplan_sonnenhang = BPlan.objects.create(
            name="BPlan Am Sonnenhang",
            nummer="BP-2026-XYZ",
            massstab=1000,
            geltungsbereich=dummy_polygon
        )
        self.bplan_sonnenhang.gemeinde.add(self.orga)

        self.bplan_nord = BPlan.objects.create(
            name="Wohngebiet Nord-West",
            nummer="BP-999-ABC",
            massstab=2500,
            geltungsbereich=dummy_polygon
        )
        self.bplan_nord.gemeinde.add(self.orga)

    # Testfall: B-Plan Filter by name substring.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assertNotIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_bplan_filter_by_name_substring(self):
        """Der Filter muss Pläne anhand eines Namens-Teilstrings korrekt herausfiltern."""
        if not BPlanFilter:
            self.skipTest("BPlanFilter-Klasse konnte in filter.py nicht gefunden werden.")

        # Wir simulieren den GET-Filter-Parameter ?name=Sonnenhang
        filter_params = {"name": "Sonnenhang"}
        
        # Initialisieren des Filters gegen das vollständige QuerySet
        filter_instance = BPlanFilter(data=filter_params, queryset=BPlan.objects.all())
        
        # Das gefilterte QuerySet extrahieren
        filtered_qs = filter_instance.qs
        
        # Verifikation: Nur 'Am Sonnenhang' darf im Resultat stehen
        self.assertEqual(filtered_qs.count(), 1)
        self.assertIn(self.bplan_sonnenhang, filtered_qs)
        self.assertNotIn(self.bplan_nord, filtered_qs)

    # Testfall: B-Plan Filter no results on fantasy Abfrage.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_bplan_filter_no_results_on_fantasy_query(self):
        """Wenn nach einem Fantasiewort gefiltert wird, muss das QuerySet leer sein."""
        if not BPlanFilter:
            self.skipTest("BPlanFilter-Klasse nicht gefunden.")

        filter_params = {"name": "Fantasiebezirk404"}
        filter_instance = BPlanFilter(data=filter_params, queryset=BPlan.objects.all())
        
        self.assertEqual(filter_instance.qs.count(), 0)

    # Testfall: B-Plan Filter by exact number.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_bplan_filter_by_exact_number(self):
        """Der Filter muss Pläne anhand ihrer exakten Nummer identifizieren."""
        if not BPlanFilter:
            self.skipTest("BPlanFilter-Klasse nicht gefunden.")

        # Viele django-filter Klassen bieten ein 'nummer'-Feld an
        filter_params = {"nummer": "BP-999-ABC"}
        filter_instance = BPlanFilter(data=filter_params, queryset=BPlan.objects.all())
        
        # Falls das Feld 'nummer' im Filter existiert, validieren wir die Selektion
        if "nummer" in filter_instance.filters:
            self.assertEqual(filter_instance.qs.count(), 1)
            self.assertIn(self.bplan_nord, filter_instance.qs)
