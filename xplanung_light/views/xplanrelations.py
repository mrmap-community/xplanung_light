from django.views.generic import (CreateView, UpdateView, DeleteView)
from xplanung_light.models import BPlan
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from django.contrib.auth.mixins import LoginRequiredMixin
from xplanung_light.views.user import ExtentUserOrgaInfo
from xplanung_light.views.mixins import PlantypMixin, GemeindeAdminRequiredMixin
from django.shortcuts import get_object_or_404

"""
Generische Klassen zur Verwaltung von Relationen zu XPlänen
"""
class XPlanRelationsCreateView(GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, CreateView):
    reference_model = BPlan
    list_url_name = 'test'
    reference_model_name_lower = str(reference_model._meta.model_name).lower()

    def dispatch(self, request, *args, **kwargs):
        self.reference_object = get_object_or_404(
            self.reference_model,
            pk=self.kwargs["planid"],
        )
        self.check_gemeinde_admin(self.reference_object)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        planid = self.kwargs['planid']
        context = super().get_context_data(**kwargs)
        plan = self.reference_model.objects.get(pk=planid)
        # Die Berechtigungsprüfung läuft vollständig über dispatch()
        # (check_gemeinde_admin), hier wird nur der Plan fürs Template gesetzt.
        context[self.reference_model_name_lower] = plan
        return context

    # reduce choices for invoice to own invoices    
    # https://stackoverflow.com/questions/48089590/limiting-choices-in-foreign-key-dropdown-in-django-using-generic-views-createv
    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        #https://django-bootstrap-datepicker-plus.readthedocs.io/en/latest/Walkthrough.html
        #form.fields['issue_date'].widget = DatePickerInput()
        #form.fields['due_date'].widget = DatePickerInput()
        #form.fields['actual_delivery_date'].widget = DatePickerInput()
        return form
    
    def get_form_kwargs(self):
        form = super().get_form_kwargs()
        planid = self.kwargs['planid']
        form['initial'].update({self.reference_model_name_lower: self.reference_model.objects.get(pk=planid)})
        return form

    def form_valid(self, form):
        #planid = self.kwargs['planid']
        #print("ID des Plans: " + str(planid) + " - TYP: " + str(self.reference_model) + " name lower: " + self.reference_model_name_lower)
        # hier wird das Objekt aus der dispatch Funktion genutzt - keine doppelten Abfragen
        if self.reference_model_name_lower == 'bplan':
            form.instance.bplan = self.reference_object
        if self.reference_model_name_lower == 'fplan':
            form.instance.fplan = self.reference_object 
        #print(form.instance)
        # TODO: check ob der Extent des Rasterbilds innerhalb der Abgrenzung der AdministrativeUnit liegt ...  
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})   
    

class XPlanRelationsListView(GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, SingleTableView):
    reference_model = BPlan
    list_url_name = 'test'
    reference_model_name_lower = str(reference_model._meta.model_name).lower()
    #model = BPlanBeteiligung
    #table_class = BPlanBeteiligungTable
    #template_name = 'xplanung_light/bplanbeteiligung_list.html'
    list_url_name = 'test'
    success_url = reverse_lazy(list_url_name) 

    def dispatch(self, request, *args, **kwargs):
        self.reference_object = get_object_or_404(
            self.reference_model,
            pk=self.kwargs["planid"],
        )
        self.check_gemeinde_admin(self.reference_object)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        if self.reference_model_name_lower == 'bplan':
            context['bplanid'] = self.kwargs['planid']
        if self.reference_model_name_lower == 'fplan':
            context['fplanid'] = self.kwargs['planid']
        context[self.reference_model_name_lower] = self.reference_model.objects.get(pk=self.kwargs['planid'])
        return context
    
    def get_queryset(self):
        # planid kommt aus der Routen-Regex (\d+) und ist nie leer; ein
        # unfilterbares "alle"-Ergebnis gab es hier nur theoretisch.
        if self.reference_model_name_lower == 'bplan':
            return self.model.objects.filter(
                bplan=self.reference_model.objects.get(pk=self.kwargs['planid'])
            )#.order_by('-created')
        if self.reference_model_name_lower == 'fplan':
            return self.model.objects.filter(
                fplan=self.reference_model.objects.get(pk=self.kwargs['planid'])
            )#.order_by('-created')
        

class XPlanRelationsUpdateView(GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, UpdateView):
    reference_model = BPlan
    reference_model_name_lower = str(reference_model._meta.model_name).lower()
    list_url_name = 'dummy'

    def dispatch(self, request, *args, **kwargs):
        self.reference_object = get_object_or_404(
            self.reference_model,
            pk=self.kwargs["planid"],
        )
        self.check_gemeinde_admin(self.reference_object)
        return super().dispatch(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        planid = self.kwargs['planid']
        context = super().get_context_data(**kwargs)
        context[self.reference_model_name_lower] = self.reference_object
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        return form 

    def form_valid(self, form):
        planid = self.kwargs['planid']
        if self.reference_model_name_lower == 'bplan':
            form.instance.bplan = self.reference_object
        if self.reference_model_name_lower == 'fplan':
            form.instance.fplan = self.reference_object
        return super().form_valid(form)

    def get_queryset(self):
        """
        Einschränken auf den jeweiligen Plan
        """
        queryset = super().get_queryset()

        if self.reference_model_name_lower == "bplan":
            return queryset.filter(bplan=self.reference_object)

        if self.reference_model_name_lower == "fplan":
            return queryset.filter(fplan=self.reference_object)
        # reference_model ist in allen Subklassen BPlan oder FPlan,
        # ein anderer Wert ist pro Klassenattribut nicht möglich.

    def get_success_url(self):
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})


class XPlanRelationsDeleteView(GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, DeleteView):
    """
    Beim Löschen muss Nutzer Admin aller zugewiesenen Gemeinden sein!
    """
    reference_model = BPlan
    reference_model_name_lower = str(reference_model._meta.model_name).lower()
    list_url_name = 'dummy'

    def get_success_url(self):
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})
    
    def get_object(self):
        object = super().get_object()
        # reference_model ist in allen Subklassen BPlan oder FPlan
        if self.reference_model_name_lower == "bplan":
            plan = object.bplan
        else:
            plan = object.fplan
        self.check_gemeinde_all_admin(plan)
        return object

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.reference_model_name_lower == "bplan":
            return queryset.filter(
                bplan_id=self.kwargs["planid"]
            )
        else:
            return queryset.filter(
                fplan_id=self.kwargs["planid"]
            )
        # reference_model ist in allen Subklassen BPlan oder FPlan,
        # ein anderer Wert ist pro Klassenattribut nicht möglich.
