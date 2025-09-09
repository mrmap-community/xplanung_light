from xplanung_light.forms import FPlanBeteiligungForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import FPlan, FPlanBeteiligung
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import FPlanBeteiligungTable


"""
View Klassen zur Verwaltung von Beteiligungen
"""
class FPlanBeteiligungCreateView(XPlanRelationsCreateView):
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanBeteiligungForm
    list_url_name = 'fplanbeteiligung-list'


class FPlanBeteiligungListView(XPlanRelationsListView, SingleTableView):
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    table_class = FPlanBeteiligungTable
    template_name = 'xplanung_light/fplanbeteiligung_list.html'
    list_url_name = 'fplanbeteiligung-list'


class FPlanBeteiligungUpdateView(XPlanRelationsUpdateView):
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    form_class = FPlanBeteiligungForm
    list_url_name = 'fplanbeteiligung-list'


class FPlanBeteiligungDeleteView(XPlanRelationsDeleteView):
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    list_url_name = 'fplanbeteiligung-list'
