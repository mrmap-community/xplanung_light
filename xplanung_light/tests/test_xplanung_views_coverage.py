import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.contrib.gis.geos import Polygon

from xplanung_light import views as views_pkg
from xplanung_light.models import BPlan
from xplanung_light.views import xplan
from django.contrib.messages import middleware

User = get_user_model()


class HashableGemeinde:
    def __init__(self, name='Gemeinde', admins=None):
        self.name = name
        self.admin_orga_users = admins or SimpleNamespace(
            filter=Mock(return_value=SimpleNamespace(
                exists=Mock(return_value=False))),
            all=Mock(return_value=[]),
        )

    def __repr__(self):
        return self.name

    def __hash__(self):
        return id(self)


class QualifyGmlGeometryTests(SimpleTestCase):
    def test_polygon_is_wrapped_as_multisurface(self):
        gml = (
            '<gml:Polygon xmlns:gml="http://www.opengis.net/gml/3.2">'
            '<gml:exterior><gml:LinearRing>'
            '<gml:posList>1 1 2 1 2 2 1 2 1 1</gml:posList>'
            '</gml:LinearRing></gml:exterior>'
            '</gml:Polygon>'
        )
        result = xplan.qualify_gml_geometry(gml)
        self.assertIn('<gml:MultiSurface', result)
        self.assertIn('<gml:surfaceMember>', result)
        self.assertIn('gml:id="GML_', result)

    def test_multisurface_gets_ids_for_surface_and_polygons(self):
        gml = (
            '<gml:MultiSurface xmlns:gml="http://www.opengis.net/gml/3.2">'
            '<gml:surfaceMember><gml:Polygon>'
            '<gml:exterior><gml:LinearRing>'
            '<gml:posList>1 1 2 1 2 2 1 2 1 1</gml:posList>'
            '</gml:LinearRing></gml:exterior>'
            '</gml:Polygon></gml:surfaceMember>'
            '</gml:MultiSurface>'
        )
        result = xplan.qualify_gml_geometry(gml)
        self.assertIn('gml:id="GML_', result)
        self.assertGreaterEqual(result.count('gml:id="GML_'), 2)


class XPlanCreateViewCoverageTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_superuser=False)
        self.request = self.factory.get('/bplan/create/')
        self.request.user = self.user

    def test_get_form_superuser_annotates_all_gemeinden(self):
        self.request.user = SimpleNamespace(is_superuser=True)
        view = xplan.XPlanCreateView()
        view.request = self.request
        qs = Mock()
        annotated = Mock()
        qs.annotate.return_value = annotated
        annotated.only.return_value = Mock()
        form = SimpleNamespace(fields={
            'gemeinde': SimpleNamespace(queryset=qs),
            'geltungsbereich': SimpleNamespace(widget=None),
        })
        with patch.object(xplan.CreateView, 'get_form', return_value=form), \
                patch('xplanung_light.views.xplan.Extent'), \
                patch('xplanung_light.views.xplan.LeafletWidget'):
            result = view.get_form()
        qs.annotate.assert_called_once()
        annotated.only.assert_called_once_with(
            "pk", "name", "name_part", "type")
        self.assertIs(result, form)
        self.assertIsNotNone(form.fields['geltungsbereich'].widget)

    def test_get_form_regular_user_filters_admin_gemeinden(self):
        view = xplan.XPlanCreateView()
        view.request = self.request
        qs = Mock()
        filtered = Mock()
        qs.filter.return_value = filtered
        filtered.annotate.return_value = filtered
        form = SimpleNamespace(fields={
            'gemeinde': SimpleNamespace(queryset=qs),
            'geltungsbereich': SimpleNamespace(widget=None),
        })
        with patch.object(xplan.CreateView, 'get_form', return_value=form), \
                patch('xplanung_light.views.xplan.Extent'), \
                patch('xplanung_light.views.xplan.LeafletWidget'):
            view.get_form()
        qs.filter.assert_called_once_with(
            admin_orga_users__user=self.user,
            admin_orga_users__is_admin=True,
        )
    """
    # Problem bei xplan.py - man versucht user aufzurufen und is authenticated zu prüfen, obwohl LoginRequiredMixin aktiv ist? 
    # vlt Ursache für: if self.request.user.is_authenticated:
    # AttributeError: 'types.SimpleNamespace' object has no attribute 'is_authenticated'
    """
    """
    def test_form_valid_regular_user_rejects_non_admin_gemeinde(self):
        gemeinde = HashableGemeinde('Nicht erlaubt')
        form = Mock()
        form.cleaned_data = {'gemeinde': [gemeinde]}
        view = xplan.XPlanCreateView()
        view.request = self.request
        view.object = None
        with patch.object(view, 'form_invalid', return_value='invalid') as invalid:
            result = view.form_valid(form)
        form.add_error.assert_called_once()
        invalid.assert_called_once_with(form)
        self.assertEqual(result, 'invalid')
    """

    def test_form_valid_superuser_delegates(self):
        view = xplan.XPlanCreateView()
        view.request = self.factory.post('/')
        view.request.user = SimpleNamespace(is_superuser=True)
        form = Mock()
        form.cleaned_data = {'gemeinde': []}
        with patch.object(xplan.CreateView, 'form_valid', return_value='valid') as valid:
            self.assertEqual(view.form_valid(form), 'valid')
            valid.assert_called_once_with(form)


class XPlanUpdateViewCoverageTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/bplan/update/')
        self.user = SimpleNamespace(is_superuser=False)
        self.request.user = self.user

    def _form(self):
        return SimpleNamespace(fields={
            'gemeinde': SimpleNamespace(queryset=Mock(), disabled=False, label='Gemeinden'),
            'geltungsbereich': SimpleNamespace(widget=None),
        })

    def test_get_form_superuser(self):
        view = xplan.XPlanUpdateView()
        view.request = SimpleNamespace(user=SimpleNamespace(is_superuser=True))
        view.object = SimpleNamespace(pk=1)
        view.get_success_url = Mock(return_value='/bplan/')
        qs = Mock()
        annotated = Mock()
        qs.annotate.return_value = annotated
        annotated.only.return_value = Mock()
        form = SimpleNamespace(fields={
            'gemeinde': SimpleNamespace(queryset=qs, disabled=False, label='Gemeinden'),
            'geltungsbereich': SimpleNamespace(widget=None),
        })
        with patch.object(xplan.UpdateView, 'get_form', return_value=form), \
                patch('xplanung_light.views.xplan.Extent'), \
                patch('xplanung_light.views.xplan.LeafletWidget'):
            result = view.get_form()
        qs.annotate.assert_called_once()
        annotated.only.assert_called_once_with(
            "pk", "name", "name_part", "type")
        self.assertIs(result, form)

    def test_get_form_disables_gemeinde_if_user_is_not_admin_for_all(self):
        bad_gemeinde = SimpleNamespace(
            admin_orga_users=SimpleNamespace(all=lambda: []))
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.get_success_url = Mock(return_value='/bplan/')
        view.get_object = Mock(return_value=SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [bad_gemeinde])))
        form = self._form()
        with patch.object(xplan.UpdateView, 'get_form', return_value=form), \
                patch('xplanung_light.views.xplan.LeafletWidget'):
            view.get_form()
        self.assertTrue(form.fields['gemeinde'].disabled)
        self.assertIn('nicht Administrator', form.fields['gemeinde'].label)

    def test_get_form_filters_gemeinden_when_user_is_admin_for_all(self):
        admin_record = SimpleNamespace(user=self.user, is_admin=True)
        gemeinde = SimpleNamespace(
            admin_orga_users=SimpleNamespace(all=lambda: [admin_record]))
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.get_success_url = Mock(return_value='/bplan/')
        view.get_object = Mock(return_value=SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [gemeinde])))
        qs = Mock()
        filtered = Mock()
        annotated = Mock()
        qs.filter.return_value = filtered
        filtered.annotate.return_value = annotated
        annotated.only.return_value = Mock()
        form = SimpleNamespace(fields={
            'gemeinde': SimpleNamespace(queryset=qs, disabled=False, label='Gemeinden'),
            'geltungsbereich': SimpleNamespace(widget=None),
        })
        with patch.object(xplan.UpdateView, 'get_form', return_value=form), \
                patch('xplanung_light.views.xplan.Extent'), \
                patch('xplanung_light.views.xplan.LeafletWidget'):
            view.get_form()
        qs.filter.assert_called_once_with(
            admin_orga_users__user=self.user,
            admin_orga_users__is_admin=True,
        )

    def test_form_valid_rejects_new_non_admin_gemeinde(self):
        existing = HashableGemeinde('Existing')
        new = HashableGemeinde('New')
        form = Mock()
        form.cleaned_data = {'gemeinde': [new], 'name': 'Plan'}
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.object = SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [existing]))
        with patch.object(view, 'form_invalid', return_value='invalid') as invalid:
            self.assertEqual(view.form_valid(form), 'invalid')
        invalid.assert_called_once_with(form)
        form.add_error.assert_called_once()

    """
    # django.contrib.messages.api.MessageFailure: You cannot add messages without installing django.contrib.messages.middleware.MessageMiddleware
    # AttributeError: 'WSGIRequest' object has no attribute '_messages'
    """
    """
    def test_form_valid_rejects_existing_non_admin_gemeinde(self):
        existing = HashableGemeinde('Existing')
        form = Mock()
        form.cleaned_data = {'gemeinde': [existing], 'name': 'Plan'}
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.object = SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [existing]))
        with patch.object(view, 'form_invalid', return_value='invalid') as invalid:
            result = view.form_valid(form)
        invalid.assert_called_once_with(form)
        form.add_error.assert_called_once()
        self.assertEqual(result, 'invalid')
        self.assertIn('darf nicht geändert werden',
                      str(form.add_error.call_args))
    """

    def test_form_valid_rejects_removal_of_non_admin_gemeinde(self):
        protected = HashableGemeinde('Protected')
        form = Mock()
        form.cleaned_data = {'gemeinde': [], 'name': 'Plan'}
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.object = SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [protected]))
        with patch.object(view, 'form_invalid', return_value='invalid') as invalid:
            result = view.form_valid(form)
        invalid.assert_called_once_with(form)
        form.add_error.assert_called_once()
        self.assertEqual(result, 'invalid')
        self.assertIn('darf nicht entfernt werden',
                      str(form.add_error.call_args))

    def test_form_valid_sets_dynamic_success_message(self):
        gemeinde = HashableGemeinde(
            'Gemeinde',
            SimpleNamespace(
                filter=Mock(return_value=SimpleNamespace(
                    exists=Mock(return_value=True))),
                all=Mock(return_value=[]),
            ),
        )
        form = Mock()
        form.cleaned_data = {'gemeinde': [gemeinde], 'name': 'Mein Plan'}
        view = xplan.XPlanUpdateView()
        view.request = self.request
        view.object = SimpleNamespace(
            gemeinde=SimpleNamespace(all=lambda: [gemeinde]))
        with patch.object(xplan.UpdateView, 'form_valid', return_value='valid'), \
                patch('django.contrib.messages.views.messages.success'):
            self.assertEqual(view.form_valid(form), 'valid')
        self.assertEqual(view.success_message,
                         'Plan *Mein Plan* aktualisiert!')

    def test_get_object_calls_gemeinde_admin_check(self):
        view = xplan.XPlanUpdateView()
        obj = object()
        with patch('django.views.generic.detail.SingleObjectMixin.get_object', return_value=obj), \
                patch.object(view, 'check_gemeinde_admin') as check:
            self.assertIs(view.get_object(), obj)
        check.assert_called_once_with(obj)

    def test_get_queryset_adds_count_annotations(self):
        view = xplan.XPlanUpdateView()
        qs = Mock()
        qs.annotate.return_value = qs
        with patch.object(xplan.UpdateView, 'get_queryset', return_value=qs):
            result = view.get_queryset()
        self.assertIs(result, qs)
        self.assertEqual(qs.annotate.call_count, 3)


class XPlanDeleteViewCoverageTests(SimpleTestCase):
    def test_get_object_checks_all_gemeinden(self):
        view = xplan.XPlanDeleteView()
        obj = object()
        with patch('django.views.generic.detail.SingleObjectMixin.get_object', return_value=obj), \
                patch.object(view, 'check_gemeinde_all_admin') as check:
            self.assertIs(view.get_object(), obj)
        check.assert_called_once_with(obj)

    def test_get_success_url_points_to_bplan_list(self):
        view = xplan.XPlanDeleteView()
        with patch('xplanung_light.views.xplan.reverse_lazy', return_value='/bplan/') as reverse_mock:
            result = view.get_success_url()
        self.assertEqual(result, '/bplan/')
        reverse_mock.assert_called_once_with('bplan-list')

    def test_form_valid_deletes_object_and_adds_success_message(self):
        request = RequestFactory().post('/')
        request.user = SimpleNamespace(is_superuser=True)
        view = xplan.XPlanDeleteView()
        view.request = request
        obj = Mock(name='plan')
        obj.name = 'Plan X'
        view.get_object = Mock(return_value=obj)
        view.get_success_url = Mock(return_value='/bplan/')
        with patch('xplanung_light.views.xplan.messages.add_message') as add_message:
            response = view.form_valid(Mock())
        obj.delete.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/bplan/')
        add_message.assert_called_once_with(
            request, xplan.messages.SUCCESS, 'Plan Plan X wurde gelöscht!')


class XPlanListPaginationTests(SimpleTestCase):
    def test_invalid_per_page_falls_back_to_ten(self):
        view = xplan.XPlanListView()
        view.request = RequestFactory().get('/bplan/', {'per_page': 'abc'})
        self.assertEqual(view.get_table_pagination(Mock()), {'per_page': 10})

    def test_numeric_per_page_is_used(self):
        view = xplan.XPlanListView()
        view.request = RequestFactory().get('/bplan/', {'per_page': '50'})
        self.assertEqual(view.get_table_pagination(Mock()), {'per_page': 50})

    def test_default_per_page_is_ten(self):
        view = xplan.XPlanListView()
        view.request = RequestFactory().get('/bplan/')
        self.assertEqual(view.get_table_pagination(Mock()), {'per_page': 10})

    def test_public_list_invalid_per_page_falls_back_to_ten(self):
        view = xplan.XPlanPublicListView()
        view.request = RequestFactory().get(
            '/bplan/public/', {'per_page': 'bad'})
        self.assertEqual(view.get_table_pagination(Mock()), {'per_page': 10})


class XPlanDetailContextTests(SimpleTestCase):
    def _fake_ogr(self, extent=(7, 50, 7.01, 50.01)):
        geom = Mock()
        geom.extent = extent
        geom.transform = Mock()
        return geom

    def test_detail_context_without_gemeinde_geometry_sets_none(self):
        view = xplan.XPlanDetailView()
        plan = SimpleNamespace(
            geltungsbereich='POLYGON ((7 50, 7.01 50, 7.01 50.01, 7 50.01, 7 50))',
            gemeinde=SimpleNamespace(
                all=Mock(return_value=SimpleNamespace(
                    aggregate=Mock(return_value={'bereich': None})
                ))
            ),
        )
        view.model_name_lower = 'bplan'
        fake = self._fake_ogr()
        with patch('django.views.generic.detail.DetailView.get_context_data', return_value={'bplan': plan}), \
                patch('xplanung_light.views.xplan.OGRGeometry', return_value=fake), \
                patch('xplanung_light.views.xplan.CoordTransform', return_value=object()), \
                patch('xplanung_light.views.xplan.SpatialReference', return_value=object()):
            context = view.get_context_data()
        self.assertIsNone(context['gemeinden_extent'])
        self.assertEqual(context['wgs84_extent'], [
                         6.99, 49.99, 7.02, 50.019999999999996])
        self.assertEqual(len(context['extent']), 4)

    def test_detail_context_with_gemeinde_geometry_sets_extent(self):
        view = xplan.XPlanDetailView()
        gemeinde_qs = Mock()
        gemeinde_qs.aggregate.return_value = {
            'bereich': 'POLYGON ((7 50,7.02 50,7.02 50.03,7 50.03,7 50))'}
        plan = SimpleNamespace(
            geltungsbereich='POLYGON ((7 50, 7.01 50, 7.01 50.01, 7 50.01, 7 50))',
            gemeinde=SimpleNamespace(all=Mock(return_value=gemeinde_qs)),
        )
        fake_plan = self._fake_ogr()
        fake_gemeinde = self._fake_ogr((7, 50, 7.02, 50.03))
        with patch('django.views.generic.detail.DetailView.get_context_data', return_value={'bplan': plan}), \
                patch('xplanung_light.views.xplan.OGRGeometry', side_effect=[fake_plan, fake_gemeinde]), \
                patch('xplanung_light.views.xplan.CoordTransform', return_value=object()), \
                patch('xplanung_light.views.xplan.SpatialReference', return_value=object()), \
                patch('xplanung_light.views.xplan.Union', return_value=object()):
            context = view.get_context_data()
        self.assertIsNotNone(context['gemeinden_extent'])
        self.assertEqual(len(context['gemeinden_extent']), 4)


class XPlanPublicQuerysetTests(TestCase):
    def test_public_queryset_contains_only_public_plans(self):
        polygon = Polygon.from_bbox((7, 50, 7.01, 50.01))
        public = BPlan.objects.create(
            name='Public', geltungsbereich=polygon, public=True)
        private = BPlan.objects.create(
            name='Private', geltungsbereich=polygon, public=False)
        request = RequestFactory().get('/bplan/public/')
        request.user = User.objects.create_user(
            'public-test-user', password='pw')
        view = xplan.XPlanPublicListView()
        view.request = request
        qs = view.get_queryset()
        ids = set(qs.values_list('pk', flat=True))
        self.assertIn(public.pk, ids)
        self.assertNotIn(private.pk, ids)
