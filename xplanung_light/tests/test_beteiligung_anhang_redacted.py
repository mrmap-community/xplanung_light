"""
Tests für die Schwärzung von Beitrags-Anhängen (views/beteiligungbeitraganhangredacted.py):
geschwärzte Fassung hochladen, ansehen und löschen.

Nur Administratoren der Gemeinde und Superuser dürfen schwärzen; anonyme Nutzer werden zur
Anmeldung geleitet, Fremde erhalten 403.
"""

import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
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


class BeteiligungBeitragAnhangRedacted(TestCase):
    """
    Create-, Detail- und Delete-Ansicht der geschwärzten Fassung eines Anhangs.

    Ausgangslage: BPlan 4318 der Gemeinde 1531 mit laufender Beteiligung und einem Beitrag
    (Einwendung zur Erschließung). Pro Test gibt es einen frischen Anhang (Foto der Einfahrt).
    Nutzer: der Gemeinde-Administrator admin_stadt_neustadt und ein Fremder ohne Rolle.
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
            bekanntmachung_datum=heute - datetime.timedelta(days=14),
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
        """Legt pro Test einen frischen Anhang am Beitrag an."""
        self.client = Client()
        # Für jeden Test ein frischer Original-Anhang, an dem redaktiert wird.
        self.anhang = BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=self.beitrag,
            name='Foto der Einfahrt',
            typ=BPlanBeteiligungBeitragAnhang.FOTO,
            attachment=SimpleUploadedFile(
                'original.jpg', b'ungeschwaerzter-inhalt', content_type='image/jpeg',
            ),
        )

    # --- URL-Helfer ---------------------------------------------------

    def _create_url(self, anhang=None):
        """URL zum Hochladen einer geschwärzten Fassung (Standard: der Anhang aus setUp)."""
        anhang = anhang or self.anhang
        return reverse('beteiligungbeitraganhangredacted-create', kwargs={
            'plantyp': 'bplan',
            'anhang_generic_id': str(anhang.generic_id),
        })

    def _detail_url(self, redacted):
        """URL der Detailseite der geschwärzten Fassung."""
        return reverse('beteiligungbeitraganhangredacted-detail', kwargs={
            'plantyp': 'bplan',
            'generic_id': str(redacted.generic_id),
        })

    def _delete_url(self, redacted):
        """URL zum Löschen der geschwärzten Fassung."""
        return reverse('beteiligungbeitraganhangredacted-delete', kwargs={
            'plantyp': 'bplan',
            'generic_id': str(redacted.generic_id),
        })

    def _post_redacted(self, anhang=None, content=b'geschwaerzte-version'):
        """Lädt eine geschwärzte Bilddatei (geschwaerzt.jpg) mit dem angegebenen Inhalt hoch."""
        upload = SimpleUploadedFile('geschwaerzt.jpg', content, content_type='image/jpeg')
        return self.client.post(self._create_url(anhang), data={'attachment': upload})

    def _make_redacted(self):
        """Legt direkt in der DB eine geschwärzte Version an, ohne über die View zu gehen."""
        return RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=self.anhang,
            attachment=SimpleUploadedFile(
                'geschwaerzt.jpg', b'geschwaerzte-version', content_type='image/jpeg',
            ),
        )

    # --- Create: Berechtigungen -----------------------------------------

    def test_anonymous_user_is_redirected_to_login_on_create(self):
        """
        Was wird geprüft:
            Ein anonymer Aufruf des Formulars zum Hochladen.

        Warum:
            Das Schwärzen ist nur angemeldeten Verantwortlichen erlaubt.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite.
        """
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_foreign_user_cannot_open_create_form(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet das Formular zum Hochladen.

        Warum:
            Anhänge können persönliche Daten enthalten; nur Verantwortliche der Gemeinde
            dürfen sie bearbeiten.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.fremder_user)
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_create_redacted_version_via_direct_post(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder sendet die geschwärzte Datei direkt per POST.

        Warum:
            Auch ohne das Formular zu öffnen darf kein Upload möglich sein.

        Erwartung:
            Status 403 und es entsteht keine geschwärzte Fassung.
        """
        self.client.force_login(self.fremder_user)
        response = self._post_redacted()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            RedactedBPlanBeteiligungBeitragAnhang.objects.filter(anhang=self.anhang).exists()
        )

    # --- Create: Erfolgsfall + Verknüpfung --------------------------------

    def test_gemeinde_admin_can_create_redacted_version(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator lädt eine geschwärzte Fassung hoch.

        Warum:
            Der erlaubte Hauptweg.

        Erwartung:
            Weiterleitung (302); der Anhang hat danach eine geschwärzte Fassung
            (redacted_version), die auf ihn verweist.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self._post_redacted()

        self.assertEqual(response.status_code, 302)
        # Bewusst neu aus der DB geladen statt refresh_from_db(): Reverse-
        # OneToOne-Deskriptoren cachen ihr "existiert nicht"-Ergebnis auf der
        # Instanz, refresh_from_db() räumt diesen Cache nicht zuverlässig auf.
        anhang = BPlanBeteiligungBeitragAnhang.objects.get(pk=self.anhang.pk)
        self.assertTrue(hasattr(anhang, 'redacted_version'))
        self.assertEqual(anhang.redacted_version.anhang_id, anhang.pk)

    def test_create_redirects_to_anhang_list_of_the_correct_beitrag(self):
        """
        Was wird geprüft:
            Das Ziel der Weiterleitung nach dem Hochladen.

        Warum:
            Der Administrator soll direkt wieder in der Anhangliste seines Beitrags landen.

        Erwartung:
            Weiterleitung auf die Anhangliste von Plan, Beteiligung und Beitrag.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self._post_redacted()
        self.assertRedirects(
            response,
            reverse('beteiligungbeitraganhang-list', kwargs={
                'plantyp': 'bplan',
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'pk': self.beitrag.pk,
            }),
        )

    def test_superuser_can_create_redacted_version_without_gemeinde_admin_role(self):
        """check_gemeinde_admin() lässt Superuser unabhängig von Admin-Rollen zu."""
        superuser = User.objects.get(pk=1)  # laut test_initial_data.py: admin, is_superuser
        self.client.force_login(superuser)
        response = self._post_redacted()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RedactedBPlanBeteiligungBeitragAnhang.objects.filter(anhang=self.anhang).exists()
        )

    # --- Create: bekannte Lücke - keine Duplikatsprüfung ------------------

    def test_creating_second_redacted_version_crashes_with_integrity_error(self):
        """
        Dokumentiert eine Lücke: die View prüft vor dem Speichern nicht, ob
        für diesen Anhang schon eine geschwärzte Version existiert (OneToOne
        ohne Vorab-Check). Ein zweiter POST landet nicht als sauberer
        Formularfehler beim Nutzer, sondern reißt eine ungefangene
        IntegrityError (--> 500) hoch. BeteiligungBeitragAnhangRedactedUpdateView
        existiert zwar schon als Klasse, ist aber noch ein leerer Stub (nur
        `pass`, kein Formular, keine URL) - der einzig unterstützte Weg, eine
        geschwärzte Version zu ersetzen, ist aktuell Löschen + Neuanlegen.

        Falls hier künftig eine "Version existiert bereits"-Meldung ergänzt
        wird, muss dieser Test entsprechend umgestellt werden - das wäre dann
        ein begrüßenswerter Fix, kein Regressionsfehler.
        """
        self.client.force_login(self.gemeinde_admin)
        erste_antwort = self._post_redacted(content=b'erste-version')
        self.assertEqual(erste_antwort.status_code, 302)

        with self.assertRaises(IntegrityError):
            self._post_redacted(content=b'zweite-version')

    # --- Detail: Berechtigungen + Inhalt ----------------------------------

    def test_anonymous_user_is_redirected_to_login_on_detail(self):
        """
        Was wird geprüft:
            Ein anonymer Aufruf der Detailseite einer geschwärzten Fassung.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite.
        """
        redacted = self._make_redacted()
        response = self.client.get(self._detail_url(redacted))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_foreign_user_cannot_view_redacted_detail(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet die Detailseite.

        Erwartung:
            Status 403.
        """
        redacted = self._make_redacted()
        self.client.force_login(self.fremder_user)
        response = self.client.get(self._detail_url(redacted))
        self.assertEqual(response.status_code, 403)

    def test_gemeinde_admin_can_view_redacted_detail(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet die Detailseite.

        Erwartung:
            Status 200.
        """
        redacted = self._make_redacted()
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(self._detail_url(redacted))
        self.assertEqual(response.status_code, 200)

    def test_detail_view_reports_creator_from_history(self):
        """
        Die History-Middleware (simple_history.middleware.HistoryRequestMiddleware,
        in base.py konfiguriert) soll history_user automatisch aus
        request.user befüllen - get_context_data() liest daraus
        'bearbeitet_von' für die Anzeige "wer hat das zuletzt geändert".
        """
        self.client.force_login(self.gemeinde_admin)
        create_response = self._post_redacted()
        self.assertEqual(create_response.status_code, 302)

        redacted = RedactedBPlanBeteiligungBeitragAnhang.objects.get(anhang=self.anhang)
        response = self.client.get(self._detail_url(redacted))

        self.assertEqual(response.context['bearbeitet_von'], self.gemeinde_admin)
        self.assertIsNotNone(response.context['letzte_aenderung_am'])

    def test_detail_view_without_request_context_reports_no_editor(self):
        """
        _make_redacted() legt den Datensatz direkt per .objects.create() an,
        ohne HTTP-Request-Kontext. HistoricalRecords erzeugt trotzdem einen
        History-Eintrag (post_save-Signal) - nur history_user bleibt None,
        weil HistoryRequestMiddleware ihn nur innerhalb eines echten Requests
        aus request.user befüllt. Ein Zeitstempel ist also vorhanden,
        'bearbeitet_von' bleibt aber None. Zeigt vor allem: die View stürzt
        bei fehlendem history_user nicht ab, sondern liefert sauber None.
        """
        redacted = self._make_redacted()
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(self._detail_url(redacted))

        self.assertIsNotNone(response.context['letzte_aenderung_am'])
        self.assertIsNone(response.context['bearbeitet_von'])

    # --- Delete: Berechtigungen + Nebenwirkungen --------------------------

    def test_anonymous_user_is_redirected_to_login_on_delete(self):
        """
        Was wird geprüft:
            Ein anonymer POST auf die Löschen-Ansicht.

        Warum:
            Ohne Anmeldung darf nichts gelöscht werden.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite; die geschwärzte Fassung bleibt
            bestehen.
        """
        redacted = self._make_redacted()
        response = self.client.post(self._delete_url(redacted))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertTrue(
            RedactedBPlanBeteiligungBeitragAnhang.objects.filter(pk=redacted.pk).exists()
        )

    def test_foreign_user_cannot_delete_redacted_version(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder löscht die geschwärzte Fassung.

        Erwartung:
            Status 403; die geschwärzte Fassung bleibt bestehen.
        """
        redacted = self._make_redacted()
        self.client.force_login(self.fremder_user)
        response = self.client.post(self._delete_url(redacted))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            RedactedBPlanBeteiligungBeitragAnhang.objects.filter(pk=redacted.pk).exists()
        )

    def test_gemeinde_admin_can_delete_redacted_version(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator löscht die geschwärzte Fassung.

        Erwartung:
            Weiterleitung (302) und die geschwärzte Fassung existiert nicht mehr.
        """
        redacted = self._make_redacted()
        self.client.force_login(self.gemeinde_admin)
        response = self.client.post(self._delete_url(redacted))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            RedactedBPlanBeteiligungBeitragAnhang.objects.filter(pk=redacted.pk).exists()
        )

    def test_deleting_redacted_version_does_not_delete_the_original_anhang(self):
        """CASCADE steht auf der Redacted-Seite des OneToOneField - das Original
        darf beim Löschen der geschwärzten Version nicht mit verschwinden."""
        redacted = self._make_redacted()
        self.client.force_login(self.gemeinde_admin)
        self.client.post(self._delete_url(redacted))

        self.assertTrue(BPlanBeteiligungBeitragAnhang.objects.filter(pk=self.anhang.pk).exists())
        # Frisch geladen statt refresh_from_db() - siehe Hinweis oben bei
        # test_gemeinde_admin_can_create_redacted_version.
        anhang = BPlanBeteiligungBeitragAnhang.objects.get(pk=self.anhang.pk)
        self.assertFalse(hasattr(anhang, 'redacted_version'))
