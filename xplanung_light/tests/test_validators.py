"""Tests der Validatoren für XPlanung-Dateien, ZIP-Archive und Rasterdateien."""

import inspect
import zipfile
from copy import deepcopy

from django.apps import apps
from django.conf import settings
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from xplanung_light.models import AdministrativeOrganization, BPlanSpezExterneReferenz 
from xplanung_light.validators import (
    bplan_content_validator,
    fplan_content_validator,
    bplan_upload_file_validator,
    fplan_upload_file_validator,
    geotiff_raster_validator,
    validate_xplan_attachment_extension
)

class XPlanValidatorsTests(TestCase):
    """Gültige und ungültige Dateien bei den Inhalts- und Archiv-Validatoren."""

    def setUp(self):
        # Wir legen die im XML referenzierte Gemeinde passend in der DB an,
        # aufgeteilt in ls, ks, gs, damit der Inhalts-Check sie findet.
        AdministrativeOrganization.objects.get_or_create(
            ls='07',
            ks='316',
            gs='000',
            name="Neustadt an der Weinstraße, kreisfreie Stadt"
        )

    # ==============================================================================
    # 1. TESTS FÜR XML / GML INHALTS-VALIDATOREN
    # ==============================================================================

    def test_content_validators_handle_valid_xml_gml(self):
        """Prüft, ob das beigefügte reelle XPlanung 6.0-GML-Original mit deinen Namespaces akzeptiert wird."""
        
        # KORREKTUR: Namespaces exakt auf deine Vorgaben zurückgesetzt
        bplan_gml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<xplan:XPlanAuszug xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://w3.org" xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:xsi="http://w3.org" xsi:schemaLocation="http://xplanung.de http://gdi-de.org" gml:id="GML_32d36c80-a7d9-4d06-8f8a-470209cd32d4">'
            b'  <gml:boundedBy>'
            b'    <gml:Envelope srsName="EPSG:25832">'
            b'      <gml:lowerCorner>567015.8040 5937951.7580</gml:lowerCorner>'
            b'      <gml:upperCorner>567582.8240 5938562.2710</gml:upperCorner>'
            b'    </gml:Envelope>'
            b'  </gml:boundedBy>'
            b'  <gml:featureMember>'
            b'    <xplan:BP_Plan gml:id="GML_5b2f5374-fbe6-4ffd-be95-06a257dc5c91">'
            b'      <gml:boundedBy>'
            b'        <gml:Envelope srsName="EPSG:25832">'
            b'          <gml:lowerCorner>436104.85390563804 5463436.092545369</gml:lowerCorner>'
            b'          <gml:upperCorner>436570.32736793294 5463774.156689</gml:upperCorner>'
            b'        </gml:Envelope>'
            b'      </gml:boundedBy>'
            b'      <xplan:name>Andergasse - Kaesgasse</xplan:name>'
            b'      <xplan:nummer>156</xplan:nummer><xplan:beschreibung>21.10.1992 (nachtraeglich ausgefertigt)\nDer Bebauungsplan wird im BEREICH des neuen BP "ANDERGASSE" ersetzt.</xplan:beschreibung><xplan:untergangsDatum>2026-03-20</xplan:untergangsDatum><xplan:erstellungsMassstab>1000</xplan:erstellungsMassstab>'
            b'      <xplan:raeumlicherGeltungsbereich>'
            b'        <gml:MultiSurface srsName="EPSG:25832" gml:id="GML_6fbf9832-2278-4d9e-a56f-d2924037fdb3"><gml:surfaceMember><gml:Polygon gml:id="GML_4df93d64-dc65-40a4-9ba1-ff9b88fb020a"><gml:exterior><gml:LinearRing><gml:posList srsDimension="2">436104.85390564 5463751.69231124 436124.64358817 5463681.09740405 436133.33921193 5463682.98919936 436135.10324988 5463670.59415875 436148.39968108 5463668.56555334 436158.57548066 5463668.04754797 436164.15107753 5463668.30466303 436164.09651466 5463641.16034437 436174.67509012 5463641.04858482 436171.56533962 5463599.39210373 436185.15352156 5463600.24093389 436187.43524357 5463583.54988306 436139.81618399 5463562.49166355 436118.45960927 5463558.29973327 436117.78046611 5463551.54920908 436116.80077779 5463541.82299631 436111.38175025 5463520.17145336 436112.22600232 5463482.14871958 436105.26343582 5463456.39765689 436132.59997112 5463455.67391332 436163.00393645 5463452.34408309 436182.37471746 5463447.63768409 436198.00197537 5463442.89329095 436215.99354395 5463438.50414026 436230.5136713 5463436.09254537 436261.30503207 5463439.1583995 436276.08510526 5463444.48142878 436290.61739622 5463452.2874615 436301.04477183 5463458.35470509 436334.36900581 5463466.78858209 436386.60824782 5463478.79569887 436435.00116248 5463483.39430583 436541.01156276 5463500.95914129 436541.39348144 5463590.95028364 436528.78395455 5463617.3605229 436526.9978058 5463677.75388437 436565.41458792 5463695.18497288 436564.000048 5463700.40154664 436563.39274228 5463705.23816404 436569.51930235 5463730.10648139 436570.32736793 5463755.90985207 436527.69123462 5463774.156689 436524.52527055 5463747.54787208 436483.68123252 5463753.00626386 436483.06742595 5463748.91725026 436450.70552493 5463754.31648402 436446.12700003 5463720.83136379 436410.21123791 5463726.52947855 436409.3815246 5463720.73177325 43649.40533313 5463735.67547517 436344.17889868 5463725.15525269 436301.71233247 5463742.49837144 436265.04674148 5463755.50938665 436263.91718185 5463754.72970464 436211.45381849 5463746.01661066 436219.88641383 5463734.25318301 436189.0495555 5463730.91377492 436130.83064019 5463748.88619006 436118.102687 5463752.8147507 436104.85390564 5463751.69231124</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>'
            b'      </xplan:raeumlicherGeltungsbereich>'
            b'      <xplan:gemeinde>'
            b'        <xplan:XP_Gemeinde>'
            b'          <xplan:ags>07316000</xplan:ags>'
            b'          <xplan:gemeindeName>Neustadt an der Weinstra\xc3\x9fe, kreisfreie Stadt</xplan:gemeindeName>'
            b'        </xplan:XP_Gemeinde>'
            b'      </xplan:gemeinde>'
            b'      <xplan:planArt>10000</xplan:planArt>'
            b'      <xplan:rechtsstand>5000</xplan:rechtsstand>'
            b'    </xplan:BP_Plan>'
            b'  </gml:featureMember>'
            b'</xplan:XPlanAuszug>'
        )

        fplan_gml_content = bplan_gml_content.replace(b'xplan:BP_Plan', b'xplan:FP_Plan')

        # Teste BPlan Validator
        uploaded_bplan = SimpleUploadedFile("valid_bplan_orig.gml", bplan_gml_content, content_type="application/gml+xml")
        try:
            bplan_content_validator(uploaded_bplan)
        except ValidationError as e:
            self.fail(f"bplan_content_validator hat das Original-GML fälschlicherweise abgelehnt: {e}")

        # Teste FPlan Validator
        uploaded_fplan = SimpleUploadedFile("valid_fplan_orig.gml", fplan_gml_content, content_type="application/gml+xml")
        try:
            fplan_content_validator(uploaded_fplan)
        except ValidationError as e:
            self.fail(f"fplan_content_validator hat das Original-GML fälschlicherweise abgelehnt: {e}")

    def test_content_validators_raise_error_on_corrupted_binary_data(self):
        """Prüft, ob Binärdaten als korruptes XML erkannt werden."""
        corrupted_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01'
        uploaded_file = SimpleUploadedFile("broken_plan.gml", corrupted_data, content_type="application/xml")
        
        with self.assertRaises(ValidationError):
            bplan_content_validator(uploaded_file)
            
        with self.assertRaises(ValidationError):
            fplan_content_validator(uploaded_file)

    def test_content_validators_raise_error_on_empty_file(self):
        """Ein komplett leerer Datei-Upload muss abgefangen werden."""
        empty_file = SimpleUploadedFile("empty.gml", b"", content_type="application/xml")
        
        with self.assertRaises(ValidationError):
            bplan_content_validator(empty_file)

    # ==============================================================================
    # 2. TESTS FÜR ARCHIV-VALIDATOREN
    # ==============================================================================

    def test_upload_file_validators_reject_invalid_zip_archives(self):
        """Fängt das ungeschützte BadZipFile-Verhalten der Archiv-Validatoren ab."""
        fake_zip_data = b'Ich bin gar kein echtes ZIP-Archiv, sondern reiner Text!'
        uploaded_file = SimpleUploadedFile("fake_archive.zip", fake_zip_data, content_type="application/zip")
        
        with self.assertRaises(zipfile.BadZipFile):
            bplan_upload_file_validator(uploaded_file)
            
        with self.assertRaises(zipfile.BadZipFile):
            fplan_upload_file_validator(uploaded_file)

    # ==============================================================================
    # 3. TESTS FÜR RASTERDATEN-VALIDATOREN
    # ==============================================================================

    def test_geotiff_raster_validator_rejects_corrupted_image(self):
        """Der Rasterdatei-Validator muss beschädigte oder unlesbare Bilddateien abfangen."""
        bad_tiff_data = b'Geotiff-Anhang-Dummy-Text-ohne-Inhalt'
        uploaded_file = SimpleUploadedFile("plankarte.tif", bad_tiff_data, content_type="image/tiff")
        
        with self.assertRaises(ValidationError):
            geotiff_raster_validator(uploaded_file)


class AnlageErlaubteDateiendungenTests(TestCase):
    """
    Der Prüfer für erlaubte Dateiendungen der Anlagen
    (validators.validate_xplan_attachment_extension).

    Er wurde als FileExtensionValidator-Instanz beim Import aus den settings
    gebaut. Validatoren dekonstruieren sich aber mit ihren Argumenten - die
    Liste der erlaubten Endungen wanderte damit in den Migrationszustand der
    Attachment-Felder. Seit dem Nachziehen der Liste (Commit 7a09f7e) meldete
    makemigrations --check offen: vier AlterField-Operationen, deren Migration
    am Schema nichts ändert (sqlmigrate: no-op). Der Prüfer wird deshalb erst
    beim Aufruf gebaut, wie die Nachbarn für Mimetype und Dateigröße.
    """

    def _einstellungen_mit(self, erlaubte_endungen):
        """Die laufende Konfiguration, aber mit einer anderen Endungsliste."""
        konfiguration = deepcopy(dict(settings.XPLANUNG_LIGHT_CONFIG))
        konfiguration['xplan_attachments']['allowed_extensions'] = erlaubte_endungen
        return override_settings(XPLANUNG_LIGHT_CONFIG=konfiguration)

    def _datei(self, name):
        return SimpleUploadedFile(name, b"Inhalt", content_type="application/octet-stream")

    def _offene_aenderungen(self):
        """Was makemigrations ohne Dateien zu schreiben finden würde, je App."""
        lader = MigrationLoader(None, ignore_no_migrations=True)
        autodetektor = MigrationAutodetector(
            lader.project_state(),
            ProjectState.from_apps(apps),
            NonInteractiveMigrationQuestioner(specified_apps=set(), dry_run=True),
        )
        return autodetektor.changes(graph=lader.graph, trim_to_apps={'xplanung_light'})

    def test_keine_Endungsliste_im_Modellfeld(self):
        """
        Was wird geprüft:
            Die Dekonstruktion des Attachment-Felds einer spezifizierten
            externen Referenz: welche Validatoren dort landen und ob eine
            Endungsliste darin enthalten ist.

        Warum:
            Nur was ein Feld bei der Dekonstruktion mitgibt, steht später im
            Migrationszustand. Ein Validierungsobjekt, das die Liste aus den
            settings kennt, macht das Modell von einer Deployment-Einstellung
            abhängig - der eigentliche Fehler.

        Erwartung:
            Der Endungsprüfer ist eine Funktion ohne eigene Listen-Mitgabe, das
            Feld dekonstruiert sich in allen vier Modellen gleich und ohne
            etwas, das von den Einstellungen käme.
        """
        feld = BPlanSpezExterneReferenz._meta.get_field('attachment')

        selbst = dict(feld.deconstruct()[3])['validators']
        pruefer = [v for v in selbst
                   if getattr(v, '__name__', '') == 'validate_xplan_attachment_extension']
        self.assertEqual(len(pruefer), 1)
        self.assertTrue(inspect.isfunction(pruefer[0]))
        for validator in selbst:
            self.assertFalse(
                hasattr(validator, 'allowed_extensions'),
                "Das Feld trägt eine Endungsliste mit - sie wandert in den "
                "Migrationszustand und hängt dann von den settings ab")

    def test_abweichende_Einstellungen_erzeugen_keine_Migrationsdifferenz(self):
        """
        Was wird geprüft:
            Ob der Migrationsautodetektor ein AlterField für die
            Attachment-Felder will, wenn die Liste der erlaubten Endungen von
            den Auslieferungs-Einstellungen abweicht - wie in einer
            Installation mit eigener Vorgabe.

        Warum:
            Genau diese Konstellation war unauffällig kaputt: wich die
            Einstellung von dem in Migration 0092 gemerkten Stand ab, forderte
            der Autodetektor vier AlterFields - deren Migration am Schema nichts
            ändert (sqlmigrate: no-op). Installationen mit eigener Liste
            liefen dauerhaft mit "offenen" Migrationen mit.

        Erwartung:
            Keine Operation für ein attachment-Feld. Über die ganze App wird
            das hier nicht geprüft: die choices von simple_historys history_type
            werden beim Laden der Migrationsdateien in der gerade aktiven
            Sprache ausgelesen, ein App-weiter Vergleich hängt deshalb an der
            Sprache. Dafür läuft makemigrations --check in der Integration.
        """
        with self._einstellungen_mit(['pdf', 'webp']):
            aenderungen = self._offene_aenderungen()

        betroffen = [
            (operation.model_name, operation.name)
            for migration in aenderungen.get('xplanung_light', [])
            for operation in migration.operations
            if getattr(operation, "name", "") == "attachment"
        ]
        self.assertEqual(betroffen, [])

    def test_Liste_gilt_zum_Zeitpunkt_des_Aufrufs(self):
        """
        Was wird geprüft:
            Welche Dateiendungen der Prüfer durchlässt, wenn die Einstellung
            während der Laufzeit verschwindet bzw. auftaucht.

        Warum:
            Die Liste ist eine Deployment-Einstellung. Die Validierung muss ihr
            folgen, sonst entscheidet der Stand beim Import des Moduls - und
            eine Installation, die die Liste pflegt, validiert gegen falsche
            Endungen.

        Erwartung:
            Mit den Auslieferungs-Einstellungen gehen .jpg und .pdf durch; mit
            der Vorgabe nur "pdf" geht .pdf weiter, .jpg wird abgelehnt.
        """
        self.assertIsNone(validate_xplan_attachment_extension(self._datei("Plan.jpg")))
        self.assertIsNone(validate_xplan_attachment_extension(self._datei("Plan.pdf")))

        with self._einstellungen_mit(['pdf']):
            self.assertIsNone(validate_xplan_attachment_extension(self._datei("Plan.pdf")))
            with self.assertRaises(ValidationError):
                validate_xplan_attachment_extension(self._datei("Plan.jpg"))

    def test_leere_Werte_und_Datei_ohne_Eendung(self):
        """
        Was wird geprüft:
            Der Prüfer mit leerem Feldwert und mit einer Datei ohne Endung.

        Warum:
            Das Feld ist null=True und blank=True; Field.run_validators sortiert
            leere Werte aus, der Prüfer bekommt sie im Formularlauf also nie zu
            sehen. Der eigene Aufrufpfad darf an beiden Enden nicht anders
            reagieren: weder mit einer Ausnahme für leere Werte - Djangos
            FileExtensionValidator fasst in Django 5.2 value.name an und meldet
            für None einen AttributeError - noch mit einer stillschweigenden
            Erlaubnis für Namen ohne Endung.

        Erwartung:
            Für None und den Leerstring passiert nichts, eine Datei ohne Endung
            wird abgelehnt.
        """
        self.assertIsNone(validate_xplan_attachment_extension(None))
        self.assertIsNone(validate_xplan_attachment_extension(""))

        with self.assertRaises(ValidationError):
            validate_xplan_attachment_extension(self._datei("Planohneendung"))
