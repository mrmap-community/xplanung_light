"""
Abdeckungstests für die Beitrags-Views (views/beteiligungbeitrag.py und
views/beteiligungbeitraganhang.py), die über normale HTTP-Requests nicht erreichbar sind:

1. Die Anhangliste für FPlan-Beiträge (der FPlan-Zweig in dispatch und get_queryset).
2. Die Methode form_collection_valid der Create-Views (Generic und TÖB). django-formset
   kann beim POST keine Dateien mitschicken (ein JSON-Body kennt kein files-Mapping),
   deshalb werden die Saved-Forms hier direkt aufgerufen — wie sie django-formset sie
   nach erfolgreicher Validierung an die View weitergibt.
"""

import datetime
import json
import uuid

from django.contrib.auth.models import User
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from unittest.mock import MagicMock

from xplanung_light.models import (
    AdministrativeOrganization as Orga,
    AdminOrgaUser,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang,
    FPlan,
    FPlanBeteiligung,
    FPlanBeteiligungBeitrag,
    FPlanBeteiligungBeitragAnhang,
    ToebUnit,
)
from xplanung_light.views.beteiligungbeitrag import (
    BeteiligungBeitragGenericCreateView,
    BeteiligungBeitragToebCreateView,
)

HEUTE = datetime.date.today()

DUMMY_POLYGON = GEOSGeometry(
    'POLYGON ((6.0 50.0, 6.1 50.0, 6.1 50.1, 6.0 50.1, 6.0 50.0))')

TIPTAP_LEER = '{"type": "doc", "content": []}'


class BeitragFormFake:
    """
    Simuliert die gültige Haupt-Form („beitrag") einer django-formset-Collection:
    eine echte, bereits gespeicherte Instanz als .instance und eine echte
    ungespeicherte Instanz als Rückgabe von save(commit=False).
    """

    def __init__(self, gespeicherte_instanz, ungespeicherte_instanz):
        self.instance = gespeicherte_instanz
        self._neu = ungespeicherte_instanz

    def save(self, commit=False):
        return self._neu

    def save_m2m(self):
        pass


def anhang_holder(*anhang_instanzen, ohneformular=False):
    """
    Baut den Collection-Holder für die Anhangs-Collection nach: valid_holders ist
    eine Liste von Dicts, deren Schlüssel 'attachment' das gültige Anhangs-Form
    enthält. Mit ohneformular=True wird ein Dict ohne Formular ergänzt (leere
    Sub-Form wird übersprungen).
    """
    dicts = []
    for instanz in anhang_instanzen:
        form = MagicMock()
        form.save.return_value = instanz
        dicts.append({'attachment': form})
    if ohneformular:
        dicts.append({'anderes_feld': MagicMock()})
    holder = MagicMock()
    holder.valid_holders = dicts
    return holder


class FPlanAnhangListTests(TestCase):
    """Die Anhangliste eines FPlan-Beitrags — bisher nur für BPlan getestet."""

    @classmethod
    def setUpTestData(cls):
        cls.kommune = Orga.objects.create(
            name='Kreis Windkraft', ls='07', ks='316', gs='000')
        cls.admin = User.objects.create_user(
            username='fplan_admin', password='password123')
        AdminOrgaUser.objects.create(
            organization=cls.kommune, user=cls.admin, is_admin=True)

        cls.fplan = FPlan.objects.create(
            name='FPlan Windkraft Liste', geltungsbereich=DUMMY_POLYGON)
        cls.fplan.gemeinde.add(cls.kommune)
        cls.beteiligung = FPlanBeteiligung.objects.create(
            fplan=cls.fplan, typ='1000', bekanntmachung_datum=HEUTE,
            start_datum=HEUTE, end_datum=HEUTE + datetime.timedelta(days=30),
            allow_online_beitrag=True)
        cls.beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=cls.beteiligung, titel='Einwand Wald',
            beschreibung=TIPTAP_LEER, name='Max Mustermann',
            email='max@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=HEUTE, typ='1000')
        cls.anhang = FPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=cls.beitrag, name='Karte Wald', typ='3000',
            attachment=SimpleUploadedFile(
                'karte.pdf', b'%PDF-1.4', content_type='application/pdf'))

    def test_fplan_anhang_list_rendered_for_gemeinde_admin(self):
        """
        Was wird geprüft:
            Die Anhangliste zu einem Beitrag eines FPlans, aufgerufen von einem
            Gemeinde-Administrator.

        Warum:
            Die Liste unterscheidet pro Plantyp in dispatch() und get_queryset()
            nach Beteiligung und Plan; der FPlan-Zweig war bislang ungetestet.

        Erwartung:
            Status 200 und der angelegte Anhang erscheint in der Tabelle.
        """
        self.client.force_login(self.admin)
        url = reverse('beteiligungbeitraganhang-list', kwargs={
            'plantyp': 'fplan',
            'planid': self.fplan.pk,
            'beteiligungid': self.beteiligung.pk,
            'pk': self.beitrag.pk,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        qs = response.context['beteiligungbeitraganhang_list']
        self.assertEqual([a.pk for a in qs], [self.anhang.pk])


class GenericCreateFormCollectionValidTests(TestCase):
    """form_collection_valid der manuellen Erfassung (GenericCreateView)."""

    @classmethod
    def setUpTestData(cls):
        cls.kommune = Orga.objects.create(
            name='Stadt Formular', ls='07', ks='316', gs='000')
        cls.bplan = BPlan.objects.create(
            name='BPlan Formular', geltungsbereich=DUMMY_POLYGON)
        cls.bplan.gemeinde.add(cls.kommune)
        cls.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.bplan, typ='1000', bekanntmachung_datum=HEUTE,
            start_datum=HEUTE, end_datum=HEUTE + datetime.timedelta(days=30),
            allow_online_beitrag=True)
        cls.fplan = FPlan.objects.create(
            name='FPlan Formular', geltungsbereich=DUMMY_POLYGON)
        cls.fplan.gemeinde.add(cls.kommune)
        cls.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=cls.fplan, typ='1000', bekanntmachung_datum=HEUTE,
            start_datum=HEUTE, end_datum=HEUTE + datetime.timedelta(days=30),
            allow_online_beitrag=True)

    def _view(self, plantyp):
        """View-Instanz, wie sie dispatch() für den jeweiligen Plantyp hinterlässt."""
        view = BeteiligungBeitragGenericCreateView()
        view.plantyp = plantyp
        if plantyp == 'bplan':
            view.model = BPlanBeteiligungBeitrag
            view.beteiligung = self.bplan_beteiligung
        else:
            view.model = FPlanBeteiligungBeitrag
            view.beteiligung = self.fplan_beteiligung
        view.kwargs = {'beteiligungid': (
            self.bplan_beteiligung.pk if plantyp == 'bplan'
            else self.fplan_beteiligung.pk)}
        view.success_url = '/fertig/'
        return view

    def test_beitrag_wird_neu_angelegt_und_anhaenge_verlinkt(self):
        """
        Was wird geprüft:
            Das Speichern einer gültigen Formular-Collection mit einem Beitrag und
            zwei Anhängen (einem echten Formular und einem leeren Dict).

        Warum:
            django-formset übergibt der View nur gültige Forms; ein bereits geladener
            Beitrag muss beim Anlegen zurückgesetzt werden und die Anhänge müssen mit
            dem NEUEN Beitrag verknüpft werden. Per HTTP-POST sind keine Dateien
            übertragbar, deshalb der direkte Aufruf der Speichermethode.

        Erwartung:
            Der Originalbeitrag bleibt unverändert, es entsteht ein neuer Beitrag mit
            frischem Primary Key; der Anhang zeigt auf den neuen Beitrag, das leere
            Dict wird übersprungen; die Antwort enthält die Erfolgs-URL.
        """
        original = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel='Vorlage',
            beschreibung=TIPTAP_LEER, name='Vorlagen Nutzer',
            email='vorlage@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=HEUTE, typ='1000')
        original_pk = original.pk
        neu = BPlanBeteiligungBeitrag(
            bplan_beteiligung=self.bplan_beteiligung, titel='Neu erfasst',
            beschreibung=TIPTAP_LEER, name='Sachbearbeitung',
            email='sachbearbeitung@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=HEUTE, typ='1000')
        anhang_neu = BPlanBeteiligungBeitragAnhang(
            name='Scan des Briefs', typ='1000',
            attachment=SimpleUploadedFile(
                'scan.pdf', b'%PDF-1.4', content_type='application/pdf'))

        collection = MagicMock()
        collection.valid_holders = {
            'beitrag': BeitragFormFake(original, neu),
            'attachments': anhang_holder(anhang_neu, ohneformular=True),
        }
        response = self._view('bplan').form_collection_valid(collection)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)['success_url'], '/fertig/')
        # Original unverändert, neuer Beitrag mit eigenem pk in der Datenbank
        # (die View setzt .pk des übergebenen Formular-Objekts auf None zurück,
        #  deshalb mit gemerkter pk prüfen)
        original = BPlanBeteiligungBeitrag.objects.get(pk=original_pk)
        self.assertEqual(original.titel, 'Vorlage')
        neu.refresh_from_db()
        self.assertIsNotNone(neu.pk)
        self.assertNotEqual(neu.pk, original_pk)
        self.assertEqual(
            BPlanBeteiligungBeitrag.objects.filter(titel='Neu erfasst').count(), 1)
        # Anhang hängt am neuen Beitrag, nicht am Original
        anhang = BPlanBeteiligungBeitragAnhang.objects.get(name='Scan des Briefs')
        self.assertEqual(anhang.beitrag.pk, neu.pk)

    def test_ohne_dateiformular_wird_nur_beitrag_gespeichert(self):
        """
        Was wird geprüft:
            Speichern einer Collection ohne Anhangs-Collection (holders enthält den
            Schlüssel 'attachments' nicht) bei einem FPlan.

        Warum:
            Bei der manuellen Erfassung dürfen Beiträge auch ganz ohne Anlagen
            gespeichert werden; der FPlan-Zweig der Beteiligungszuweisung muss
            dieselbe Arbeit leisten wie der BPlan-Zweig.

        Erwartung:
            Ein neuer FPlan-Beitrag entsteht, die Erfolgs-URL wird zurückgegeben.
        """
        original = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung, titel='FPlan Vorlage',
            beschreibung=TIPTAP_LEER, name='Vorlagen Nutzer',
            email='vorlage@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=HEUTE, typ='1000')
        neu = FPlanBeteiligungBeitrag(
            fplan_beteiligung=self.fplan_beteiligung, titel='FPlan neu',
            beschreibung=TIPTAP_LEER, name='Sachbearbeitung',
            email='sachbearbeitung@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=HEUTE, typ='1000')

        collection = MagicMock()
        collection.valid_holders = {'beitrag': BeitragFormFake(original, neu)}
        response = self._view('fplan').form_collection_valid(collection)

        self.assertEqual(response.status_code, 200)
        neu.refresh_from_db()
        self.assertNotEqual(neu.pk, original.pk)
        self.assertEqual(
            FPlanBeteiligungBeitrag.objects.filter(titel='FPlan neu').count(), 1)


class ToebCreateFormCollectionValidTests(TestCase):
    """form_collection_valid der TÖB-Erfassung (ToebCreateView)."""

    @classmethod
    def setUpTestData(cls):
        cls.behoerde = Orga.objects.create(
            name='Umweltamt', ls='07', ks='316', gs='001')
        cls.reporter = User.objects.create_user(
            username='toeb_schreiber', email='reporter@behoerde.de',
            password='password123')
        cls.editor = AdminOrgaUser.objects.create(
            organization=cls.behoerde, user=cls.reporter, is_toeb_reporter=True)
        cls.toeb = ToebUnit.objects.create(
            organization=cls.behoerde, name='Fachbereich Umwelt',
            theme='NSLP', public=True)
        cls.toeb.editors.add(cls.editor)

        cls.kommune = Orga.objects.create(
            name='Stadt Toeb', ls='07', ks='316', gs='000')
        cls.bplan = BPlan.objects.create(
            name='BPlan Toeb', geltungsbereich=DUMMY_POLYGON)
        cls.bplan.gemeinde.add(cls.kommune)
        cls.beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.bplan, typ='1000', bekanntmachung_datum=HEUTE,
            start_datum=HEUTE, end_datum=HEUTE + datetime.timedelta(days=30),
            allow_online_beitrag=True)

    def test_toeb_beitrag_mit_anhang_und_abgesichertem_eingangsdatum(self):
        """
        Was wird geprüft:
            Das Speichern einer gültigen TÖB-Formular-Collection mit Beitrag und
            einem Anhang.

        Warum:
            Die TÖB-Erfassung setzt E-Mail der einreichenden Person, heutiges
            Eingangsdatum und die TÖB-Stelle selbst — unabhängig davon, was im
            Formular stand. Auch hier ist der JSON-POST ohne Dateien möglich,
            deshalb direkter Aufruf.

        Erwartung:
            Neuer Beitrag mit TÖB-Stelle, E-Mail der Reporterin und heutigem
            Eingangsdatum; der Anhang ist mit dem neuen Beitrag verknüpft; die
            Erfolgs-URL wird zurückgegeben.
        """
        original = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung, titel='TÖB Vorlage',
            beschreibung=TIPTAP_LEER, name='Fremder Absender',
            email='fremd@example.com', generic_id=uuid.uuid4(),
            eingangsdatum=datetime.date(2000, 1, 1), typ='2000')
        original_pk = original.pk
        neu = BPlanBeteiligungBeitrag(
            bplan_beteiligung=self.beteiligung, titel='TÖB Stellungnahme',
            beschreibung=TIPTAP_LEER, name='Fachbereich',
            email='wird@ueberschrieben.de', generic_id=uuid.uuid4(),
            eingangsdatum=datetime.date(2000, 1, 1), typ='2000')
        anhang_neu = BPlanBeteiligungBeitragAnhang(
            name='Gutachten', typ='1000',
            attachment=SimpleUploadedFile(
                'gutachten.pdf', b'%PDF-1.4', content_type='application/pdf'))

        request = RequestFactory().post('/toeb/create/')
        request.user = self.reporter
        view = BeteiligungBeitragToebCreateView()
        view.request = request
        view.plantyp = 'bplan'
        view.model = BPlanBeteiligungBeitrag
        view.model_parent = BPlanBeteiligung
        view.reference_model_name_lower = 'bplan'
        view.toeb_id = self.toeb.pk
        view.beteiligung_pk = self.beteiligung.pk
        view.kwargs = {'beteiligungid': self.beteiligung.pk}
        view.success_url = '/toeb-fertig/'

        collection = MagicMock()
        collection.valid_holders = {
            'beitrag': BeitragFormFake(original, neu),
            'attachments': anhang_holder(anhang_neu),
        }
        response = view.form_collection_valid(collection)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)['success_url'], '/toeb-fertig/')
        original = BPlanBeteiligungBeitrag.objects.get(pk=original_pk)
        self.assertEqual(original.titel, 'TÖB Vorlage')
        neu.refresh_from_db()
        self.assertNotEqual(neu.pk, original_pk)
        self.assertEqual(neu.toeb_id, self.toeb.pk)
        self.assertEqual(neu.email, 'reporter@behoerde.de')
        self.assertEqual(neu.eingangsdatum, HEUTE)
        anhang = BPlanBeteiligungBeitragAnhang.objects.get(name='Gutachten')
        self.assertEqual(anhang.beitrag.pk, neu.pk)
