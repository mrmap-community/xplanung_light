"""
Tests der Import-Klasse XPlanung (helper/xplanung.py) auf deren Verzweigungen:
Versionserkennung (5.1/5.4), Fehlerzweige von Import und Archiv-Import
(unbekannte Gemeinde, fehlendes Planelement, fehlende Plannummer, Speicherfehler),
externe Referenzen aus ZIP-Archiven (inkl. Prüfung georeferenzierter Scans) sowie
die GML-Proxies mit Anlagen und historischen Versionen.
"""

import io
import zipfile
from unittest.mock import patch

from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model as DjangoModel
from django.test import TestCase

import xplanung_light.helper.xplanung as xplanung_helper
from xplanung_light.helper.xplanung import XPlanung
from xplanung_light.models import (
    AdministrativeOrganization,
    BPlan,
    BPlanSpezExterneReferenz,
    FPlan,
    FPlanSpezExterneReferenz,
)

XPLAN_NS_60 = "http://www.xplanung.de/xplangml/6/0"
XPLAN_NS_54 = "http://www.xplanung.de/xplangml/5/4"
XPLAN_NS_51 = "http://www.xplanung.de/xplangml/5/1"
GML_NS = "http://www.opengis.net/gml/3.2"

AGS = "07316000"
GEMEINDE_NAME = "Testgemeinde Weinstraße"

GEOMETRIE = """<gml:Polygon srsName="EPSG:25832" gml:id="GML_geltungsbereich">
  <gml:exterior>
    <gml:LinearRing>
      <gml:posList>
        430000.000 5470000.000
        430200.000 5470000.000
        430200.000 5470200.000
        430000.000 5470200.000
        430000.000 5470000.000
      </gml:posList>
    </gml:LinearRing>
  </gml:exterior>
</gml:Polygon>"""

REFERENZ_VORLAGE = """<xplan:externeReferenz>
  <xplan:XP_SpezExterneReferenz>
    <xplan:referenzName>{name}</xplan:referenzName>
    <xplan:referenzURL>{datei}</xplan:referenzURL>
    <xplan:typ>{typ}</xplan:typ>
  </xplan:XP_SpezExterneReferenz>
</xplan:externeReferenz>"""


def make_gml(plan_element="BP_Plan", name="Testplan", nummer="2099",
             xplan_ns=XPLAN_NS_60, extra_elemente=""):
    """
    Erzeugt ein minimales XPlanung-GML mit wählbarem Planelement, Version,
    Nummer und zusätzlichen Elementen (für externe Referenzen). nummer=None
    lässt das Nummer-Element ganz weg.
    """
    nummer_element = f"<xplan:nummer>{nummer}</xplan:nummer>" if nummer else ""
    return f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<xplan:XPlanAuszug
    xmlns:xplan="{xplan_ns}"
    xmlns:gml="{GML_NS}"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    gml:id="GML_testauszug">
  <gml:featureMember>
    <xplan:{plan_element} gml:id="GML_testplan">
      <xplan:name>{name}</xplan:name>
      {nummer_element}
      <xplan:raeumlicherGeltungsbereich>{GEOMETRIE}</xplan:raeumlicherGeltungsbereich>
      <xplan:gemeinde>
        <xplan:XP_Gemeinde>
          <xplan:ags>{AGS}</xplan:ags>
          <xplan:gemeindeName>{GEMEINDE_NAME}</xplan:gemeindeName>
        </xplan:XP_Gemeinde>
      </xplan:gemeinde>
      <xplan:planArt>1000</xplan:planArt>
      {extra_elemente}
    </xplan:{plan_element}>
  </gml:featureMember>
</xplan:XPlanAuszug>
"""


def gml_upload(gml_text, filename="testplan.gml"):
    """Verpackt GML-Text als Einzel-Upload (kein ZIP)."""
    return SimpleUploadedFile(filename, gml_text.encode("utf-8"),
                              content_type="application/gml")


def zip_upload(gml_text, dateien=None, filename="plan.zip"):
    """Verpackt GML plus weitere Dateien als ZIP-Upload (Archiv-Import)."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as zf:
        zf.writestr("plan.gml", gml_text)
        for name, inhalt in (dateien or {}).items():
            zf.writestr(name, inhalt)
    return SimpleUploadedFile(filename, puffer.getvalue(),
                              content_type="application/zip")


def magic_wiehrt_dateityp(puffer, mime=True):
    """
    Ersetzt libmagic durch eine Signature-Erkennung, damit die Tests ohne echte
    TIFF-/PDF-Binärdateien auskommen. Der defekte Scan (Typ 99999, aber kein
    TIFF) fällt bewusst durch die Prüfung.
    """
    if puffer.startswith(b"II-TIFFTEST"):
        return "image/tiff"
    return "text/plain"


class XPlanungImportTests(TestCase):
    """Versionserkennung und Fehlerzweige des GML-Imports (ohne ZIP)."""

    def setUp(self):
        AdministrativeOrganization.objects.create(
            name=GEMEINDE_NAME, ls=AGS[:2], ks=AGS[2:5], gs=AGS[5:8])

    def test_get_orgas_bekaennt_unbekannte_gemeinde_verletzung_ein(self):
        """
        Was wird geprüft:
            get_orgas mit einem GML, dessen Gemeinde nicht in der Datenbank ist.

        Warum:
            Die Ausnahme-Behandlung von get_orgas (und damit der Fehlschlag eines
            Imports mit unbekannter Kommune) war ungetestet.

        Erwartung:
            ValidationError mit dem Hinweis auf die fehlenden Gemeinden.
        """
        gml = make_gml(name="Fiktionsplan")
        gml = gml.replace(AGS, "07999999").replace(GEMEINDE_NAME, "Nimmerstadt")
        mit_helfer = XPlanung(gml_upload(gml))
        with self.assertRaises(forms.ValidationError):
            mit_helfer.get_orgas()

    def test_import_plan_erkennt_versionen_54_und_51(self):
        """
        Was wird geprüft:
            Import von GML-Dokumenten mit den Namespace-URIs 5.4 und 5.1.

        Warum:
            import_planmerkt die Dokumentversion über den Namespace; nur die
            6.0-Variante war bisher durchgetestet.

        Erwartung:
            Beide Pläne werden angelegt und tragen "5.4" bzw. "5.1" als
            xplan_gml_version.
        """
        for version, ns in (("5.4", XPLAN_NS_54), ("5.1", XPLAN_NS_51)):
            with self.subTest(version=version):
                gml = make_gml(name=f"Altversion {version}", xplan_ns=ns)
                selbst = XPlanung(gml_upload(gml)).import_plan(plan_typ="bplan")
                self.assertTrue(selbst)
                plan = BPlan.objects.get(name=f"Altversion {version}")
                self.assertEqual(plan.xplan_gml_version, version)

    def test_import_plan_raegt_unbekannte_gemeinde_ab(self):
        """
        Was wird geprüft:
            import_plan mit einem GML, dessen Gemeinde fehlt.

        Warum:
            Auch im Import selbst (nicht nur in get_orgas) wird die Gemeinde
            nachgeschlagen; der Fehlerzweig war ungetestet.

        Erwartung:
            ValidationError, kein neuer Plan.
        """
        gml = make_gml(name="Obdachloser Plan").replace(AGS, "07999999")
        with self.assertRaises(forms.ValidationError):
            XPlanung(gml_upload(gml)).import_plan()
        self.assertFalse(BPlan.objects.filter(name="Obdachloser Plan").exists())

    def test_import_plan_ueberschreibt_nummer_bei_overwrite(self):
        """
        Was wird geprüft:
            Zweiter Import desselben Plans mit overwrite=True und geänderter
            Plannummer.

        Warum:
            Der Überschreibungs-Zweig von import_plan war ohne Nummer getestet —
            die Übernahme der Nummer ins Bestandsobjekt (existing_plan.nummer)
            damit nie ausgeführt.

        Erwartung:
            import_plan liefert True und der Bestandsplan trägt die neue Nummer.
        """
        XPlanung(gml_upload(make_gml(name="Wandelplan", nummer="A-1"))).import_plan()
        zweiter = XPlanung(gml_upload(make_gml(name="Wandelplan", nummer="B-2")))
        self.assertTrue(zweiter.import_plan(overwrite=True))
        plan = BPlan.objects.get(name="Wandelplan")
        self.assertEqual(plan.nummer, "B-2")
        self.assertEqual(BPlan.objects.filter(name="Wandelplan").count(), 1)

    def test_import_plan_wird_bei_speicherfehler_abgewehrt(self):
        """
        Was wird geprüft:
            import_plan, wenn das zweite Speichern des neu angelegten Plans
            (nach Gemeinde-Zuordnung) fehlschlägt.

        Warum:
            Scheitert das eigentliche Ablegen des Plans, muss der Nutzer eine
            saubere ValidationError-Meldung bekommen statt eines rohen Tracebacks.

        Erwartung:
            ValidationError mit dem Hinweis "Fehler beim Abspeichern".
        """
        aufrufe = []

        def zweiter_aufruf_fehlt(selbst, *args, **kwargs):
            aufrufe.append(1)
            if len(aufrufe) == 2:
                raise Exception("simulierter Datenbankfehler")
            return DjangoModel.save(selbst, *args, **kwargs)

        with patch.object(BPlan, "save", autospec=True,
                          side_effect=zweiter_aufruf_fehlt):
            with self.assertRaisesRegex(forms.ValidationError, "Abspeichern"):
                XPlanung(gml_upload(make_gml(name="Kaputtgespeicherter Plan"))).import_plan()
        self.assertGreaterEqual(len(aufrufe), 2)


class XPlanungArchivImportTests(TestCase):
    """Archiv-Import (ZIP) inklusive externer Referenzen und seiner Fehlerzweige."""

    def setUp(self):
        AdministrativeOrganization.objects.create(
            name=GEMEINDE_NAME, ls=AGS[:2], ks=AGS[2:5], gs=AGS[5:8])

    def test_import_plan_archiv_ohne_planelement_liefert_false(self):
        """
        Was wird geprüft:
            import_plan_archiv, wenn das erwartete Planelement (BP_Plan) im GML
            fehlt (Dokument enthält nur einen FP_Plan).

        Warum:
            Der Parser liest den Pfad über das Planelement; fehlt es, soll der
            Import still mit False abbrechen statt den Nutzer mit einer
            Exception zurückzulassen.

        Erwartung:
            Rückgabe False, keine Exception.
        """
        gml = make_gml(plan_element="FP_Plan", name="Falscher Typ")
        ergebnis = XPlanung(gml_upload(gml)).import_plan_archiv(plan_typ="bplan")
        self.assertFalse(ergebnis)

    def test_import_plan_archiv_ohne_plannummer(self):
        """
        Was wird geprüft:
            Archiv-Import eines GML ohne xplan:nummer-Element.

        Warum:
            Die Nummer ist optional; der Exception-Zweig beim Auslesen (find
            liefert None) war ungetestet.

        Erwartung:
            Plan wird ohne Nummer angelegt, Import liefert True.
        """
        gml = make_gml(name="Nummerloser Plan", nummer=None)
        with patch.object(xplanung_helper.magic, "from_buffer", side_effect=magic_wiehrt_dateityp):
            selbst = XPlanung(zip_upload(gml)).import_plan_archiv()
        self.assertTrue(selbst)
        plan = BPlan.objects.get(name="Nummerloser Plan")
        self.assertEqual(plan.nummer, "")

    def test_import_plan_archiv_raegt_unbekannte_gemeinde_ab(self):
        """
        Was wird geprüft:
            import_plan_archiv mit fehlender Gemeinde in der Datenbank.

        Warum:
            Der Archiv-Import hat seinen eigenen, kopierten Gemeinde-Abgleich —
            dessen Fehlerzweig war ungetestet.

        Erwartung:
            ValidationError mit dem Hinweis auf die Gemeinden.
        """
        gml = make_gml(name="Heimatloser Plan").replace(AGS, "07999999")
        with self.assertRaises(forms.ValidationError):
            XPlanung(gml_upload(gml)).import_plan_archiv()

    def test_import_plan_archiv_liefert_bei_einfacher_gml_datei_validation_error(self):
        """
        Was wird geprüft:
            import_plan_archiv mit einer einfachen GML-Datei statt eines ZIPs.

        Warum:
            sync_referenzen öffnet ungeachtet vorhandener Referenzen immer das
            ZIP; bei einer Nicht-ZIP-Datei läuft der Import in die
            ValidationError-Absicherung. Der Test dokumentiert dieses Verhalten.

        Erwartung:
            ValidationError "Fehler beim Abspeichern des neuen Plan-Objekts".
        """
        gml = make_gml(name="Archivloser Plan")
        with self.assertRaisesRegex(forms.ValidationError, "Abspeichern"):
            XPlanung(gml_upload(gml)).import_plan_archiv()

    def test_import_plan_archiv_ohne_overwrite_legts_keinen_zweiten_plan_an(self):
        """
        Was wird geprüft:
            Zweiter Archiv-Import desselben GMLs ohne overwrite.

        Warum:
            Findet der Import einen gleichnamigen Bestandsplan, soll er ohne
            Bestätigung schreibend nichts tun; dieser False-Zweig war ungetestet.

        Erwartung:
            Rückgabe False, weiterhin genau ein Plan.
        """
        gml = make_gml(name="Doppelter Archivplan")
        with patch.object(xplanung_helper.magic, "from_buffer", side_effect=magic_wiehrt_dateityp):
            self.assertTrue(XPlanung(zip_upload(gml)).import_plan_archiv())
            self.assertFalse(XPlanung(zip_upload(gml)).import_plan_archiv())
        self.assertEqual(BPlan.objects.filter(name="Doppelter Archivplan").count(), 1)

    def test_import_plan_archiv_referenzen_bei_fplan(self):
        """
        Was wird geprüft:
            Archiv-Import eines FP_Plan mit einer externen Referenz.

        Warum:
            sync_referenzen hat für BPlan und FPlan getrennte Anlege-Zweige;
            der FPlan-Zweig war ungenutzt.

        Erwartung:
            Eine FPlanSpezExterneReferenz mit Anlage, Plan existiert einmal.
        """
        referenz = REFERENZ_VORLAGE.format(name="Begruendung", datei="begruendung.pdf", typ="1000")
        gml = make_gml(plan_element="FP_Plan", name="Archiv-FPlan", extra_elemente=referenz)
        with patch.object(xplanung_helper.magic, "from_buffer", side_effect=magic_wiehrt_dateityp):
            selbst = XPlanung(zip_upload(gml, {"begruendung.pdf": b"%PDF-begr"})) \
                .import_plan_archiv(plan_typ="fplan")
        self.assertTrue(selbst)
        self.assertEqual(FPlanSpezExterneReferenz.objects.count(), 1)
        begruendung = FPlanSpezExterneReferenz.objects.get(name="Begruendung")
        self.assertIn("begruendung", begruendung.attachment.name)
        self.assertEqual(FPlan.objects.filter(name="Archiv-FPlan").count(), 1)

    def test_import_plan_archiv_ueberschreibt_referenzen_aus_zip(self):
        """
        Was wird geprüft:
            Zwei Archiv-Importe desselben GMLs mit drei externen Referenzen:
            eine reguläre (Typ 1060, PDF), ein georeferenzierter Scan (Typ
            99999, TIFF) und ein defekter Scan (Typ 99999, aber kein TIFF).

        Warum:
            sync_referenzen inkl. validate() war komplett ungetestet; der zweite
            Durchlauf prüft zusätzlich den Überschreibungs-Zweig
            (update_or_create mit bestehenden Referenzen).

        Erwartung:
            Genau zwei Referenzen mit Anlage und aus_archiv=True; der defekte
            Scan wird abgewiesen. Nach dem zweiten Import bleibt es bei zwei
            Referenzen (aktualisiert, nicht dupliziert).
        """
        referenzen = "".join((
            REFERENZ_VORLAGE.format(name="Satzung", datei="satzung.pdf", typ="1060"),
            REFERENZ_VORLAGE.format(name="Gruendruck", datei="scan.tif", typ="99999"),
            REFERENZ_VORLAGE.format(name="Defekter Scan", datei="kaputt.txt", typ="99999"),
        ))
        gml = make_gml(name="Referenzplan", extra_elemente=referenzen)
        dateien = {
            "satzung.pdf": b"%PDF-1.4 satzung",
            "scan.tif": b"II-TIFFTEST georefenzierter scan",
            "kaputt.txt": b"nur text, kein tiff",
        }
        with patch.object(xplanung_helper.magic, "from_buffer", side_effect=magic_wiehrt_dateityp):
            selbst = XPlanung(zip_upload(gml, dateien)).import_plan_archiv()
            self.assertTrue(selbst)
            self.assertEqual(BPlanSpezExterneReferenz.objects.count(), 2)
            self.assertFalse(BPlanSpezExterneReferenz.objects.filter(name="Defekter Scan").exists())
            # Zweiter Import: Überschreiben statt Anlegen
            XPlanung(zip_upload(gml, dateien)).import_plan_archiv(overwrite=True)
        self.assertEqual(BPlanSpezExterneReferenz.objects.count(), 2)
        satzung = BPlanSpezExterneReferenz.objects.get(name="Satzung")
        self.assertTrue(satzung.aus_archiv)
        # Bei Namenskollision in uploads/ hängt Django einen Zufallssuffix an
        self.assertIn("satzung", satzung.attachment.name)
        plan = BPlan.objects.get(name="Referenzplan")
        self.assertEqual(plan.attachments.count(), 2)


class XPlanungProxyTests(TestCase):
    """GML-Proxies: Anlagen zu externen Referenzen machen, historische Versionen."""

    def setUp(self):
        self.geometrie = GEOSGeometry("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))")

    def _bplan_mit_anlage(self, name):
        alte_referenz = REFERENZ_VORLAGE.format(
            name="ALT_ALTE_SATZUNG", datei="alt.pdf", typ="1060")
        plan = BPlan.objects.create(
            name=name, geltungsbereich=self.geometrie,
            xplan_gml=make_gml(name=name, extra_elemente=alte_referenz),
            xplan_gml_version="6.0")
        BPlanSpezExterneReferenz.objects.create(
            bplan=plan, name="Satzung aktuell", typ="1060",
            attachment=SimpleUploadedFile("satzung_neu.pdf", b"%PDF-aktuell"))
        return plan

    def test_proxy_bplan_gml_eretzt_referenzen_durch_anlagen(self):
        """
        Was wird geprüft:
            proxy_bplan_gml für einen Plan mit im GML hinterlegter alter
            externer Referenz und einer echten Anlage in der Datenbank.

        Warum:
            Der Proxy soll die im GML stehenden Referenzen ersetzen — die
            alten entfernen und die Anlagen als neue externe Referenzen
            einsetzen.

        Erwartung:
            Die alte Referenz ist aus dem Ergebnis verschwunden, die Anlage
            taucht mit Name, Datei und Typ auf.
        """
        plan = self._bplan_mit_anlage("Proxyplan B")
        ergebnis = XPlanung.proxy_bplan_gml(plan.id)
        self.assertNotIn("ALT_ALTE_SATZUNG", ergebnis)
        self.assertIn("Satzung aktuell", ergebnis)
        self.assertIn("satzung_neu", ergebnis)
        self.assertIn(">1060<", ergebnis)

    def test_proxy_bplan_gml_kennt_versionen_54_und_51(self):
        """
        Was wird geprüft:
            proxy_bplan_gml mit Plänen der Dokumentversionen 5.4 und 5.1.

        Warum:
            Der Proxy baut den Namespace aus xplan_gml_version; die beiden
            historischen Zweige waren ungenutzt.

        Erwartung:
            Das Ergebnis enthält den jeweils zugehörigen Namespace.
        """
        for version, ns in (("5.4", XPLAN_NS_54), ("5.1", XPLAN_NS_51)):
            with self.subTest(version=version):
                plan = BPlan.objects.create(
                    name=f"Proxyplan Alt {version}", geltungsbereich=self.geometrie,
                    xplan_gml=make_gml(name=f"Proxyplan Alt {version}", xplan_ns=ns),
                    xplan_gml_version=version)
                ergebnis = XPlanung.proxy_bplan_gml(plan.id)
                self.assertIn(ns, ergebnis)

    def test_proxy_fplan_gml_eretzt_referenzen_durch_anlagen(self):
        """
        Was wird geprüft:
            proxy_fplan_gml mit alter GML-Referenz und einer Datenbank-Anlage.

        Warum:
            Spiegelbild des BPlan-Proxies — der FPlan-Zweig war komplett
            ungetestet.

        Erwartung:
            Alte Referenz raus, Anlage mit Name/Datei/Typ drin.
        """
        alte_referenz = REFERENZ_VORLAGE.format(
            name="ALT_ALTE_BEGruENDUNG", datei="alt.pdf", typ="1000")
        plan = FPlan.objects.create(
            name="Proxyplan F", geltungsbereich=self.geometrie,
            xplan_gml=make_gml(plan_element="FP_Plan", name="Proxyplan F",
                               extra_elemente=alte_referenz),
            xplan_gml_version="6.0")
        FPlanSpezExterneReferenz.objects.create(
            fplan=plan, name="Begruendung aktuell", typ="1000",
            attachment=SimpleUploadedFile("begruendung.pdf", b"%PDF-begruendung"))
        ergebnis = XPlanung.proxy_fplan_gml(plan.id)
        self.assertNotIn("ALT_ALTE_BEGruENDUNG", ergebnis)
        self.assertIn("Begruendung aktuell", ergebnis)
        # Dateiendname kann bei Kollision einen Zufallssuffix tragen
        self.assertIn("begruendung", ergebnis)

    def test_proxy_fplan_gml_kennt_versionen_54_und_51(self):
        """
        Was wird geprüft:
            proxy_fplan_gml mit xplan_gml_version 5.4 und 5.1.

        Warum:
            Auch der FPlan-Proxy bildet die historischen Namespaces ab; beide
            Zweige waren ungenutzt.

        Erwartung:
            Der jeweilige Namespace erscheint im Ergebnis.
        """
        for version, ns in (("5.4", XPLAN_NS_54), ("5.1", XPLAN_NS_51)):
            with self.subTest(version=version):
                name = f"Proxyplan F Alt {version}"
                plan = FPlan.objects.create(
                    name=name, geltungsbereich=self.geometrie,
                    xplan_gml=make_gml(plan_element="FP_Plan", name=name, xplan_ns=ns),
                    xplan_gml_version=version)
                ergebnis = XPlanung.proxy_fplan_gml(plan.id)
                self.assertIn(ns, ergebnis)
