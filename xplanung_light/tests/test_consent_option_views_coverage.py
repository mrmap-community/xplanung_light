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

    def test_create_get_form_returns_form_for_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.superuser)

        form = view.get_form()

        self.assertIsInstance(form, ConsentOptionForm)

    def test_create_get_form_returns_false_for_non_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.user)

        self.assertFalse(view.get_form())

    def test_create_form_valid_saves_for_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.superuser, "post")
        view.object = None
        form = self._valid_form(title="Neue Option")

        with patch.object(FormViewMixin, "form_valid", return_value="valid"):
            result = view.form_valid(form)

        self.assertEqual(result, "valid")

    def test_create_form_valid_rejects_non_superuser(self):
        view = ConsentOptionCreateView()
        view.request = self._request(self.user, "post")
        view.object = None
        form = self._valid_form()

        with patch.object(FormViewMixin, "form_invalid", return_value="invalid"):
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        self.assertIn("Nutzer ist nicht der zentrale Administrator!", form.errors["__all__"])

    def test_create_success_url(self):
        view = ConsentOptionCreateView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))

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

    def test_update_get_form_returns_form_for_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser)

        self.assertIsInstance(view.get_form(), ConsentOptionForm)

    def test_update_get_form_returns_false_for_non_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.user)

        self.assertFalse(view.get_form())

    def test_update_get_object_allows_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser)
        view.kwargs = {"pk": self.option.pk}

        self.assertEqual(view.get_object(), self.option)

    def test_update_get_object_rejects_non_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.user)
        view.kwargs = {"pk": self.option.pk}

        with self.assertRaises(PermissionDenied):
            view.get_object()

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

    def test_update_form_valid_saves_for_superuser(self):
        view = ConsentOptionUpdateView()
        view.request = self._request(self.superuser, "post")
        view.object = self.option
        form = self._valid_form(instance=self.option, title="Geänderte Option")

        with patch.object(FormViewMixin, "form_valid", return_value="valid"):
            result = view.form_valid(form)

        self.assertEqual(result, "valid")

    def test_update_success_url(self):
        view = ConsentOptionUpdateView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))

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

    def test_list_view_is_accessible_and_contains_option(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("consentoption-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.option.title)

    def test_delete_get_object_allows_superuser(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.superuser)
        view.kwargs = {"pk": self.option.pk}

        self.assertEqual(view.get_object(), self.option)

    def test_delete_get_object_rejects_non_superuser(self):
        view = ConsentOptionDeleteView()
        view.request = self._request(self.user)
        view.kwargs = {"pk": self.option.pk}

        with self.assertRaises(PermissionDenied):
            view.get_object()

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
    def test_delete_success_url(self):
        view = ConsentOptionDeleteView()
        self.assertEqual(view.get_success_url(), reverse("consentoption-list"))
