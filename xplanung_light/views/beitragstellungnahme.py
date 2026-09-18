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
from xplanung_light.views.user import ExtentUserOrgaInfo
from django.shortcuts import get_object_or_404
from xplanung_light.views.mixins import GemeindeAdminRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin

class BeitragStellungnahmeScopeMixin(GemeindeAdminRequiredMixin): #(GemeindeAdminRequiredMixin):

    def resolve_scope(self):
        self.plan = get_object_or_404(
            self.reference_model,
            pk=self.planid,
        )
        self.check_gemeinde_admin(self.plan)

        if self.plantyp == "bplan":
            self.beteiligung = get_object_or_404(
                BPlanBeteiligung,
                pk=self.beteiligungid,
                bplan=self.plan,
            )
            self.beitrag = get_object_or_404(
                BPlanBeteiligungBeitrag,
                pk=self.beitragid,
                bplan_beteiligung=self.beteiligung,
            )
        elif self.plantyp == "fplan":
            self.beteiligung = get_object_or_404(
                FPlanBeteiligung,
                pk=self.beteiligungid,
                fplan=self.plan,
            )
            self.beitrag = get_object_or_404(
                FPlanBeteiligungBeitrag,
                pk=self.beitragid,
                fplan_beteiligung=self.beteiligung,
            )
        else:
            raise PermissionDenied("Unbekannter Plantyp.")


class XPlanBeitragStellungnahmeCreateView(ExtentUserOrgaInfo, CreateView):
    """
    Anlagen eines BPlanBeitragStellungnahme-Datensatzes über Formular.

    """
    #form_class = BPlanCreateForm


class BeitragStellungnahmeListView(BeitragStellungnahmeScopeMixin, ExtentUserOrgaInfo, LoginRequiredMixin, SingleTableView):
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
        elif self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeitragStellungnahme
            self.beteiligung = FPlanBeteiligung
            self.parent_model = FPlanBeteiligungBeitrag
            self.table_class = FPlanBeitragStellungnahmeTable
            self.reference_model = FPlan
        else:
            raise PermissionDenied("Unbekannter Plantyp.")
        
        self.planid = kwargs['planid']
        self.beitragid = kwargs['beitragid']
        self.beteiligungid = kwargs['beteiligungid']

        self.resolve_scope()
        """
        self.plan = get_object_or_404(
            self.reference_model,
            pk=self.planid,
        )
        self.check_gemeinde_admin(self.plan)
        if self.plantyp == 'bplan':
            self.beteiligung = get_object_or_404(
                BPlanBeteiligung,
                pk=self.beteiligungid,
                bplan=self.plan,
            )
            self.beitrag = get_object_or_404(
                BPlanBeteiligungBeitrag,
                pk=self.beitragid,
                bplan_beteiligung=self.beteiligung,
            )
        else:
            self.beteiligung = get_object_or_404(
                FPlanBeteiligung,
                pk=self.beteiligungid,
                fplan=self.plan,
            )
            self.beitrag = get_object_or_404(
                FPlanBeteiligungBeitrag,
                pk=self.beitragid,
                fplan_beteiligung=self.beteiligung,
            )
        """
        self.template_name = 'xplanung_light/beitragstellungnahme_list.html'
        # Debugausgabe
        #print(f"Typ: {self.plantyp}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        """
        Docstring for get_queryset
        
        :param self: Description
        :param kwargs: Description
        """
        qs = super().get_queryset().filter(beitrag=self.beitrag).annotate(
                    last_changed=Subquery(
                        self.model.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )
                ).order_by('-last_changed')
        return qs

    def get_context_data(self, **kwargs):
        """
        Docstring for get_context_data
        
        :param self: Description
        :param kwargs: Description
        """
        #planid = self.kwargs['planid']
        #beteiligungid = self.kwargs['beteiligungid']
        context = super().get_context_data(**kwargs)
        context["plan"] = self.plan
        context["plantyp"] = self.plantyp
        context["beteiligung"] = self.beteiligung
        context["beitrag"] = self.beitrag
        # Für oie Legende benötigen wir die TagList
        context['tags_dict'] = self.model.TAGS_DICT
        return context


class XPlanBeitragStellungnahmeCreateView(BeitragStellungnahmeScopeMixin, FormViewMixin, XPlanRelationsCreateView):
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

        self.resolve_scope()

        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        initial['beitrag'] = self.beitragid
        return initial
    
    def form_valid(self, form):
        form.instance.beitrag = self.beitrag
        return super().form_valid(form)
    
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


class XPlanBeitragStellungnahmeUpdateView(BeitragStellungnahmeScopeMixin,FormViewMixin, XPlanRelationsUpdateView):
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

        self.resolve_scope()

        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.beitrag = self.beitrag
        return super().form_valid(form)
    
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            pk=self.kwargs["pk"],
            beitrag=self.beitrag,
        )
    """   

    def get_queryset(self):
        return self.model.objects.filter(
            pk=self.kwargs["pk"],
            beitrag=self.beitrag,
        )

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


class XPlanBeitragStellungnahmeDeleteView(BeitragStellungnahmeScopeMixin, XPlanRelationsDeleteView):
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
        self.resolve_scope()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = get_object_or_404(
            self.model,
            pk=self.kwargs["pk"],
            beitrag=self.beitrag,
        )
        self.check_gemeinde_admin(self.plan)
        return obj
    
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
