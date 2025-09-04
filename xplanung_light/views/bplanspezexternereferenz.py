from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import BPlanSpezExterneReferenz, BPlan
from django_tables2 import SingleTableView
from xplanung_light.forms import BPlanSpezExterneReferenzForm
from xplanung_light.tables import BPlanSpezExterneReferenzTable


class BPlanSpezExterneReferenzCreateView(XPlanRelationsCreateView):
    model = BPlanSpezExterneReferenz
    reference_model = BPlan
    form_class = BPlanSpezExterneReferenzForm
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzListView(XPlanRelationsListView, SingleTableView):
    model = BPlanSpezExterneReferenz
    reference_model = BPlan
    table_class = BPlanSpezExterneReferenzTable
    template_name = 'xplanung_light/bplanattachment_list.html'
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzUpdateView(XPlanRelationsUpdateView):
    model = BPlanSpezExterneReferenz
    reference_model = BPlan
    form_class = BPlanSpezExterneReferenzForm
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzDeleteView(XPlanRelationsDeleteView):
    model = BPlanSpezExterneReferenz
    reference_model = BPlan
    list_url_name = 'bplanattachment-list'
