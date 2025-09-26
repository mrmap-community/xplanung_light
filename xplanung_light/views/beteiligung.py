from django.http import HttpResponseRedirect
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung
from xplanung_light.tables import BeteiligungenTable
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.db.models import Count, F, Value
from django_tables2 import SingleTableView

class BeteiligungenListView(SingleTableView):
    template_name = "xplanung_light/beteiligungen.html"
    #model = BPlan
    #model_name_lower = str(model._meta.model_name).lower()
    table_class = BeteiligungenTable
    #filterset_class = BPlanFilter


    def get_queryset(self):
        #self.publisher = get_object_or_404(Publisher, name=self.kwargs["publisher"])
        #beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('bplan__name')).annotate(gemeinde=F('bplan__gemeinde__name')).annotate(plantyp=Value('BPlan'))
        #beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('fplan__name')).annotate(gemeinde=F('fplan__gemeinde__name')).annotate(plantyp=Value('FPlan'))    
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('bplan__name')).annotate(plantyp=Value('BPlan'))
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('fplan__name')).annotate(plantyp=Value('FPlan'))    

        
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene)
        return beteiligungen_plaene  