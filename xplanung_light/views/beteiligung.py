from django.http import HttpResponseRedirect
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, AdministrativeOrganization
from xplanung_light.tables import BeteiligungenTable, BeteiligungenOrgaTable
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.db.models import Count, F, Value, OuterRef, Subquery
from django.db.models.functions import Concat
from django_tables2 import SingleTableView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import serializers
from django.db.models import JSONField, CharField, Func, Aggregate
import json
#from django.db.models.aggregates import Aggregate

# https://stackoverflow.com/questions/74111981/django-aggregate-into-array
# TODO: for sqlite - für Postgres gibt es eigene Aggregatfunktionen!
class JsonGroupArray(Aggregate):
    function = 'JSON_GROUP_ARRAY'
    output_field = JSONField()
    template = '%(function)s(%(distinct)s%(expressions)s)'

"""
Nach KI-Recherche - Abstraktion für postgresql und sqlite
Eigentlich wird JSONAgg vorgeschlagen - ob JSONBAgg klappt müssen wir noch ausprobieren

"""
from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models.functions import JSONObject
from django.db import connection


class SQLiteJSONGroupArray(Aggregate):
    function = "JSON_GROUP_ARRAY"
    output_field = JSONField()


class SQLiteJSONObject(Func):
    function = "json_object"


def sqlite_organization_aggregation(plantyp='bplan'):
    return SQLiteJSONGroupArray(
        SQLiteJSONObject(
            Value("id"), plantyp + "__gemeinde__id",
            Value("name"), plantyp + "__gemeinde__name",
        )
    )   

def postgres_organization_aggregation(plantyp='bplan'):
    return JSONBAgg(
        JSONObject(
            id = plantyp + "__gemeinde__id",
            name = plantyp + "__gemeinde__name",
        )
    )

def organization_json_aggregation(plantyp='bplan'):
    if connection.vendor == "postgresql":

        return postgres_organization_aggregation(plantyp)

    if connection.vendor == "sqlite":
        result = sqlite_organization_aggregation(plantyp)
        return result

    raise NotImplementedError


class BeteiligungenListView(SingleTableView):
    """
    Klasse zur Anzeige der laufenden BPlan- und FPlan-Verfahren einer Gebietskörperschaft.

    """
    template_name = "xplanung_light/beteiligungen.html"
    table_class = BeteiligungenTable

    def get_queryset(self):
        """
        Überschreiben von get_queryset um ein union verschiedener Modelle zu ermöglichen.
        
        :param self: Description
        """
        #if 'pk' in self.kwargs.keys():
        #    print("Got pk: " + str(self.kwargs['pk']))

        # Info: https://forum.djangoproject.com/t/group-concat-in-orm/21149
        # https://stackoverflow.com/questions/73668842/django-with-mysql-subquery-returns-more-than-1-row
        # https://djangosnippets.org/snippets/10860/
        #gemeinden_bplaene = AdministrativeOrganization.objects.filter(bplan__id=OuterRef("bplan__id"))
        #beteiligungen_bplaene_1 = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=serializers.serialize('json', Subquery(gemeinden_bplaene)))
        #beteiligungen_bplaene_1 = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=Subquery(gemeinden_bplaene))

        #beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=JsonGroupArray('bplan__gemeinde__name'))
        beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), bplan__public=True).distinct().annotate(xplan_name=F('bplan__name'), plantyp=Value('BPlan'), gemeinden=organization_json_aggregation())
        #beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), fplan__public=True).distinct().annotate(xplan_name=F('fplan__name'), plantyp=Value('FPlan'), gemeinden=JsonGroupArray('fplan__gemeinde__name'))
        beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now(), fplan__public=True).distinct().annotate(xplan_name=F('fplan__name'), plantyp=Value('FPlan'), gemeinden=organization_json_aggregation(plantyp='fplan'))

        if not self.request.user.is_superuser and not self.request.user.is_anonymous:
            beteiligungen_bplaene = beteiligungen_bplaene.filter(bplan__gemeinde__organization_users__user=self.request.user, bplan__gemeinde__organization_users__is_admin=True)
            beteiligungen_fplaene = beteiligungen_fplaene.filter(fplan__gemeinde__organization_users__user=self.request.user, fplan__gemeinde__organization_users__is_admin=True)
        # Info:
        # union(), intersection(), and difference() return model instances of the type of the first QuerySet even if the arguments are QuerySets of other models. Passing different models works as long as the SELECT list is the same in all QuerySets (at least the types, the names don’t matter as long as the types in the same order).   
        # https://pythonguides.com/union-operation-on-models-django/
        beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum')
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
    
