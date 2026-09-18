import datetime

from django.test import TestCase, Client
from django.urls import reverse

from captcha.models import CaptchaStore

from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag


class BeitragAuthenticate(TestCase):
    """
    Gast-Authentifizierung über beitrag_authenticate().

    Ein Gast, der seine Stellungnahme später bearbeiten will (aktivieren,
    zurückziehen), muss sich über die bei der Einreichung angegebene
    E-Mail-Adresse ausweisen. Bei Erfolg landet die generic_id des Beitrags
    in der Session - genau das, worauf beitrag_activate/_withdraw/_reactivate
    aufbauen (siehe test_beteiligung_workflow.py).

    Zum Captcha: CAPTCHA_TEST_MODE=True bringt hier NICHTS, obwohl es das in
    anderen Projekten oft tut. django-simple-captcha liest CAPTCHA_TEST_MODE
    in captcha/conf/settings.py als Modulkonstante einmalig beim ersten
    Import (getattr(django_settings, 'CAPTCHA_TEST_MODE', False)) - nicht
    dynamisch. @override_settings patcht nur django.conf.settings; das schon
    eingefrorene Modulattribut in captcha.conf.settings bekommt davon nichts
    mit, weil niemand auf das setting_changed-Signal lauscht. Deshalb legen
    wir stattdessen einen echten CaptchaStore-Eintrag an und schicken dessen
    hashkey/response mit - das funktioniert unabhängig von der
    Settings-Ladereihenfolge.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    PLAN_PK = 4318
    RICHTIGE_EMAIL = 'gast@example.org'
    FALSCHE_EMAIL = 'jemand.anderes@example.org'

    @classmethod
    def setUpTestData(cls):
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        heute = datetime.date.today()
        cls.beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.plan,
            bekanntmachung_datum=heute - datetime.timedelta(days=14),
            start_datum=heute - datetime.timedelta(days=7),
            end_datum=heute + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )

    def setUp(self):
        self.client = Client()
        self.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung,
            titel='Einwendung zur Erschließung',
            beschreibung='Die Zufahrt ist aus meiner Sicht zu schmal.',
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name='Erika Mustermann',
            email=self.RICHTIGE_EMAIL,
            eingangsdatum=datetime.date.today(),
        )

    def _url(self):
        return reverse('beteiligungbeitrag-authenticate', kwargs={
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
            'generic_id': str(self.beitrag.generic_id),
        })

    def _captcha_post_data(self):
        """Legt einen echten CaptchaStore-Eintrag an und liefert die dazu
        passenden POST-Felder - unabhängig von CAPTCHA_TEST_MODE gültig."""
        store = CaptchaStore.objects.create(challenge='dummy', response='affe')
        return {'captcha_0': store.hashkey, 'captcha_1': store.response}

    def _post(self, email):
        data = self._captcha_post_data()
        data['email'] = email
        return self.client.post(self._url(), data)

    # --- Erfolgsfall --------------------------------------------------

    def test_richtige_email_setzt_generic_id_in_session_und_leitet_weiter(self):
        # Erfolgsfall: richtige E-Mail -> Session gesetzt + Redirect auf die Detailseite.
        response = self._post(self.RICHTIGE_EMAIL)

        self.assertEqual(
            self.client.session.get('beitrag_generic_id'),
            str(self.beitrag.generic_id),
        )
        self.assertRedirects(
            response,
            reverse('gastbeteiligungbeitrag-detail', kwargs={
                'plantyp': 'bplan',
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'generic_id': str(self.beitrag.generic_id),
            }),
        )

    def test_erfolgreiche_authentifizierung_gewaehrt_zugriff_auf_detailseite(self):
        """End-to-End: nach der Authentifizierung ist die Detailseite ohne
        weiteren Redirect erreichbar."""
        self._post(self.RICHTIGE_EMAIL)
        detail_response = self.client.get(
            reverse('gastbeteiligungbeitrag-detail', kwargs={
                'plantyp': 'bplan',
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'generic_id': str(self.beitrag.generic_id),
            })
        )
        self.assertEqual(detail_response.status_code, 200)

    # --- Fehlerfall -----------------------------------------------------

    def test_falsche_email_setzt_keine_session_und_zeigt_fehlermeldung(self):
        # Negativfall: falsche E-Mail -> keine Session, Formular wird mit Fehlermeldung neu angezeigt.
        response = self._post(self.FALSCHE_EMAIL)

        self.assertNotIn('beitrag_generic_id', self.client.session)
        self.assertEqual(response.status_code, 200)  # kein Redirect
        messages = list(response.context['messages'])
        self.assertTrue(
            any('nicht' in str(m) and 'E-Mail' in str(m) for m in messages),
            "Erwartete Fehlermeldung zur falschen E-Mail wurde nicht gefunden",
        )

    def test_falsche_email_gewaehrt_keinen_zugriff_auf_geschuetzten_workflow(self):
        """
        Verzahnung mit den Workflow-Views: ohne gültige Session bleibt
        beitrag_activate() weiterhin gesperrt.
        """
        self._post(self.FALSCHE_EMAIL)
        response = self.client.get(reverse('beteiligungbeitrag-activate', kwargs={
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
            'generic_id': str(self.beitrag.generic_id),
        }))
        self.assertEqual(response.status_code, 302)
        self.assertIn('authenticate', response.url)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.get(pk=self.beitrag.pk).approved)

    def test_email_ohne_gross_klein_schreibung_wird_nicht_gleichgesetzt(self):
        """
        Dokumentiert das aktuelle Verhalten: der Vergleich beitrag.email ==
        cleaned_data['email'] ist exakt / case-sensitiv. Ein Groß-/
        Kleinschreibungsunterschied führt zur Ablehnung.
        """
        response = self._post(self.RICHTIGE_EMAIL.upper())
        self.assertNotIn('beitrag_generic_id', self.client.session)
        self.assertEqual(response.status_code, 200)