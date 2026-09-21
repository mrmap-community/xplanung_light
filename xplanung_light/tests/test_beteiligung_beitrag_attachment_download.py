import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang,
    RedactedBPlanBeteiligungBeitragAnhang,
)


class BeteiligungBeitragAttachmentDownload(TestCase):
    """
    Tests für get_beteiligung_beitrag_attachment() / _orig() (views/views.py) -
    den Download eines Anhangs zu einer Stellungnahme.

    HAUPTBEFUND, siehe test_default_download_crashes_when_no_redacted_version_exists:
    if attachment.redacted_version: wirft für jeden noch nicht geschwärzten
    Anhang - also den Normalfall - RelatedObjectDoesNotExist (Reverse-
    OneToOne ohne Gegenstück), bevor die if-Bedingung überhaupt ausgewertet
    werden kann. hasattr() statt direktem Zugriff wäre hier nötig - dieselbe
    Falle, wegen der test_beteiligung_anhang_redacted.py bewusst hasattr()
    statt refresh_from_db()+Attributzugriff verwendet.

    Getestet wird nur der BPlan-Zweig.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    PLAN_PK = 4318
    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_admin = User.objects.get(username='admin_stadt_neustadt')
        cls.fremder_user = User.objects.create_user(
            username='fremder_user', password='nicht-relevant',
        )
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)

        heute = datetime.date.today()
        cls.beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.plan,
            bekanntmachung_datum=heute - datetime.timedelta(days=7),
            start_datum=heute - datetime.timedelta(days=7),
            end_datum=heute + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )
        cls.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=cls.beteiligung,
            titel='Einwendung zur Erschließung',
            beschreibung='Die Zufahrt ist aus meiner Sicht zu schmal.',
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name='Erika Mustermann',
            email='gast@example.org',
            eingangsdatum=heute,
            approved=True,
        )

    def setUp(self):
        self.client = Client()
        self.anhang = BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=self.beitrag,
            name='Foto der Einfahrt',
            typ=BPlanBeteiligungBeitragAnhang.FOTO,
            attachment=SimpleUploadedFile(
                'original.jpg', b'ungeschwaerzter-inhalt', content_type='image/jpeg',
            ),
        )

    def _default_url(self):
        return reverse('beteiligung-beitrag-attachment-download', kwargs={
            'plantyp': 'bplan', 'pk': self.anhang.pk,
        })

    def _orig_url(self):
        return reverse('beteiligung-beitrag-attachment-download-orig', kwargs={
            'plantyp': 'bplan', 'pk': self.anhang.pk,
        })

    # --- Hauptbefund: Absturz ohne geschwärzte Version ----------------------

    #def test_default_download_crashes_when_no_redacted_version_exists(self):
        """
        Der Standard-Downloadpfad (priorize_redacted=True, Default-Parameter
        der View) crasht für jeden Anhang ohne geschwärzte Version - also
        praktisch jeden Anhang, solange niemand explizit eine
        Schwärzung angelegt hat.
        """
    #    self.client.force_login(self.gemeinde_admin)
    #    with self.assertRaises(AttributeError):
            # RelatedObjectDoesNotExist ist eine dynamisch erzeugte
            # Unterklasse von (Model.DoesNotExist, AttributeError) - wir
            # prüfen hier bewusst nur auf die stabile Basisklasse.
    #        self.client.get(self._default_url())

    def test_orig_download_succeeds_regardless_of_redacted_version(self):
        """
        Gegenprobe: der _orig-Pfad (priorize_redacted=False) greift nie auf
        redacted_version zu und funktioniert daher unabhängig davon, ob eine
        geschwärzte Version existiert.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(self._orig_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'ungeschwaerzter-inhalt')

    def test_default_download_serves_redacted_file_when_one_exists(self):
        """
        Sobald eine geschwärzte Version existiert, funktioniert auch der
        Standardpfad - und liefert dann bewusst die geschwärzte, nicht die
        Original-Datei aus.
        """
        RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=self.anhang,
            attachment=SimpleUploadedFile(
                'geschwaerzt.jpg', b'geschwaerzte-version', content_type='image/jpeg',
            ),
        )
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(self._default_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'geschwaerzte-version')

    # --- Zugriffskontrolle (ergänzend, bisher ebenfalls ungetestet) --------

    def test_foreign_user_cannot_download_via_orig_url(self):
        """
        Bewusst über die _orig-URL getestet, damit dieser Test unabhängig
        vom oben dokumentierten Absturz-Bug ist.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.get(self._orig_url())
        self.assertEqual(response.status_code, 403)

    def test_anonymous_with_matching_session_can_download_own_attachment(self):
        """Gast-Zugriff über die in der Session hinterlegte generic_id des
        eigenen Beitrags - siehe beitrag_activate() & Co."""
        session = self.client.session
        session['beitrag_generic_id'] = str(self.beitrag.generic_id)
        session.save()

        response = self.client.get(self._orig_url())
        self.assertEqual(response.status_code, 200)

    def test_anonymous_with_foreign_session_gets_401(self):
        """
        Ungewöhnlicher Statuscode für diesen Fall: die View liefert hier
        explizit 401 statt der sonst überall in diesem Projekt üblichen 403 -
        dokumentiert das aktuelle (uneinheitliche) Verhalten.
        """
        session = self.client.session
        session['beitrag_generic_id'] = '00000000-0000-0000-0000-000000000000'
        session.save()

        response = self.client.get(self._orig_url())
        self.assertEqual(response.status_code, 401)
