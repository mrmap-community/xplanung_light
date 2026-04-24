from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeitragStellungnahme, AdministrativeOrganization#, BPlanBeitragStellungnahmeAnhang
from xplanung_light.models import FPlanBeteiligung, FPlan, FPlanBeitragStellungnahme, ContactOrganization
from xplanung_light.models import FPlanBeteiligungBeitrag, BPlanBeteiligungBeitrag
from xplanung_light.models import ConsentOption
from xplanung_light.forms import BPlanBeitragStellungnahmeForm, FPlanBeitragStellungnahmeForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from django.views.generic import CreateView, ListView, DeleteView, DetailView, UpdateView
from formset.views import FormViewMixin, FormCollectionView, EditCollectionView #, CreateCollectionView
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeitragStellungnahmeTable, FPlanBeitragStellungnahmeTable
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import BPlanBeteiligungCollection, FPlanBeteiligungCollection
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import json
from django.core.exceptions import PermissionDenied
from django.db.models import Subquery, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.core.mail import send_mail, EmailMessage
from django.utils.timezone import datetime
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from formset.views import FormViewMixin


class XPlanBeitragStellungnahmeCreateView(CreateView):
    """
    Anlagen eines BPlanBeitragStellungnahme-Datensatzes über Formular.

    """
    #form_class = BPlanCreateForm


class BeitragStellungnahmeListView(SingleTableView):
    """
    ListView zur Anzeige der BeitragStellungnahme-Records. Hier Die Klasse entscheidet je nach URL, um welchen Plantyp es sich handelt.

    """
    # Default Werte für Initialiisierung - werden durch dispatch Funktion überschrieben
    model = BPlanBeitragStellungnahme
    parent_model = BPlanBeteiligungBeitrag
    reference_model = BPlan
    table_class = BPlanBeitragStellungnahmeTable
    reference_model_name_lower = 'bplan'
    
    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeitragStellungnahme
            self.beteiligung = BPlanBeteiligung
            self.parent_model = BPlanBeteiligungBeitrag
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeitragStellungnahme
            self.beteiligung = FPlanBeteiligung
            self.parent_model = FPlanBeteiligungBeitrag
            self.table_class = FPlanBeitragStellungnahmeTable
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beitragstellungnahme_list.html'
        #TODO: Anpassen für FPlan
        self.beitragid = kwargs.get('beitragid')
        self.beteiligungid = kwargs.get('beteiligungid')
        # Debugausgabe
        #print(f"Typ: {self.plantyp}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        """
        Docstring for get_queryset
        
        :param self: Description
        :param kwargs: Description
        """
        qs = super().get_queryset().annotate(
                    last_changed=Subquery(
                        self.model.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )
                )
        plan = self.reference_model.objects.get(pk=self.kwargs['planid'])
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:   
                        # Zugriff wird erteilt
                        if self.plantyp == 'bplan':                    
                            return qs.filter(beitrag_id=self.kwargs['beitragid']).order_by('-last_changed')
                        if self.plantyp == 'fplan':                    
                            return qs.filter(beitrag_id=self.kwargs['beitragid']).order_by('-last_changed')
            raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
        else:
            if self.plantyp == 'bplan': 
                return qs.filter(beitrag_id=self.kwargs['beitragid']).order_by('-last_changed')
            if self.plantyp == 'fplan': 
                return qs.filter(beitrag_id=self.kwargs['beitragid']).order_by('-last_changed')


    def get_context_data(self, **kwargs):
        """
        Docstring for get_context_data
        
        :param self: Description
        :param kwargs: Description
        """
        #planid = self.kwargs['planid']
        #beteiligungid = self.kwargs['beteiligungid']
        context = super().get_context_data(**kwargs)
        context["plan"] = self.reference_model.objects.get(pk=self.planid)
        context["plantyp"] = self.plantyp
        context["beteiligung"] = self.beteiligung.objects.get(pk=self.beteiligungid)
        context["beitrag"] = self.parent_model.objects.get(pk=self.beitragid)
        # Für oie Legende benötigen wir die TagList
        context['tags_dict'] = self.model.TAGS_DICT
        return context


class XPlanBeitragStellungnahmeCreateView(FormViewMixin, XPlanRelationsCreateView):
    """
    Klasse zum Anlegen einer Stellungnahme zu einem Beteiligungsbeitrag. Die Klasse nutzt django-formset um 
    auch Richtext-Beschreibungen zu ermöglichen. Sie erbt von der Standard XPlanRelations Klasse um die Berechtigungen 
    abzufangen. Die hängen an den Plänen.
    
    """
    # Dummy Werte für Klasse
    model = BPlanBeitragStellungnahme
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    parent_model = BPlanBeteiligungBeitrag
    template_name="xplanung_light/bplanbeitragstellungnahme_form.html"
    form_class = BPlanBeitragStellungnahmeForm
    list_url_name = 'beitragstellungnahme-list'
    extra_context = None

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeitragStellungnahme
            self.parent_model = BPlanBeteiligungBeitrag
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeitragStellungnahme
            self.parent_model = FPlanBeteiligungBeitrag
            self.table_class = FPlanBeitragStellungnahmeTable
            self.form_class = FPlanBeitragStellungnahmeForm
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beitragstellungnahme_form.html'
        #TODO: Anpassen für FPlan
        self.beitragid = kwargs.get('beitragid')
        self.beteiligungid = kwargs.get('beteiligungid')
        # Debugausgabe
        #print(f"Typ: {self.plantyp}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        initial['beitrag'] = self.beitragid
        return initial
    
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
        Wenn das Anlagen des Stellungnahmeobjektes erfolgreich war, wird auf die Liste der Stellungnahmen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid'], 'plantyp': self.plantyp, 'beteiligungid': self.beteiligungid, 'beitragid': self.beitragid})


class XPlanBeitragStellungnahmeUpdateView(FormViewMixin, XPlanRelationsUpdateView):
    """
    Klasse zum Anlegen einer Stellungnahme zu einem Beteiligungsbeitrag. Die Klasse nutzt django-formset um 
    auch Richtext-Beschreibungen zu ermöglichen. Sie erbt von der Standard XPlanRelations Klasse um die Berechtigungen 
    abzufangen. Die hängen an den Plänen.
    
    """
    # Dummy Werte für Klasse
    model = BPlanBeitragStellungnahme
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    parent_model = BPlanBeteiligungBeitrag
    template_name="xplanung_light/beitragstellungnahme_form.html"
    form_class = BPlanBeitragStellungnahmeForm
    list_url_name = 'beitragstellungnahme-list'
    extra_context = None

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeitragStellungnahme
            self.parent_model = BPlanBeteiligungBeitrag
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeitragStellungnahme
            self.parent_model = FPlanBeteiligungBeitrag
            self.table_class = FPlanBeitragStellungnahmeTable
            self.form_class = FPlanBeitragStellungnahmeForm
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beitragstellungnahme_form.html'
        self.beitragid = kwargs.get('beitragid')
        self.beteiligungid = kwargs.get('beteiligungid')
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        initial['beitrag'] = self.beitragid
        return initial
    
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
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid'], 'plantyp': self.plantyp, 'beteiligungid': self.beteiligungid, 'beitragid': self.beitragid})


class XPlanBeitragStellungnahmeDeleteView(XPlanRelationsDeleteView):
    """
    Klasse zum Löschen einer Stellungnhme zu einem Beteiligungsbeitrag
    """
    model = BPlanBeitragStellungnahme
    reference_model = BPlan
    model_name_lower = str(model._meta.model_name).lower()
    success_message = "Stellungnahme wurde gelöscht!"
    template_name = "xplanung_light/beitragstellungnahme_confirm_delete.html"
    list_url_name = "beitragstellungnahme-list"

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeitragStellungnahme
            self.parent_model = BPlanBeteiligungBeitrag
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeitragStellungnahme
            self.parent_model = FPlanBeteiligungBeitrag
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.beitragid = kwargs.get('beitragid')
        self.beteiligungid = kwargs.get('beteiligungid')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #context['beitrag']
        return context
    
    def get_success_url(self):
        """
        Wenn das Anlagen des Beteiligungsobjektes erfolgreich war, wird auf die Liste der Beteiligungen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid'], 'plantyp': self.plantyp, 'beteiligungid': self.beteiligungid, 'beitragid': self.beitragid})
