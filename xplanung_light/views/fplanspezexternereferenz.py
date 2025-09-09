from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import FPlanSpezExterneReferenz, FPlan
from django_tables2 import SingleTableView
from xplanung_light.forms import FPlanSpezExterneReferenzForm
from xplanung_light.tables import FPlanSpezExterneReferenzTable


class FPlanSpezExterneReferenzCreateView(XPlanRelationsCreateView):
    model = FPlanSpezExterneReferenz
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanSpezExterneReferenzForm
    list_url_name = 'fplanattachment-list'


class FPlanSpezExterneReferenzListView(XPlanRelationsListView, SingleTableView):
    model = FPlanSpezExterneReferenz
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    table_class = FPlanSpezExterneReferenzTable
    template_name = 'xplanung_light/FPlanattachment_list.html'
    list_url_name = 'fplanattachment-list'


class FPlanSpezExterneReferenzUpdateView(XPlanRelationsUpdateView):
    model = FPlanSpezExterneReferenz
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanSpezExterneReferenzForm
    list_url_name = 'fplanattachment-list'


class FPlanSpezExterneReferenzDeleteView(XPlanRelationsDeleteView):
    model = FPlanSpezExterneReferenz
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    list_url_name = 'fplanattachment-list'
