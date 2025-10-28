from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang
from xplanung_light.forms import BPlanBeteiligungBeitragForm
from django.views.generic import CreateView, ListView, DeleteView
from formset.views import FormViewMixin, FormCollectionView, EditCollectionView #, CreateCollectionView
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungBeitragTable
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import BPlanBeteiligungCollection

class XPlanBeteiligungBeitragCreateView(CreateView):
    """
    Anlagen eines BPlanBeteiligungBeitrag-Datensatzes über Formular.
    """
    #form_class = BPlanCreateForm


class BPlanBeteiligungBeitragListView(SingleTableView):

    model = BPlanBeteiligungBeitrag
    reference_model = BPlan
    table_class = BPlanBeteiligungBeitragTable
    reference_model_name_lower = 'bplan'
    
    def get_context_data(self, **kwargs):
        planid = self.kwargs['planid']
        beteiligungid = self.kwargs['beteiligungid']
        context = super().get_context_data(**kwargs)
        context["bplan"] = BPlan.objects.get(pk=planid)
        context["beteiligung"] = BPlanBeteiligung.objects.get(pk=beteiligungid)
        return context


class BPlanBeteiligungBeitragDeleteView(SuccessMessageMixin, DeleteView):
    """
    Löschen eines BeteiligungsBeitrag-Datensatzes.
    """
    model = BPlanBeteiligungBeitrag
    model_name_lower = str(model._meta.model_name).lower()

    success_message = "Beteiligungsbeitrag wurde gelöscht!"

    def form_valid(self, form):
        self.success_url = reverse_lazy('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return super().form_valid(form)


"""
Function based view für das Handling des Formulars, dass sowohl das Beitragsobjekt, als auch die Anhänge editierbar macht 
"""

def bplan_beteiligung_beitrag_create():

    pass

    
"""
View für Abbildung des kombinierten Fomulars über django-formsets EditCollectionView
https://django-formset.fly.dev/model-collections/

"""
class BPlanBeteiligungBeitragCreateView(EditCollectionView):
    model = BPlanBeteiligung
    collection_class = BPlanBeteiligungCollection
    template_name = 'xplanung_light/bplanbeteiligungbeitrag_form.html'
    
    #success_url = reverse_lazy('bplanbeteiligungbeitrag-list')
    #reference_model = BPlan
    #reference_model_name_lower = 'bplan'
    #success_url = reverse_lazy('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
    def get_initial(self):
        print("Initiale Funktion für die django-formset EditCollectionView")
        self.success_url = reverse('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['pk']})
        #context = super().get_context_data()
        #context["bplan"] = BPlan.objects.get(pk=self.kwargs['planid'])
        #context["beteiligung"] = BPlanBeteiligung.objects.get(pk=self.kwargs['pk'])
        return super().get_initial()
    
    """
    def get_success_url(self, **kwargs):
        print("view3 - get success url")
        return reverse('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['pk']})
    
    def form_valid(self, form):
        print("Form was valid ... we need to store the information ...")
        return super().form_valid(form)
    
    """
    def get_context_data(self, **kwargs):
        #planid = self.kwargs['planid']
        #beteiligungid = self.kwargs['beteiligungid']
        context = super().get_context_data(**kwargs)
        context["bplan"] = BPlan.objects.get(pk=self.kwargs['planid'])
        context["beteiligung"] = BPlanBeteiligung.objects.get(pk=self.kwargs['pk'])
        return context
    """
    def form_valid(self, form):
        # check ob alles valide ist!
        beteiligungid = self.kwargs['beteiligungid']
        #print("ID des Plans: " + str(planid) + " - TYP: " + str(self.reference_model) + " name lower: " + self.reference_model_name_lower)
        form.instance.bplan_beteiligung = BPlanBeteiligung.objects.get(pk=beteiligungid)
        self.success_url = reverse_lazy('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return super().form_valid(form)
    """