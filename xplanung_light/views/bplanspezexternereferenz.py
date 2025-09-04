from xplanung_light.views.bplanrelations import BPlanRelationsCreateView, BPlanRelationsListView, BPlanRelationsUpdateView, BPlanRelationsDeleteView
from xplanung_light.models import BPlanSpezExterneReferenz
from django_tables2 import SingleTableView
from xplanung_light.forms import BPlanSpezExterneReferenzForm
from xplanung_light.tables import BPlanSpezExterneReferenzTable


class BPlanSpezExterneReferenzCreateView(BPlanRelationsCreateView):
    model = BPlanSpezExterneReferenz
    form_class = BPlanSpezExterneReferenzForm
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzListView(BPlanRelationsListView, SingleTableView):
    model = BPlanSpezExterneReferenz
    table_class = BPlanSpezExterneReferenzTable
    template_name = 'xplanung_light/bplanattachment_list.html'
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzUpdateView(BPlanRelationsUpdateView):
    model = BPlanSpezExterneReferenz
    form_class = BPlanSpezExterneReferenzForm
    list_url_name = 'bplanattachment-list'


class BPlanSpezExterneReferenzDeleteView(BPlanRelationsDeleteView):
    model = BPlanSpezExterneReferenz
    list_url_name = 'bplanattachment-list'
