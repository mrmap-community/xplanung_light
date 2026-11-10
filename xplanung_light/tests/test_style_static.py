"""
Tests der Style-Parametrisierung (Setting XPLANUNG_STYLE + Context-Processor).

Was wird geprüft: Dass die ausgelieferten Style-Pfade (site.css,
Dashboard-Bilder) vom Setting XPLANUNG_STYLE abhaengen und die alten
Fixed-Pfade nicht mehr vorkommen.

Warum: Die Style-Assets liegen jetzt unter static/style/<style>/, damit pro
Umgebung ein anderer Style gewaehlt werden kann, ohne Templates anzufassen.
Ohne Regressionstest wuerde ein kaputter Context-Processor oder ein hart
codierter Altpfad unbemerkt alle Seiten ohne Stylesheet dastehen lassen.

Erwartung: Home liefert die Pfade "/static/style/default/..." (bzw. des
eingestellten Styles) fuer site.css und die Dashboard-Bilder; die Altpfade
"xplanung_light/site.css" und "beispiel_"-Bildnamen erscheinen nirgends.
"""

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse


class StylePfadeTests(TestCase):
    """Die ausgelieferten Asset-Pfade folgen dem Setting XPLANUNG_STYLE."""

    def test_home_liefert_default_style_pfade(self):
        """Ohne Ueberschreibung muss Home site.css und Bilder aus
        static/style/default/ referenzieren."""
        antwort = self.client.get(reverse("home"))
        self.assertEqual(antwort.status_code, 200)
        inhalt = antwort.content.decode()
        self.assertIn("/static/style/default/css/site.css", inhalt)
        self.assertIn("/static/style/default/img/home/bplan.png", inhalt)

    def test_home_ohne_altpfade(self):
        """Die Altpfade vor dem Umzug duerfen in keinem Template mehr
        auftauchen, sonst liefern sie 404 (Dateien sind umgezogen)."""
        antwort = self.client.get(reverse("home"))
        inhalt = antwort.content.decode()
        self.assertNotIn("xplanung_light/site.css", inhalt)
        self.assertNotIn("beispiel_", inhalt)

    @override_settings(XPLANUNG_STYLE="sonderstyle")
    def test_style_ueberschreibbar(self):
        """Ein anderer Setting-Wert muss alle Style-Pfade umstellen - das ist
        die eigentliche Parametrisierung fuer Kommunenumgebungen."""
        antwort = self.client.get(reverse("home"))
        inhalt = antwort.content.decode()
        self.assertIn("/static/style/sonderstyle/css/site.css", inhalt)
        self.assertIn("/static/style/sonderstyle/img/home/bplan.png", inhalt)
        self.assertNotIn("/static/style/default/", inhalt)
