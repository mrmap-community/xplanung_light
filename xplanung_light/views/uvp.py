from xplanung_light.forms import UvpForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import Uvp, BPlan
from django_tables2 import SingleTableView
from xplanung_light.tables import UvpTable


"""
Klassen zur Verwaltung von Umweltverträglihkeitsprüfungen
"""
class UvpCreateView(XPlanRelationsCreateView):
    model = Uvp
    reference_model = BPlan
    form_class = UvpForm
    list_url_name = 'uvp-list'


class UvpListView(XPlanRelationsListView, SingleTableView):
    model = Uvp
    reference_model = BPlan
    table_class = UvpTable
    template_name = 'xplanung_light/uvp_list.html'
    list_url_name = 'uvp-list'


class UvpUpdateView(XPlanRelationsUpdateView):
    model = Uvp
    reference_model = BPlan
    form_class = UvpForm
    list_url_name = 'uvp-list'


class UvpDeleteView(XPlanRelationsDeleteView):
    model = Uvp
    reference_model = BPlan
    list_url_name = 'uvp-list'
