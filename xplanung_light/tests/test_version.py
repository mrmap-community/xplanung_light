"""
Tests für die einzelne Quelle der Versionsnummer und das Kommando "versionsstand".

Die Versionsnummer läuft in mehrere Richtungen: Fußzeile und PDF-Kopf lesen sie
über die Settings, die Sphinx-Doku liest sie aus dem Paketrumpf, publiccode.yml
für das Open-Source-Katalogverzeichnis kann sie nur abschreiben. Genau das
Auschreiben ist der Punkt, an dem es auseinanderläuft - hier die Wächter.
"""

import io
import json
import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

import xplanung_light
from xplanung_light.management.commands import versionsstand as stand_kommando


def quelltext(datei):
    """Der Text einer Datei im Projekt, für die Wächter unter den Tests."""
    return Path(datei).read_text(encoding="utf-8")


class VersionsquelleTests(SimpleTestCase):
    """Es darf genau eine Stelle geben, die eine Versionszahl ausschreibt."""

    def test_die_Settings_zeigen_dieselbe_Version_wie_die_App(self):
        """
        Was wird geprüft:
            Der Wert von settings.XPLANUNG_LIGHT_VERSION gegen
            xplanung_light.__version__.

        Warum:
            Fußzeile, PDF-Kopf und die Middleware lesen die Settings. Steht dort
            eine zweite Zahl, zeigt die Installation etwas anderes als der Code.

        Erwartung:
            Beide sind gleich, und in komserv/settings/base.py steht keine
            ausgeschriebene Versionszahl mehr.
        """
        self.assertEqual(settings.XPLANUNG_LIGHT_VERSION, xplanung_light.__version__)
        basis = quelltext(Path(settings.BASE_DIR) / "komserv" / "settings" / "base.py")
        aktive = [zeile for zeile in basis.splitlines()
                  if not zeile.lstrip().startswith("#")]
        ausgeschriebene = re.findall(
            r'^XPLANUNG_LIGHT_VERSION\s*=\s*["\'][^"\']+["\']', "\n".join(aktive),
            re.MULTILINE)
        self.assertEqual(
            ausgeschriebene, [],
            "base.py schreibt eine Version aus: {}".format(ausgeschriebene))

    def test_publiccode_nennt_dieselbe_Version(self):
        """
        Was wird geprüft:
            softwareVersion in publiccode.yml gegen xplanung_light.__version__.

        Warum:
            publiccode.yml ist statischer Text und kann die Zahl nicht lesen. Die
            Datei war bereits hinterhergelaufen (0.2.0, während die App 0.3.0
            meldete), weil niemand beim Veröffentlichen daran denkt.

        Erwartung:
            Beide nennen dieselbe Zahl.
        """
        offentlich = quelltext(Path(settings.BASE_DIR) / "publiccode.yml")
        fund = re.search(r'^softwareVersion:\s*["\']([^"\']+)["\']',
                         offentlich, re.MULTILINE)
        self.assertIsNotNone(fund, "publiccode.yml hat kein softwareVersion")
        self.assertEqual(
            fund.group(1), xplanung_light.__version__,
            "publiccode.yml und xplanung_light/__init__.py sind sich uneins - "
            "siehe RELEASING.md")

    def test_der_Paketrumpf_bleibt_ohne_Importe(self):
        """
        Was wird geprüft:
            Der Inhalt von xplanung_light/__init__.py auf Importe.

        Warum:
            Die Datei wird beim Laden der Settings und von der Doku gelesen, bevor
            Django und die App bereitstehen. Ein Import von Modellen oder Django
            an dieser Stelle würde beide Wege brechen.

        Erwartung:
            Der Paketrumpf enthält keine Importe, nur die Versionszahl.
        """
        rumpf = quelltext(Path(xplanung_light.__file__))
        aktive = [zeile for zeile in rumpf.splitlines()
                  if not zeile.lstrip().startswith("#")]
        ohne_Text = re.sub(r'""".*?"""', "", "\n".join(aktive), flags=re.DOTALL)
        self.assertEqual(
            re.findall(r"^\s*(import|from)\s+\S+", ohne_Text, re.MULTILINE), [],
            "Der Paketrumpf importiert etwas - Settings und Doku lesen ihn früh")

    def test_die_Doku_liest_dieselbe_Version(self):
        """
        Was wird geprüft:
            Die von docs/source/conf.py ermittelte Version gegen die der App.

        Warum:
            Die Doku soll die Version der Software zeigen, nicht eine zweite, die
            jemand pflegt. Geprüft wird durch Ausführen der Konfiguration, damit
            auch der Weg (Haupt- und Unterart, volle Zahl) kontrolliert ist.

        Erwartung:
            release ist die volle Zahl der App, version die gekürzte.
        """
        konfiguration = Path(settings.BASE_DIR) / "docs" / "source" / "conf.py"
        selbst = {"__file__": str(konfiguration), "__name__": "sphinx_conf_unter_pruefung"}
        exec(compile(quelltext(konfiguration), str(konfiguration), "exec"), selbst)
        voll = xplanung_light.__version__
        self.assertEqual(selbst["release"], voll)
        self.assertEqual(selbst["version"], ".".join(voll.split(".")[:2]))


class RevisionsFinderTests(SimpleTestCase):
    """Die Revisionssuche darf außerhalb einer Git-Kopie nicht scheitern."""

    def test_ohne_Git_gibt_es_keine_Revision(self):
        """
        Was wird geprüft:
            Die Antwort der Revisionssuche, wenn git nicht antwortet.

        Warum:
            Installationen werden aus Tarballs oder Paketen gesetzt, ohne
            .git-Verzeichnis; die Ausgabe des Kommandos darf deshalb nicht
            abbrechen.

        Erwartung:
            None, sowohl wenn der Aufruf fehlschlägt als auch wenn git mit
            Fehlercode antwortet.
        """
        with patch.object(stand_kommando.subprocess, "run",
                          side_effect=OSError("kein git")):
            self.assertIsNone(stand_kommando.revisions_bezeichnung())

        fake = type("Ergebnis", (), {"returncode": 128, "stdout": ""})()
        with patch.object(stand_kommando.subprocess, "run", return_value=fake):
            self.assertIsNone(stand_kommando.revisions_bezeichnung())

    def test_mit_Git_wird_die_Beschreibung_gelesen(self):
        """
        Was wird geprüft:
            Die Revisionssuche bei einer erfolgreichen Antwort von git.

        Warum:
            Der Wert ist der eigentliche Grund für das Kommando: die Frage, ob ein
            Rechner dem letzten Stand entspricht, wird damit beantwortet.

        Erwartung:
            Die Ausgabe von git, ohne das abschließende Zeilenende.
        """
        fake = type("Ergebnis", (), {"returncode": 0, "stdout": "0.3.0-14-g1a2b3c4\n"})()
        with patch.object(stand_kommando.subprocess, "run", return_value=fake):
            self.assertEqual(
                stand_kommando.revisions_bezeichnung(Path("/")),
                "0.3.0-14-g1a2b3c4")


class VersionskommandoTests(TestCase):
    """Das Kommando muss laufen und die Version nennen, auf jeder Installation."""

    def test_die_Ausgabe_nennt_Version_und_Fassungen(self):
        """
        Was wird geprüft:
            Die Textausgabe des Kommandos "version".

        Warum:
            Das Kommando ist der erste Griff bei einer Fehlermeldung aus dem
            Betrieb; es läuft auf jeder Installation, auch ohne Git und ohne
            MapServer-Bindung.

        Erwartung:
            Die Versionszahl steht in der Ausgabe, ebenso die Fassungen von
            Datenbank und Kartenserver - letztere auch als Hinweis, wenn
            mapscript nicht importierbar ist.
        """
        ausgabe = io.StringIO()
        call_command("versionsstand", stdout=ausgabe)
        text = ausgabe.getvalue()
        self.assertIn(xplanung_light.__version__, text)
        self.assertIn("XPlanung-light:", text)
        self.assertIn("Datenbank:", text)
        self.assertIn("Kartenserver:", text)
        self.assertNotIn("Achtung: settings XPLANUNG_LIGHT_VERSION", text)

    def test_die_Ausgabe_als_Json_ist_maschinenlesbar(self):
        """
        Was wird geprüft:
            Die Ausgabe des Kommandos mit --json.

        Warum:
            Fehlermeldungen und Skripte sollen die Angaben übernehmen können,
            ohne Text zu zerlegen.

        Erwartung:
            Gültiges JSON mit den Schlüsselangaben, Warnungen als Liste.
        """
        ausgabe = io.StringIO()
        call_command("versionsstand", json=True, stdout=ausgabe)
        angaben = json.loads(ausgabe.getvalue())
        self.assertEqual(angaben["version"], xplanung_light.__version__)
        for schluessel in ("revision", "python", "django", "datenbank",
                           "kartenserver", "gdal", "geos", "migrationen", "warnungen"):
            self.assertIn(schluessel, angaben)

    def test_offene_Migrationen_werden_gemeldet(self):
        """
        Was wird geprüft:
            Die Warnung des Kommandos, wenn die Bank Migrationen noch nicht hat.

        Warum:
            Der häufigste Update-Fehler ist gelaufener Code über einer nicht
            nachgezogenen Bank; das Kommando soll das als Erstes sagen.

        Erwartung:
            Die Warnung erscheint, und die Zahl der offenen Migrationen steht da.
        """
        stand = {"angewandt": 94, "offen": ["xplanung_light.0099_fehtlt"], "fehler": None}
        with patch.object(stand_kommando, "migrations_stand", return_value=stand):
            ausgabe = io.StringIO()
            call_command("versionsstand", stdout=ausgabe)
            text = ausgabe.getvalue()
        self.assertIn("Achtung:", text)
        self.assertIn("1 offen", text)

    def test_eine_abweichende_Settings_Version_wird_gemeldet(self):
        """
        Was wird geprüft:
            Die Warnung des Kommandos, wenn eine Installations-Settings-Datei die
            Version überschreibt.

        Warum:
            Genau dieser Fall ist mit der Umstellung auf eine Quelle nicht mehr
            ausgeschlossen: prod.py liegt nicht im Git und kann die Zahl setzen.
            Das Kommando soll es sagen, statt stillschweigend zwei Zahlen zu zeigen.

        Erwartung:
            Die Warnung erscheint in der Ausgabe und in der JSON-Liste.
        """
        with override_settings(XPLANUNG_LIGHT_VERSION="0.0.0-test"):
            ausgabe = io.StringIO()
            call_command("versionsstand", stdout=ausgabe)
            self.assertIn("Achtung:", ausgabe.getvalue())

            ausgabe = io.StringIO()
            call_command("versionsstand", json=True, stdout=ausgabe)
            warnungen = json.loads(ausgabe.getvalue())["warnungen"]
            self.assertTrue(any("XPLANUNG_LIGHT_VERSION" in w for w in warnungen))
