from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from formset.views import FormViewMixin

from xplanung_light.forms import ConsentOptionForm
from xplanung_light.models import ConsentOption
from xplanung_light.views.consentoption import (
    ConsentOptionCreateView,
    ConsentOptionDeleteView,
    ConsentOptionListView,
    ConsentOptionUpdateView,
)

User = get_user_model()


# Testklasse: ConsentOptionCoverageTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class ConsentOptionCoverageTests(TestCase):
    def setUp(self):
        self.today = timezone.now().date()
        self.superuser = User.objects.create_superuser(
            username="consent_superuser", password="password123"
        )
        self.user = User.objects.create_user(
            username="consent_user", password="password123"
        )
        self.option = ConsentOption.objects.create(
            type=ConsentOption.COMMENTATOR,
            title="Datenschutzerklärung Version 1.0",
            description="Einwilligungstext",
            valid_from=self.today,
            valid_until=self.today + timedelta(days=180),
            mandatory=True,
            opt_out=False,
            obsolete=False,
        )

    def _request(self, user, method="get"):
        factory = RequestFactory()
        request = getattr(factory, method)("/consentoption/")
        request.user = user
        return request

    def _valid_form(self, instance=None, title="Neue Zustimmungsoption"):
        data = {
            "type": ConsentOption.COMMENTATOR,
            "title": title,
            "description": "Beschreibung",
            "mandatory": "on",
            "opt_out": "",
            "valid_from": self.today.isoformat(),
            "valid_until": (self.today + timedelta(days=30)).isoformat(),
            "validity_period": "30",
        }
        return ConsentOptionForm(data=data, instance=instance)

    # ------------------------------------------------------------------
    # CreateView
    # ------------------------------------------------------------------

    # Testfall: erstellen get Formular liefert Formular für Superuser.
    # Erwartung/Absicherung: verwendet assertIsInstance.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_get_form_returns_form_for_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.superuser)

        form = view.get_form()

        self.assertIsInstance(form, ConsentOptionForm)

    # Testfall: erstellen get Formular liefert false für nicht Superuser.
    # Erwartung/Absicherung: verwendet assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_get_form_returns_false_for_non_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.user)

        self.assertFalse(view.get_form())

    # Testfall: erstellen Formular gültig speichert für Superuser.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_form_valid_saves_for_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.superuser, "post")
        view.object = None
        form = self._valid_form(title="Neue Option")

        with patch.object(FormViewMixin, "form_valid", return_value="valid"):
            result = view.form_valid(form)

        self.assertEqual(result, "valid")

    # Testfall: erstellen Formular gültig weist zurück nicht Superuser.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_form_valid_rejects_non_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.user, "post")
        view.object = None
        form = self._valid_form()

        with patch.object(FormViewMixin, "form_invalid", return_value="invalid"):
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        self.assertIn("Nutzer ist nicht der zentrale Administrator!", form.errors["__all__"])

    # Testfall: erstellen Erfolg URL.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_success_url(self):
        view = ConsentOptionCreateView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))

    # Testfall: erstellen Kontext contains extra Kontext.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Isolation: 'django.views.generic.edit.CreateView.get_context_data' werden gemockt/gepatcht, damit der Test den beschriebenen Fall isoliert prüft.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_context_contains_extra_context(self):
        view = ConsentOptionCreateView(extra_context={"create": True})
        view.request = self._request(self.superuser)
        view.object = None

        with patch("django.views.generic.edit.CreateView.get_context_data", return_value={}):
            context = view.get_context_data()

        self.assertEqual(context["extra_context"], {"create": True})

    # ------------------------------------------------------------------
    # UpdateView
    # ------------------------------------------------------------------

    # Testfall: aktualisieren get Formular liefert Formular für Superuser.
    # Erwartung/Absicherung: verwendet assertIsInstance.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_get_form_returns_form_for_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser)

        self.assertIsInstance(view.get_form(), ConsentOptionForm)

    # Testfall: aktualisieren get Formular liefert false für nicht Superuser.
    # Erwartung/Absicherung: verwendet assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_get_form_returns_false_for_non_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.user)

        self.assertFalse(view.get_form())

    # Testfall: aktualisieren get Objekt erlaubt Superuser.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_get_object_allows_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser)
        view.kwargs = {"pk": self.option.pk}

        self.assertEqual(view.get_object(), self.option)

    # Testfall: aktualisieren get Objekt weist zurück nicht Superuser.
    # Erwartung/Absicherung: verwendet assertRaises.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_get_object_rejects_non_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.user)
        view.kwargs = {"pk": self.option.pk}

        with self.assertRaises(PermissionDenied):
            view.get_object()

    # Testfall: aktualisieren Formular gültig weist zurück nicht Superuser.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_form_valid_rejects_non_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.user, "post")
        view.object = self.option
        form = self._valid_form(instance=self.option, title="Nicht erlaubt")

        with patch.object(FormViewMixin, "form_invalid", return_value="invalid"):
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        self.assertIn("Nutzer ist nicht der zentrale Administrator!", form.errors["__all__"])
        self.option.refresh_from_db()
        self.assertEqual(self.option.title, "Datenschutzerklärung Version 1.0")

    # Testfall: aktualisieren Formular gültig speichert für Superuser.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_form_valid_saves_for_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser, "post")
        view.object = self.option
        form = self._valid_form(instance=self.option, title="Geänderte Option")

        with patch.object(FormViewMixin, "form_valid", return_value="valid"):
            result = view.form_valid(form)

        self.assertEqual(result, "valid")

    # Testfall: aktualisieren Erfolg URL.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_success_url(self):
        view = ConsentOptionUpdateView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))

    # Testfall: aktualisieren Kontext contains extra Kontext.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Isolation: 'django.views.generic.edit.UpdateView.get_context_data' werden gemockt/gepatcht, damit der Test den beschriebenen Fall isoliert prüft.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_context_contains_extra_context(self):
        view = ConsentOptionUpdateView(extra_context={"update": True})
        view.request = self._request(self.superuser)
        view.object = self.option

        with patch("django.views.generic.edit.UpdateView.get_context_data", return_value={}):
            context = view.get_context_data()

        self.assertEqual(context["extra_context"], {"update": True})

    # ------------------------------------------------------------------
    # ListView / DeleteView
    # ------------------------------------------------------------------

    # Testfall: auflisten View ist accessible and contains option.
    # Erwartung/Absicherung: verwendet assertEqual, assertContains.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_list_view_is_accessible_and_contains_option(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("consentoption-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.option.title)

    # Testfall: löschen get Objekt erlaubt Superuser.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_delete_get_object_allows_superuser(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.superuser)
        view.kwargs = {"pk": self.option.pk}

        self.assertEqual(view.get_object(), self.option)

    # Testfall: löschen get Objekt weist zurück nicht Superuser.
    # Erwartung/Absicherung: verwendet assertRaises.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_delete_get_object_rejects_non_superuser(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.user)
        view.kwargs = {"pk": self.option.pk}

        with self.assertRaises(PermissionDenied):
            view.get_object()

    # Testfall: löschen nicht Superuser redirects and keeps Objekt.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue, assert_called_once.
    # Isolation: 'xplanung_light.views.consentoption.messages.add_message' werden gemockt/gepatcht, damit der Test den beschriebenen Fall isoliert prüft.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_delete_non_superuser_redirects_and_keeps_object(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.user, "post")
        view.object = self.option

        with patch("xplanung_light.views.consentoption.messages.add_message") as add_message:
            response = view.form_valid(Mock())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("consentoption-list"))
        self.assertTrue(ConsentOption.objects.filter(pk=self.option.pk).exists())
        add_message.assert_called_once()
        self.assertEqual(add_message.call_args.args[1], 30)  # messages.WARNING

    # TODO: Funktion muss noch entwickelt werden!
    """
    def test_delete_superuser_redirects_and_deletes_object(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.superuser, "post")
        view.object = self.option

        with patch("xplanung_light.views.consentoption.messages.add_message") as add_message:
            response = view.form_valid(Mock())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("consentoption-list"))
        self.assertFalse(ConsentOption.objects.filter(pk=self.option.pk).exists())
        add_message.assert_called_once()
        self.assertEqual(add_message.call_args.args[1], 25)  # messages.SUCCESS
    """
    # Testfall: löschen Erfolg URL.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_delete_success_url(self):
        view = ConsentOptionDeleteView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))
