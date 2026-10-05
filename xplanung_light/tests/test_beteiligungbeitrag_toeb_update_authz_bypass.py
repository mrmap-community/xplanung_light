"""
Regressionstests für einen früheren Autorisierungs-Bypass in der TÖB-Bearbeiten-Ansicht: Die
Berechtigungsprüfung lag nur in get_context_data(), das django-formset beim POST nie aufruft.
Dadurch konnte jeder Nutzer per POST Beiträge ändern. Die Prüfung sitzt jetzt in dispatch().
"""

import datetime

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from xplanung_light.forms import BPlanBeteiligungBeitragToebCollection
from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    ToebUnit,
)
from xplanung_light.views.beteiligungbeitrag import BeteiligungBeitragToebUpdateView


def _safe_error_summary(errors):
    """
    Wandelt die verschachtelte Fehlerstruktur einer FormCollection in einfache Strings um, ohne
    str() oder render() aufzurufen. Grund: FormsetErrorList hat in dieser Version einen Fehler
    in render(), der die eigentliche Diagnose verdecken würde.
    """
    if isinstance(errors, DjangoValidationError):
        return list(errors.messages)
    as_data = getattr(errors, 'as_data', None)
    if callable(as_data):
        try:
            return _safe_error_summary(as_data())
        except Exception as exc:  # pragma: no cover - reiner Diagnose-Fallback
            return f'<as_data() fehlgeschlagen: {exc!r}>'
    if isinstance(errors, dict):
        return {key: _safe_error_summary(value) for key, value in errors.items()}
    if isinstance(errors, (list, tuple)):
        return [_safe_error_summary(item) for item in errors]
    return repr(errors)


class BeteiligungBeitragToebUpdateAuthorizationBypass(TestCase):
    """
    BeteiligungBeitragToebUpdateView erbt von formset.views.EditCollectionView.
    Die einzige Berechtigungsprüfung im View steckt in get_context_data():

        if self.request.user.is_superuser == False:
            ...
            if AdminOrgaUser.objects.filter(..., is_toeb_reporter=True).exists():
                return context
            raise PermissionDenied(...)

    Laut django-formset-Quellcode (formset/views.py) ruft
    FormCollectionViewMixin.post() get_context_data() aber NIE auf:

        def post(self, request, **kwargs):
            form_collection = self.get_form_collection()
            if form_collection.is_valid():
                return self.form_collection_valid(form_collection)
            ...

    form_collection_valid() wiederum ist NICHT überschrieben - es greift die
    Version von EditCollectionView, die form_collection.construct_instance()
    aufruft und damit tatsächlich speichert (construct_instance() ruft
    holder.save() für jedes ModelForm-Holder auf, siehe formset/collection.py).

    Ergebnis: die Berechtigungsprüfung griff nur beim GET (Formular
    anzeigen), niemals beim tatsächlichen Speichern per POST. Jeder Nutzer -
    unabhängig von is_toeb_reporter - konnte einen Beitrag über diesen View
    bearbeiten, sobald er einen validen POST-Body schickte.

    Mittlerweile behoben: die Prüfung (inkl. is_authenticated-Check) sitzt
    jetzt in dispatch(), läuft also vor get() UND post(). Die Tests unten
    sichern das gegen eine Regression ab - sowohl für eingeloggte, nicht
    berechtigte Nutzer als auch für komplett anonyme Requests (GET und
    POST).

    Der erste Test unten belegt den ursprünglichen, mittlerweile behobenen
    Bypass weiterhin direkt auf Code-Ebene (ruft form_collection_valid() so
    auf, wie es der View bei einem validen POST täte) - unabhängig vom
    genauen JSON-Wire-Format, das ein echter HTTP-POST über django-formset
    verwenden würde. Das macht den Test robust gegen Unsicherheiten über
    das exakte Request-Format, während er trotzdem exakt den ursprünglich
    verwundbaren Code-Pfad prüft (form_collection_valid() selbst enthält
    weiterhin keine eigene Prüfung - der Schutz kommt jetzt ausschließlich
    aus dispatch()).
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

        heute = datetime.date.today()
        cls.beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.plan,
            bekanntmachung_datum=heute - datetime.timedelta(days=7),
            start_datum=heute - datetime.timedelta(days=7),
            end_datum=heute + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.TOEB,
            allow_online_beitrag=False,
        )

        cls.toeb_sachbearbeiter = User.objects.create_user(
            username='toeb_sachbearbeiter_bypass', password='nicht-relevant',
        )
        toeb_orga_user = AdminOrgaUser.objects.create(
            user=cls.toeb_sachbearbeiter, organization=cls.gemeinde,
            is_admin=False, is_toeb_reporter=True,
        )
        cls.toeb = ToebUnit.objects.create(
            name='Untere Wasserbehörde (Bypass-Test)',
            email='wasserbehoerde-bypass@example.org',
            organization=cls.gemeinde,
        )
        cls.toeb.editors.add(toeb_orga_user)

        # Nutzer ganz ohne is_toeb_reporter-Rolle - darf laut Fachlogik
        # diesen Beitrag NICHT bearbeiten dürfen.
        cls.fremder_user = User.objects.create_user(
            username='fremder_user_toeb_bypass', password='nicht-relevant',
        )

    def setUp(self):
        self.client = Client()
        self.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung,
            titel='Ursprünglicher Titel',
            beschreibung='Ursprüngliche Beschreibung.',
            typ=BPlanBeteiligungBeitrag.MAIL,
            email='wasserbehoerde-bypass@example.org',
            eingangsdatum=datetime.date.today(),
            approved=True,
            toeb=self.toeb,
        )

    def _make_view(self, user):
        """Baut eine BeteiligungBeitragToebUpdateView-Instanz so auf, wie sie
        nach dispatch() für diesen Beitrag aussehen würde."""
        request = RequestFactory().post('/irrelevant/')
        request.user = user
        view = BeteiligungBeitragToebUpdateView()
        view.request = request
        view.object = self.beitrag
        view.plantyp = 'bplan'
        view.planmodel = BPlan
        view.beteiligung_model = BPlanBeteiligung
        view.collection_class = BPlanBeteiligungBeitragToebCollection
        view.reference_model_name_lower = 'bplan'
        view.kwargs = {
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
            'pk': self.beitrag.pk,
        }
        return view

    # --- Hauptbefund: form_collection_valid() prüft nichts -----------------

    def test_form_collection_valid_persists_changes_without_any_authorization_check(self):
        """
        form_collection_valid() selbst enthält weiterhin KEINE eigene
        Berechtigungsprüfung - der Schutz kommt jetzt ausschließlich aus
        dispatch(). Dieser Test ruft form_collection_valid() bewusst direkt
        auf, unter Umgehung von dispatch(), und zeigt damit: die Methode
        speichert anstandslos, egal wer sie aufruft. Das ist seit dem Fix
        kein live ausnutzbarer Bug mehr (dispatch() lässt einen
        unberechtigten Request gar nicht erst bis hierhin durchkommen,
        siehe die Tests weiter unten) - der Test dokumentiert stattdessen,
        dass es hier keine Verteidigung in der Tiefe gibt: fällt dispatch()
        aus irgendeinem Grund erneut weg (Refactoring, neue Subklasse ohne
        den Check, ...), greift nichts mehr.
        """
        view = self._make_view(self.fremder_user)

        collection = BPlanBeteiligungBeitragToebCollection(
            data={
                'beitrag': {
                    'id': str(self.beitrag.pk),
                    'titel': 'Vom fremden Nutzer geänderter Titel',
                    'email': self.beitrag.email,
                    'beschreibung': (
                        '{"type":"doc","content":[{"type":"paragraph",'
                        '"content":[{"type":"text","text":'
                        '"Vom fremden Nutzer geänderte Beschreibung."}]}]}'
                    ),
                    'bplan_beteiligung': str(self.beteiligung.pk),
                },
                'attachments': [],
            },
            instance=self.beitrag,
        )
        self.assertTrue(
            collection.is_valid(),
            f"Testdaten sind laut FormCollection ungültig: "
            f"{_safe_error_summary(collection.errors)}",
        )

        # Exakt das, was FormCollectionViewMixin.post() bei einem validen
        # POST aufrufen würde - ohne vorher get_context_data() (und damit
        # die einzige Berechtigungsprüfung) durchlaufen zu haben.
        view.form_collection_valid(collection)

        self.beitrag.refresh_from_db()
        self.assertEqual(
            self.beitrag.titel, 'Vom fremden Nutzer geänderter Titel',
            "Erwarteter (fehlerhafter) IST-Zustand: die Änderung eines "
            "Nutzers ganz ohne is_toeb_reporter-Rolle wurde übernommen.",
        )

    # --- Kontrollprobe: die Prüfung selbst funktioniert - nur ihr Aufrufort nicht ---

    def test_get_context_data_still_correctly_blocks_unauthorized_user(self):
        """
        Zeigt, dass die Logik in get_context_data() an sich funktioniert -
        das Problem ist ausschließlich, dass django-formset diese Methode
        beim POST nie aufruft.
        """
        view = self._make_view(self.fremder_user)
        with self.assertRaises(PermissionDenied):
            view.get_context_data()

    def test_get_context_data_allows_the_actual_toeb_reporter(self):
        """
        Was wird geprüft:
            Der berechtigte TÖB-Reporter ruft get_context_data() direkt auf.

        Warum:
            Gegenprobe zum vorigen Test: Die Prüfung blockiert nicht jeden, sondern nur
            Unberechtigte.

        Erwartung:
            Kein Fehler, und der Kontext enthält den BPlan.
        """
        view = self._make_view(self.toeb_sachbearbeiter)
        context = view.get_context_data()
        self.assertEqual(context['bplan'], self.plan)

    # --- GET über die echte URL: stürzt für Anonyme ab ----------------------

    def test_anonymous_get_is_redirected_to_login(self):
        """
        Regressionstest für den Fix: dispatch() prüft jetzt vor dem
        eigentlichen GET/POST is_authenticated und reicht für einen
        anonymen Request an super().dispatch() durch, wo LoginRequiredMixin
        zum Login umleitet - kein TypeError mehr.
        """
        url = reverse('beteiligungbeitrag-toeb-update', kwargs={
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
            'pk': self.beitrag.pk,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_anonymous_post_is_redirected_to_login_and_does_not_save(self):
        """
        Der eigentlich kritische Fall aus dem ursprünglichen Befund: ein
        anonymer POST darf jetzt nicht mehr durchgehen. dispatch() prüft
        is_authenticated jetzt VOR dem Aufruf von form_collection_valid(),
        also unabhängig davon, ob get_context_data() beim POST aufgerufen
        wird oder nicht.
        """
        url = reverse('beteiligungbeitrag-toeb-update', kwargs={
            'plantyp': 'bplan',
            'planid': self.PLAN_PK,
            'beteiligungid': self.beteiligung.pk,
            'pk': self.beitrag.pk,
        })
        response = self.client.post(url, data={}, content_type='application/json')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.beitrag.refresh_from_db()
        self.assertEqual(self.beitrag.titel, 'Ursprünglicher Titel')
