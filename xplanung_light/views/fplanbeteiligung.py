from xplanung_light.forms import FPlanBeteiligungForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import FPlan, FPlanBeteiligung
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import FPlanBeteiligungTable
from django.db.models import Count
from formset.views import FormViewMixin

class FPlanBeteiligungCreateView(FormViewMixin, XPlanRelationsCreateView):
    """
    Klasse zum Anlegen eines Beteiligungsobjektes für Bebauungspläne. Die Klasse nutzt django-formset um 
    auch Richtext-Beschreibungen zu ermöglichen.
    
    """
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    template_name="xplanung_light/fplanbeteiligung_form.html"
    form_class = FPlanBeteiligungForm
    list_url_name = 'fplanbeteiligung-list'
    extra_context = None

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_success_url(self):
        """
        Wenn das Anlagen des Beteiligungsobjektes erfolgreich war, wird auf die Liste der Beteiligungen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})
        

class FPlanBeteiligungListView(XPlanRelationsListView, SingleTableView):
    """
    CBV für die Liste der Beteiligungen eines BFlans. Hier wird django-tables2 genutzt.

    """
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    table_class = FPlanBeteiligungTable
    template_name = 'xplanung_light/fplanbeteiligung_list.html'
    list_url_name = 'fplanbeteiligung-list'

    def get_queryset(self):
        """
        Überschreiben von get_queryset, um auch die Zahl der Kommentare anzuzeigen.
    
        """
        qs = super().get_queryset()
        qs = qs.annotate(count_comments=Count('comments', distinct=True))
        return qs
    

# In django-formset wird nur ein update view für create, detail und update benötigt
# scheint aber nicht zu funktionieren ...
class FPlanBeteiligungUpdateView(FormViewMixin, XPlanRelationsUpdateView):
    """
    Update View auf Basis von django-formset.

    """
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    template_name="xplanung_light/bplanbeteiligung_form.html"
    form_class = FPlanBeteiligungForm
    list_url_name = 'bplanbeteiligung-list'
    extra_context = None

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_success_url(self):
        """
        Wenn das Anlagen des Beteiligungsobjektes erfolgreich war, wird auf die Liste der Beteiligungen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})


class FPlanBeteiligungDeleteView(XPlanRelationsDeleteView):
    model = FPlanBeteiligung
    reference_model = FPlan
    reference_model_name_lower = 'fplan'
    list_url_name = 'fplanbeteiligung-list'
