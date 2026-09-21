import datetime

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungToebNotification,
    ToebUnit,
)


class BeteiligungToebNotification(TestCase):
    """
    Tests für BeteiligungToebNotificationCreateView (views/beteiligungtoebnotification.py) -
    das Formular, über das eine Gemeinde die TOEBs (Träger öffentlicher
    Belange) einer Beteiligung per E-Mail zur Stellungnahme auffordert.

    STAND: die View trug bis vor kurzem KEINE Zugriffskontrolle - ein
    komplett anonymer Request konnte echten E-Mail-Versand an TOEB-
    Sachbearbeiter auslösen. Das wurde durch Ergänzen von LoginRequiredMixin
    behoben (siehe test_anonymous_user_is_redirected_to_login unten, jetzt
    ein Regressionstest für genau diesen Fix).

    OFFEN: keine der oben genannten Lücken mehr - LoginRequiredMixin
    (Anmeldepflicht) UND GemeindeAdminRequiredMixin (Admin-Rolle für DIESE
    Gemeinde) sind inzwischen beide gesetzt, jeweils als Regressionstest
    unten abgesichert.

    Getestet wird nur der BPlan-Zweig; die View verzweigt intern auf
    denselben Plantyp-Mustern wie an anderer Stelle in diesem Projekt
    (siehe test_beteiligung_workflow.py) - ein FPlan-Spiegel wäre bei Bedarf
    leicht nachzuziehen.
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
        cls.gemeinde = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        # Aus der Fixture: Admin der Organisation 1531, siehe admin_orga_user.json
        cls.gemeinde_admin = User.objects.get(username='admin_stadt_neustadt')

        # Ein bei keiner Gemeinde als Admin/Reporter hinterlegter, aber
        # trotzdem authentifizierter Nutzer - für den Test auf die noch
        # offene Rollen-Lücke.
        cls.fremder_user = User.objects.create_user(
            username='fremder_user', password='nicht-relevant',
        )

        cls.sachbearbeiter = User.objects.create_user(
            username='toeb_sachbearbeiter',
            email='sachbearbeiter@toeb.example.org',
            password='nicht-relevant',
        )
        cls.sachbearbeiter_orga_user = AdminOrgaUser.objects.create(
            user=cls.sachbearbeiter,
            organization=cls.gemeinde,
            is_admin=False,
            is_toeb_reporter=True,
        )
        # Ein zweiter Sachbearbeiter ohne hinterlegte E-Mail-Adresse - prüft,
        # dass der `if user.user.email:`-Filter im View sauber greift.
        cls.sachbearbeiter_ohne_email = User.objects.create_user(
            username='toeb_ohne_email', password='nicht-relevant',
        )
        cls.orga_user_ohne_email = AdminOrgaUser.objects.create(
            user=cls.sachbearbeiter_ohne_email,
            organization=cls.gemeinde,
            is_admin=False,
            is_toeb_reporter=True,
        )

        cls.toeb = ToebUnit.objects.create(
            name='Untere Wasserbehörde',
            email='wasserbehoerde@example.org',
            organization=cls.gemeinde,
        )
        cls.toeb.editors.add(cls.sachbearbeiter_orga_user, cls.orga_user_ohne_email)

        # Ein zweiter TOEB, der der Beteiligung bewusst NICHT zugewiesen
        # wird - für den Test auf nicht auswählbare TOEBs.
        cls.nicht_zugewiesener_toeb = ToebUnit.objects.create(
            name='Nicht zugewiesene Stelle',
            email='sonstige-stelle@example.org',
            organization=cls.gemeinde,
        )

    def setUp(self):
        self.client = Client()
        heute = datetime.date.today()
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.plan,
            bekanntmachung_datum=heute - datetime.timedelta(days=1),
            start_datum=heute - datetime.timedelta(days=1),
            end_datum=heute + datetime.timedelta(days=14),
            typ=BPlanBeteiligung.TOEB,
            allow_online_beitrag=False,
        )
        self.beteiligung.assigned_toebs.add(self.toeb)

    def _url(self):
        return reverse('beteiligungnotification-create', kwargs={
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
        })

    def _post(self, toebs=None, message='Bitte um Stellungnahme.'):
        toebs = self.toeb.pk if toebs is None else toebs
        return self.client.post(self._url(), data={
            'message': message,
            'selected_toebs': [toebs] if not isinstance(toebs, (list, tuple)) else toebs,
        })

    # --- Zugriffskontrolle -----------------------------------------------

    def test_anonymous_user_is_redirected_to_login(self):
        """Regressionstest für den LoginRequiredMixin-Fix: anonyme Requests
        dürfen keinen E-Mail-Versand mehr auslösen."""
        response = self._post()

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(
            BPlanBeteiligungToebNotification.objects.filter(
                bplanbeteiligung=self.beteiligung
            ).exists()
        )

    def test_authenticated_user_without_gemeinde_admin_role_is_forbidden(self):
        """
        Regressionstest für den GemeindeAdminRequiredMixin-Fix: ein
        eingeloggter Nutzer ohne Admin-Rolle für DIESE Gemeinde bekommt jetzt
        403 statt erfolgreich eine Benachrichtigung auszulösen.
        """
        self.client.force_login(self.fremder_user)

        response = self._post()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(
            BPlanBeteiligungToebNotification.objects.filter(
                bplanbeteiligung=self.beteiligung
            ).exists()
        )

    def test_foreign_user_cannot_open_create_form(self):
        """check_gemeinde_admin() läuft in get_form_kwargs() - greift also
        auch beim reinen GET, nicht erst beim POST."""
        self.client.force_login(self.fremder_user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    # --- E-Mail-Versand: korrekte Empfänger und Inhalt ----------------------

    def test_notification_sends_email_only_to_editors_with_email_address(self):
        self.client.force_login(self.gemeinde_admin)
        self._post()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['sachbearbeiter@toeb.example.org'])

    def test_notification_email_contains_the_custom_message(self):
        self.client.force_login(self.gemeinde_admin)
        self._post(message='Bitte prüfen Sie die Auswirkungen auf den Grundwasserspiegel.')

        self.assertEqual(len(mail.outbox), 1)
        gesendete_mail = mail.outbox[0]
        # HTML-Alternative UND Text-Body enthalten den Kommentar
        self.assertIn('Grundwasserspiegel', gesendete_mail.body)
        html_alternative = gesendete_mail.alternatives[0][0]
        self.assertIn('Grundwasserspiegel', html_alternative)

    def test_notification_subject_references_beteiligung_deadline(self):
        self.client.force_login(self.gemeinde_admin)
        self._post()
        self.assertIn(str(self.beteiligung.end_datum), mail.outbox[0].subject)

    def test_notification_stores_recipient_protocol(self):
        self.client.force_login(self.gemeinde_admin)
        self._post()

        notification = BPlanBeteiligungToebNotification.objects.get(
            bplanbeteiligung=self.beteiligung
        )
        self.assertEqual(len(notification.protocol), 1)
        protokoll_eintrag = notification.protocol[0]
        self.assertEqual(protokoll_eintrag['name'], str(self.toeb))
        self.assertEqual(protokoll_eintrag['email'], ['sachbearbeiter@toeb.example.org'])

    def test_notification_sets_start_and_end_timestamps(self):
        self.client.force_login(self.gemeinde_admin)
        self._post()
        notification = BPlanBeteiligungToebNotification.objects.get(
            bplanbeteiligung=self.beteiligung
        )
        self.assertIsNotNone(notification.start)
        self.assertIsNotNone(notification.end)
        self.assertGreaterEqual(notification.end, notification.start)

    # --- Zeitfenster ---------------------------------------------------

    def test_notification_before_bekanntmachung_datum_is_rejected(self):
        self.client.force_login(self.gemeinde_admin)
        heute = datetime.date.today()
        self.beteiligung.bekanntmachung_datum = heute + datetime.timedelta(days=1)
        self.beteiligung.save()

        response = self._post()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(
            BPlanBeteiligungToebNotification.objects.filter(
                bplanbeteiligung=self.beteiligung
            ).exists()
        )

    def test_notification_after_end_datum_is_rejected(self):
        self.client.force_login(self.gemeinde_admin)
        heute = datetime.date.today()
        self.beteiligung.end_datum = heute - datetime.timedelta(days=1)
        self.beteiligung.save()

        response = self._post()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])

    # --- Auswahl nicht zugewiesener TOEBs ------------------------------

    def test_selecting_toeb_not_assigned_to_beteiligung_is_rejected(self):
        """
        Das Formular begrenzt die gültigen Auswahlmöglichkeiten auf
        ToebUnit.objects.filter(bplan_beteiligungen=beteiligung) - ein TOEB,
        der der Beteiligung nicht über assigned_toebs zugewiesen wurde, darf
        also nicht ausgewählt werden können, selbst wenn seine pk im POST
        mitgeschickt wird.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self._post(toebs=self.nicht_zugewiesener_toeb.pk)

        self.assertEqual(response.status_code, 200)  # Formularfehler, kein Redirect
        self.assertEqual(mail.outbox, [])
        self.assertFalse(
            BPlanBeteiligungToebNotification.objects.filter(
                bplanbeteiligung=self.beteiligung
            ).exists()
        )
