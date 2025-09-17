from xplanung_light.forms import FPlanUvpForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import FPlanUvp, FPlan
from django_tables2 import SingleTableView
from xplanung_light.tables import FPlanUvpTable


"""
Klassen zur Verwaltung von Umweltverträglihkeitsprüfungen
"""
class FPlanUvpCreateView(XPlanRelationsCreateView):
    model = FPlanUvp
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanUvpForm
    template_name = 'xplanung_light/fplan_uvp_form.html'
    list_url_name = 'fplan-uvp-list'


class FPlanUvpListView(XPlanRelationsListView, SingleTableView):
    model = FPlanUvp
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    table_class = FPlanUvpTable
    template_name = 'xplanung_light/fplan_uvp_list.html'
    list_url_name = 'fplan-uvp-list'


class FPlanUvpUpdateView(XPlanRelationsUpdateView):
    model = FPlanUvp
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanUvpForm
    template_name = 'xplanung_light/fplan_uvp_form.html'
    list_url_name = 'fplan-uvp-list'


class FPlanUvpDeleteView(XPlanRelationsDeleteView):
    model = FPlanUvp
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    list_url_name = 'fplan-uvp-list'
