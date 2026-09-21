from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

import django_clamd.validators as clamd_validators

from xplanung_light.models import BPlan, BPlanSpezExterneReferenz


class AttachmentUploadValidation(TestCase):
    """
    Was tatsächlich passiert, wenn eine Datei als Plan-Anhang hochgeladen
    wird - jenseits der bereits in test_permissions.py geprüften Frage, WER
    das darf.

    Der einzige Validator auf BPlanSpezExterneReferenz.attachment ist
    validate_file_infection (django-clamd). Es gibt weder einen
    FileExtensionValidator noch eine serverseitige Größenprüfung - das
    "max-size": 1024*1024 im Formular-Widget (BPlanBeteiligungBeitragAnhangForm,
    siehe forms.py) ist nur ein HTML/JS-Attribut fürs Frontend und wird vom
    Server nicht durchgesetzt.

    Diese Tests dokumentieren den IST-Zustand (auch die überraschenden
    Teile davon) und prüfen zusätzlich, dass die Virenscan-Anbindung an sich
    korrekt verdrahtet ist - unabhängig davon, ob in dieser Umgebung
    tatsächlich ein ClamAV-Dienst erreichbar ist.
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
        self.client.force_login(User.objects.get(username='admin_stadt_neustadt'))

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

    # --- Größenlimit --------------------------------------------------

    def test_oversized_attachment_is_accepted_server_side(self):
        """
        Dokumentiert eine bestehende Lücke: das Formular wirbt im help_text
        mit "Please do not upload files larger than 1MB", aber das ist reine
        Bitte an den Browser (max-size im Widget-Attribut, JS-seitig). Diese
        2-MB-Datei wird serverseitig anstandslos akzeptiert.

        Falls hier künftig ein serverseitiger Größenlimit-Validator ergänzt
        wird, muss dieser Test auf eine 4xx/Formularfehler-Assertion
        umgestellt werden - dann wäre das ein begrüßenswerter Fix, kein
        Regressionsfehler.
        """
        oversized_content = b'A' * (2 * 1024 * 1024)  # 2 MB, deutlich > 1 MB
        upload = SimpleUploadedFile(
            'grosse_datei.pdf', oversized_content, content_type='application/pdf',
        )

        response = self._post_attachment(upload)

        self.assertEqual(response.status_code, 302, (
            "Erwartetes (überraschendes) Verhalten: der Upload wird trotz "
            "Überschreitung der im UI beworbenen 1-MB-Grenze akzeptiert, "
            "weil es keine serverseitige Größenprüfung gibt."
        ))
        attachment = BPlanSpezExterneReferenz.objects.filter(bplan=self.plan, name='Test-Anhang').first()
        self.assertIsNotNone(attachment)
        self.assertEqual(attachment.attachment.size, len(oversized_content))

    # --- Dateityp / Endung ---------------------------------------------

    def test_arbitrary_file_extension_is_accepted(self):
        """
        Dokumentiert dieselbe Art Lücke wie oben, hier für den Dateityp: es
        gibt keine Allowlist für Dateiendungen oder Content-Types. Eine
        .exe-Datei wird ebenso akzeptiert wie ein PDF.
        """
        upload = SimpleUploadedFile(
            'payload.exe', b'MZ\x90\x00' + b'\x00' * 100,
            content_type='application/x-msdownload',
        )

        response = self._post_attachment(upload, name='Ausführbare Datei')

        self.assertEqual(response.status_code, 302, (
            "Erwartetes (überraschendes) Verhalten: es gibt keine "
            "Dateityp-Allowlist, die .exe-Datei wird angenommen."
        ))
        self.assertTrue(
            BPlanSpezExterneReferenz.objects.filter(
                bplan=self.plan, name='Ausführbare Datei'
            ).exists()
        )

    # --- Virenscan: Konfigurationsstand dieser Umgebung -----------------

    def test_malware_scanning_is_disabled_in_this_settings_environment(self):
        """
        Warnender Canary-Test: CLAMD_ENABLED steht in komserv/settings/base.py
        auf False. django-clamd liest diesen Wert als Modulkonstante EINMAL
        beim Import von django_clamd.conf (genau dasselbe Muster wie
        CAPTCHA_TEST_MODE bei django-simple-captcha, siehe
        test_beitrag_authenticate.py) - @override_settings würde hier also
        NICHT dynamisch greifen.

        Für komserv/settings/dev.py und komserv/settings/prod.py lagen mir
        beim Schreiben dieses Tests keine Dateien vor (nicht im Repo-Export
        enthalten) - ob dort CLAMD_ENABLED=True gesetzt wird, konnte ich
        nicht prüfen. Dieser Test deckt nur ab, was in der Test-Umgebung
        tatsächlich aktiv ist (test.py erbt von base.py, ohne eigene
        CLAMD_ENABLED-Zeile). Schlägt er künftig fehl, hat sich das geändert
        - bitte dann auch dev.py/prod.py auf denselben Stand prüfen.
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
        Prüft die Verdrahtung von validate_file_infection() unabhängig von
        einem echten, erreichbaren ClamAV-Dienst: CLAMD_ENABLED wird für die
        Dauer des Tests auf True gepatcht (als Attribut auf dem
        django_clamd.validators-Modul, siehe Hinweis im vorigen Test - ein
        @override_settings würde hier NICHT wirken), und der Scanner wird
        durch ein Mock ersetzt, das eine Infektion meldet.

        Damit ist sichergestellt: WENN ein Scanner läuft und "FOUND" meldet,
        wird der Upload tatsächlich abgelehnt und nichts landet in der DB -
        unabhängig davon, ob in dieser Sandbox ein echter ClamAV-Daemon
        erreichbar ist.
        """
        upload = SimpleUploadedFile(
            'eicar_test.txt', b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-TEST',
            content_type='text/plain',
        )

        with patch.object(clamd_validators, 'CLAMD_ENABLED', True), \
             patch.object(clamd_validators, 'get_scanner',
                           return_value=self._mock_scan_result('FOUND', 'Eicar-Test-Signature')):
            response = self._post_attachment(upload, name='Infizierte Datei')

        self.assertEqual(response.status_code, 200)  # Formular wird mit Fehler neu gerendert
        self.assertFalse(
            BPlanSpezExterneReferenz.objects.filter(
                bplan=self.plan, name='Infizierte Datei'
            ).exists()
        )

    def test_clean_file_is_accepted_when_scanning_is_enabled(self):
        """
        Positiv-Gegenprobe zum vorigen Test: derselbe Mock-Mechanismus, aber
        der Scanner meldet "OK" statt "FOUND". Stellt sicher, dass der Mock
        nicht grundsätzlich jeden Upload blockiert, sondern tatsächlich am
        Scan-Ergebnis hängt.
        """
        upload = SimpleUploadedFile(
            'unbedenklich.txt', b'Ganz normaler Text.', content_type='text/plain',
        )

        with patch.object(clamd_validators, 'CLAMD_ENABLED', True), \
             patch.object(clamd_validators, 'get_scanner',
                           return_value=self._mock_scan_result('OK')):
            response = self._post_attachment(upload, name='Unbedenkliche Datei')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            BPlanSpezExterneReferenz.objects.filter(
                bplan=self.plan, name='Unbedenkliche Datei'
            ).exists()
        )