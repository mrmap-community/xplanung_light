"""
Tests zur serverseitigen Prüfung von Datei-Uploads bei Plan-Anhängen: Endung, Inhalt
(Mimetype per libmagic), Größe und Virenscan.

Validatoren (siehe validators.py und XPLANUNG_LIGHT_CONFIG['xplan_attachments'] in base.py):
FileExtensionValidator, validate_xplan_attachment_mimetype, validate_xplan_attachment_file_size
und validate_file_infection (django-clamd).
"""

import base64
import copy
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

import django_clamd.validators as clamd_validators

from xplanung_light.models import BPlan, BPlanSpezExterneReferenz

PDF = b'%PDF-1.4\n%Testinhalt\n'
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)
JPG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'
TIF = b'II*\x00\x08\x00\x00\x00\x00\x00'
EXE = b'MZ\x90\x00' + b'\x00' * 100


def _config_with_limit(limit):
    cfg = copy.deepcopy(settings.XPLANUNG_LIGHT_CONFIG)
    cfg['limits']['upload_file_size_limits']['other'] = limit
    return cfg


class AttachmentUploadValidation(TestCase):
    """
    Was passiert, wenn eine Datei als Plan-Anhang hochgeladen wird - jenseits
    der in test_permissions.py geprüften Frage, WER das darf.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    PLAN_PK = 4318

    @classmethod
    def setUpTestData(cls):
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)

    def setUp(self):
        self.client = Client()
        self.client.force_login(User.objects.get(
            username='admin_stadt_neustadt'))

    def _post_attachment(self, file_obj, typ=BPlanSpezExterneReferenz.BESCHREIBUNG, name='Test-Anhang'):
        return self.client.post(
            reverse('bplanattachment-create', kwargs={'planid': self.PLAN_PK}),
            data={
                'public': False,
                'typ': typ,
                'name': name,
                'attachment': file_obj,
            },
        )

    def _assert_rejected(self, upload, name):
        response = self._post_attachment(upload, name=name)
        # Formular mit Fehler neu gerendert
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.context['form'].errors)
        self.assertFalse(BPlanSpezExterneReferenz.objects.filter(
            bplan=self.plan, name=name).exists())

    def _assert_accepted(self, upload, name):
        response = self._post_attachment(upload, name=name)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BPlanSpezExterneReferenz.objects.filter(
            bplan=self.plan, name=name).exists())

    # --- Endung ---------------------------------------------------------

    def test_allowed_types_are_accepted(self):
        cases = [('a.pdf', PDF, 'application/pdf'),
                 ('a.png', PNG, 'image/png'),
                 ('a.jpg', JPG, 'image/jpeg'),
                 ('a.jpeg', JPG, 'image/jpeg'),
                 ('a.tif', TIF, 'image/tiff'),
                 ('a.tiff', TIF, 'image/tiff')]
        for filename, content, ctype in cases:
            with self.subTest(filename=filename):
                self._assert_accepted(
                    SimpleUploadedFile(filename, content, content_type=ctype),
                    name=f'ok-{filename}')

    def test_uppercase_extension_is_accepted(self):
        # FileExtensionValidator vergleicht case-insensitive
        self._assert_accepted(
            SimpleUploadedFile('BERICHT.PDF', PDF,
                               content_type='application/pdf'),
            name='Grossbuchstaben')

    def test_exe_extension_is_rejected(self):
        self._assert_rejected(
            SimpleUploadedFile('payload.exe', EXE,
                               content_type='application/x-msdownload'),
            name='Ausführbare Datei')

    def test_double_extension_exe_is_rejected(self):
        # nur das letzte Suffix zählt
        self._assert_rejected(
            SimpleUploadedFile('bericht.pdf.exe', PDF,
                               content_type='application/pdf'),
            name='doppelt')

    # --- Inhalt (Mimetype per libmagic) ---------------------------------

    def test_exe_content_with_pdf_extension_is_rejected(self):
        self._assert_rejected(
            SimpleUploadedFile('getarnt.pdf', EXE,
                               content_type='application/pdf'),
            name='getarnt')

    def test_text_content_with_pdf_extension_is_rejected(self):
        self._assert_rejected(
            SimpleUploadedFile('text.pdf', b'A' * 5000,
                               content_type='application/pdf'),
            name='text-als-pdf')

    # --- Größe ----------------------------------------------------------

    def test_file_at_size_limit_is_accepted(self):
        limit = 4096
        with override_settings(XPLANUNG_LIGHT_CONFIG=_config_with_limit(limit)):
            self._assert_accepted(
                SimpleUploadedFile('grenze.pdf', PDF + b'A' * (limit - len(PDF)),
                                   content_type='application/pdf'),
                name='genau-am-limit')

    def test_file_above_size_limit_is_rejected(self):
        limit = 4096
        with override_settings(XPLANUNG_LIGHT_CONFIG=_config_with_limit(limit)):
            self._assert_rejected(
                SimpleUploadedFile('zu_gross.pdf', PDF + b'A' * (limit - len(PDF) + 1),
                                   content_type='application/pdf'),
                name='ein-byte-zu-gross')

    # --- Virenscan: Konfigurationsstand dieser Umgebung -----------------

    def test_malware_scanning_is_disabled_in_this_settings_environment(self):
        """
        Warnender Canary-Test: CLAMD_ENABLED steht in komserv/settings/base.py
        auf False. django-clamd liest diesen Wert als Modulkonstante EINMAL
        beim Import - @override_settings würde hier also NICHT dynamisch
        greifen. Schlägt der Test künftig fehl, hat sich das geändert -
        bitte dann auch dev.py/prod.py auf denselben Stand prüfen.
        """
        self.assertFalse(
            clamd_validators.CLAMD_ENABLED,
            "CLAMD_ENABLED scheint nicht mehr False zu sein - falls das "
            "eine bewusste Änderung war, prüfe bitte auch, ob "
            "dev.py/prod.py denselben Stand haben und ob ein laufender "
            "ClamAV-Dienst erreichbar ist."
        )

    # --- Virenscan: Verdrahtung (unabhängig von echtem ClamAV) ---------

    def _mock_scan_result(self, status, signature=None):
        scanner = MagicMock()
        scanner.instream.return_value = {'stream': (status, signature)}
        return scanner

    def test_infected_file_is_rejected_when_scanning_is_enabled(self):
        """
        Prüft die Verdrahtung von validate_file_infection() ohne echten
        ClamAV-Dienst: CLAMD_ENABLED wird als Attribut auf dem
        django_clamd.validators-Modul gepatcht, der Scanner durch ein Mock
        ersetzt, das eine Infektion meldet. Die Testdatei hat gültige Endung
        und gültigen Inhalt, damit die Ablehnung nachweislich vom Scan kommt.
        """
        upload = SimpleUploadedFile(
            'eicar_test.pdf',
            PDF + b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-TEST',
            content_type='application/pdf',
        )
        scanner = self._mock_scan_result('FOUND', 'Eicar-Test-Signature')

        with patch.object(clamd_validators, 'CLAMD_ENABLED', True), \
                patch.object(clamd_validators, 'get_scanner', return_value=scanner):
            self._assert_rejected(upload, name='Infizierte Datei')

        # Beweist: die Ablehnung kam vom Scanner (kein assert_called_once,
        # falls Validatoren durch ModelForm._post_clean doppelt laufen)
        self.assertTrue(scanner.instream.called)

    def test_clean_file_is_accepted_when_scanning_is_enabled(self):
        """
        Positiv-Gegenprobe: derselbe Mock-Mechanismus, aber der Scanner
        meldet "OK". Stellt sicher, dass der Upload am Scan-Ergebnis hängt.
        """
        upload = SimpleUploadedFile(
            'unbedenklich.pdf', PDF + b'Ganz normaler Text.',
            content_type='application/pdf',
        )
        scanner = self._mock_scan_result('OK')

        with patch.object(clamd_validators, 'CLAMD_ENABLED', True), \
                patch.object(clamd_validators, 'get_scanner', return_value=scanner):
            self._assert_accepted(upload, name='Unbedenkliche Datei')

        self.assertTrue(scanner.instream.called)

    def test_png_extension_with_pdf_content_is_rejected(self):
        self._assert_rejected(
            SimpleUploadedFile('bild.png', PDF, content_type='image/png'),
            name='png-mit-pdf')
