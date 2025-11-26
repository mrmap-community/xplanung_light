from django.http import HttpResponseRedirect
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, AdministrativeOrganization
from xplanung_light.tables import BeteiligungenTable, BeteiligungenOrgaTable
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.db.models import Count, F, Value
from django_tables2 import SingleTableView
from django.contrib.auth.mixins import LoginRequiredMixin

class BeteiligungenListView(SingleTableView):
    template_name = "xplanung_light/beteiligungen.html"
    #model = BPlan
    #model_name_lower = str(model._meta.model_name).lower()
    table_class = BeteiligungenTable
    #filterset_class = BPlanFilter

    def get_queryset(self):
        if 'pk' in self.kwargs.keys():
            print("Got pk: " + str(self.kwargs['pk']))
        #self.publisher = get_object_or_404(Publisher, name=self.kwargs["publisher"])
        #beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('bplan__name')).annotate(gemeinde=F('bplan__gemeinde__name')).annotate(plantyp=Value('BPlan'))
        #beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('fplan__name')).annotate(gemeinde=F('fplan__gemeinde__name')).annotate(plantyp=Value('FPlan'))    
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('bplan__name')).annotate(plantyp=Value('BPlan'))
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('fplan__name')).annotate(plantyp=Value('FPlan'))
        if not self.request.user.is_superuser and not self.request.user.is_anonymous:
            beteiligungen_bplaene = beteiligungen_bplaene.filter(bplan__gemeinde__organization_users__user=self.request.user, bplan__gemeinde__organization_users__is_admin=True)
            beteiligungen_fplaene = beteiligungen_fplaene.filter(fplan__gemeinde__organization_users__user=self.request.user, fplan__gemeinde__organization_users__is_admin=True)
            
        # union(), intersection(), and difference() return model instances of the type of the first QuerySet even if the arguments are QuerySets of other models. Passing different models works as long as the SELECT list is the same in all QuerySets (at least the types, the names don’t matter as long as the types in the same order).
    
        # https://pythonguides.com/union-operation-on-models-django/
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene)

        for beteiligung in beteiligungen_plaene:
            print(beteiligung.plantyp + " - " + str(beteiligung.bekanntmachung_datum))
            #print(str(beteiligung.bekanntmachung_datum) + " - " + beteiligung.typ)
            #if beteiligung.plantyp == 'BPlan':
            #    print(beteiligung.bplan.gemeinde.all)
            #if beteiligung.plantyp == 'FPlan':
            #    print(beteiligung.fplan.gemeinde.all)    
        return beteiligungen_plaene  
    

class BeteiligungenOrgaListView(BeteiligungenListView):
    template_name = "xplanung_light/organization_beteiligungen.html"
    table_class = BeteiligungenOrgaTable
    # Dynamic Forms with HTMX
    # https://www.youtube.com/watch?v=XdZoYmLkQ4w

    def get_queryset(self):
        if 'pk' in self.kwargs.keys():
            print("Got pk: " + str(self.kwargs['pk']))
        #self.publisher = get_object_or_404(Publisher, name=self.kwargs["publisher"])
        
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(
            bplan__gemeinde__id=self.kwargs['pk']
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('bplan__name'),
            xplan_id=F('bplan__id'),
            plantyp=Value('BPlan')
        )
        #).annotate(
        #    count_comments=Count('comments', distinct=True)
        #)
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(
            fplan__gemeinde__id=self.kwargs['pk']
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('fplan__name'),
            xplan_id=F('fplan__id'),
            plantyp=Value('FPlan')
        )
        #).annotate(
        #    count_comments=Count('comments', distinct=True)
        #)    

        # https://pythonguides.com/union-operation-on-models-django/
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum')

        for beteiligung in beteiligungen_plaene:
            print(beteiligung.plantyp + " - " + str(beteiligung.bekanntmachung_datum))
            #print(str(beteiligung.bekanntmachung_datum) + " - " + beteiligung.typ)
            #if beteiligung.plantyp == 'BPlan':
            #    print(beteiligung.bplan.gemeinde.all)
            #if beteiligung.plantyp == 'FPlan':
            #    print(beteiligung.fplan.gemeinde.all)    
        return beteiligungen_plaene  
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['gemeinde'] = AdministrativeOrganization.objects.get(pk=self.kwargs['pk'])
        return context
    
