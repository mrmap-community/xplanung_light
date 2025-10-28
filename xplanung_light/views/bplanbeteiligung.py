from xplanung_light.forms import BPlanBeteiligungForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import BPlan, BPlanBeteiligung
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungTable
from django.db.models import Count

"""
View Klassen zur Verwaltung von Beteiligungen
"""
class BPlanBeteiligungCreateView(XPlanRelationsCreateView):
    model = BPlanBeteiligung
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    form_class = BPlanBeteiligungForm
    list_url_name = 'bplanbeteiligung-list'


class BPlanBeteiligungListView(XPlanRelationsListView, SingleTableView):
    model = BPlanBeteiligung
    reference_model = BPlan
    table_class = BPlanBeteiligungTable
    template_name = 'xplanung_light/bplanbeteiligung_list.html'
    list_url_name = 'bplanbeteiligung-list'
    # TODO: Hinzunehmen von BeteiligungBeitrag - zumindest die Zahl der Beiträge

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.annotate(count_comments=Count('comments', distinct=True))
        return qs
    
    

class BPlanBeteiligungUpdateView(XPlanRelationsUpdateView):
    model = BPlanBeteiligung
    reference_model = BPlan
    form_class = BPlanBeteiligungForm
    list_url_name = 'bplanbeteiligung-list'


class BPlanBeteiligungDeleteView(XPlanRelationsDeleteView):
    model = BPlanBeteiligung
    reference_model = BPlan
    list_url_name = 'bplanbeteiligung-list'
