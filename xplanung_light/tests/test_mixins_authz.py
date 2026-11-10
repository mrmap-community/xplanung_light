"""
Unit-Tests der Zugriffs-Mixins aus views/mixins.py per Direktaufruf.

Die gemischten Pfade (nicht angemeldet, Plan ohne Gemeinde) sind über
echte Routen schwer erreichbar, weil vorgeschaltete Mixins (LoginRequired)
oder URL-Regexe vorher abfangen. Für reine Prüfmethoden wie
check_gemeinde_admin() ist der Direktaufruf mit gebauter View-Instanz die
angemessene Testform - die Authentizität der Prüfung bleibt gewahrt, weil
die originale Methode auf einer echten Mixin-Instanz läuft.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.views.generic import DetailView

from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlan,
)
from xplanung_light.views.mixins import (
    GemeindeAdminRequiredMixin,
    PublicOrGemeindeAdminRequiredMixin,
)

User = get_user_model()


class _NurPruefung(GemeindeAdminRequiredMixin):
    """Minimaler Träger für die reinen Prüfmethoden des Mixins."""


class _DetailMitOeffentlichemZugriff(PublicOrGemeindeAdminRequiredMixin, DetailView):
    """DetailView-Träger, um get_object() des Mixins direkt aufrufen zu können."""

    model = BPlan


class GemeindeAdminRequiredMixinTests(TestCase):
    """check_gemeinde_admin und check_gemeinde_all_admin."""

    def setUp(self):
        polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.kommune = AdministrativeOrganization.objects.create(
            name="Stadt Schilda", ls="07", ks="111", gs="000")
        self.bplan = BPlan.objects.create(name="BPlan Test", geltungsbereich=polygon)
        self.bplan.gemeinde.add(self.kommune)
        self.bplan_ohne = BPlan.objects.create(name="BPlan ohne Gemeinde",
                                               geltungsbereich=polygon)
        self.einfacher = User.objects.create_user(
            username="MixinMax", password="password123")

    def _request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_check_gemeinde_admin_denies_anonymous(self):
        """
        Was wird geprüft:
            check_gemeinde_admin mit einem anonymen request.user.

        Warum:
            Views ohne vorgeschaltetes LoginRequiredMixin sollen auch ohne
            Anmeldung sauber mit PermissionDenied (und nicht mit
            AttributeError auf is_superuser) abbrechen.

        Erwartung:
            PermissionDenied mit Hinweis auf fehlende Anmeldung.
        """
        pruefung = _NurPruefung()
        pruefung.request = self._request(AnonymousUser())
        with self.assertRaises(PermissionDenied) as raised:
            pruefung.check_gemeinde_admin(self.bplan)
        self.assertIn("nicht angemeldet", str(raised.exception))

    def test_check_gemeinde_all_admin_denies_anonymous(self):
        """
        Was wird geprüft:
            check_gemeinde_all_admin mit einem anonymen request.user.

        Warum:
            Auch die verschärfte All-Admin-Prüfung muss anonyme Anfragen als
            Erstes abfangen, bevor Gemeinde-Zählungen starten.

        Erwartung:
            PermissionDenied mit Hinweis auf fehlende Anmeldung.
        """
        pruefung = _NurPruefung()
        pruefung.request = self._request(AnonymousUser())
        with self.assertRaises(PermissionDenied) as raised:
            pruefung.check_gemeinde_all_admin(self.bplan)
        self.assertIn("nicht angemeldet", str(raised.exception))

    def test_check_gemeinde_all_admin_denies_plan_without_gemeinde(self):
        """
        Was wird geprüft:
            check_gemeinde_all_admin für einen angemeldeten, einfachen Nutzer
            auf einen Plan ohne jegliche zugewiesene Gemeinde.

        Warum:
            all([]) über eine leere Gemeinde-Menge wäre automatisch wahr -
            der Filter muss leere Mengen explizit ablehnen, sonst dürfte jeder
            einen Plan ohne Gemeindezuordnung löschen.

        Erwartung:
            PermissionDenied mit Hinweis auf fehlende Gemeindezuweisung.
        """
        pruefung = _NurPruefung()
        pruefung.request = self._request(self.einfacher)
        with self.assertRaises(PermissionDenied) as raised:
            pruefung.check_gemeinde_all_admin(self.bplan_ohne)
        self.assertIn("keine Gemeinden", str(raised.exception))


class PublicOrGemeindeAdminRequiredMixinTests(TestCase):
    """Direktaufruf von get_object() des öffentlich/admin-Mixins."""

    def setUp(self):
        polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.bplan = BPlan.objects.create(
            name="Verborgener BPlan", geltungsbereich=polygon, public=False)

    def test_get_object_directly_denies_anonymous_for_private_plan(self):
        """
        Was wird geprüft:
            Der direkte Aufruf von get_object() ohne vorheriges dispatch()
            durch einen anonymen Nutzer auf einen nicht öffentlichen Plan.

        Warum:
            Normal fängt dispatch() den anonymen Fall mit 401 ab; get_object()
            muss aber auch bei Direktaufruf (z. B. durch fremde Aufrufer)
            dicht sein und darf kein Objekt ausliefern.

        Erwartung:
            PermissionDenied statt eines Planobjekts.
        """
        view = _DetailMitOeffentlichemZugriff()
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        view.setup(request, pk=self.bplan.id)
        with self.assertRaises(PermissionDenied):
            view.get_object()

    def test_get_object_directly_allows_anonymous_for_public_plan(self):
        """
        Was wird geprüft:
            Derselbe Direktaufruf auf einen öffentlichen Plan.

        Warum:
            Öffentliche Pläne sind bewusst anonym lesbar - die Sperre darf
            nur nicht öffentliche Pläne treffen.

        Erwartung:
            get_object() liefert das Planobjekt zurück.
        """
        self.bplan.public = True
        self.bplan.save()
        view = _DetailMitOeffentlichemZugriff()
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        view.setup(request, pk=self.bplan.id)
        self.assertEqual(view.get_object(), self.bplan)
