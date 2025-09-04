from xplanung_light.forms import UvpForm
from xplanung_light.views.bplanrelations import BPlanRelationsCreateView, BPlanRelationsListView, BPlanRelationsUpdateView, BPlanRelationsDeleteView
from xplanung_light.models import Uvp
from django_tables2 import SingleTableView
from xplanung_light.tables import UvpTable


"""
Klassen zur Verwaltung von Umweltverträglihkeitsprüfungen
"""
class UvpCreateView(BPlanRelationsCreateView):
    model = Uvp
    form_class = UvpForm
    list_url_name = 'uvp-list'


class UvpListView(BPlanRelationsListView, SingleTableView):
    model = Uvp
    table_class = UvpTable
    template_name = 'xplanung_light/uvp_list.html'
    list_url_name = 'uvp-list'


class UvpUpdateView(BPlanRelationsUpdateView):
    model = Uvp
    form_class = UvpForm
    list_url_name = 'uvp-list'


class UvpDeleteView(BPlanRelationsDeleteView):
    model = Uvp
    list_url_name = 'uvp-list'
