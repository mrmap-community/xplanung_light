from xplanung_light.forms import BPlanBeteiligungForm
from django.views.generic import (CreateView, UpdateView, DeleteView)
from xplanung_light.models import BPlan, BPlanBeteiligung
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungTable
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied


"""
Klassen zur Verwaltung von Beteiligungen
"""
class BPlanBeteiligungCreateView(CreateView):
    model = BPlanBeteiligung
    form_class = BPlanBeteiligungForm
    
    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        bplan = BPlan.objects.get(pk=bplanid)
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                         context['bplan'] = bplan
                         return context
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        context['bplan'] = bplan
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
        bplanid = self.kwargs['bplanid']
        
        form['initial'].update({'bplan': BPlan.objects.get(pk=bplanid)})
        #form['initial'].update({'owned_by_user': self.request.user})
        return form
        #return super().get_form_kwargs()

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        # TODO: check ob der Extent des Rasterbilds innerhalb der Abgrenzung der AdministrativeUnit liegt ...  
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})   
    

class BPlanBeteiligungListView(SingleTableView):
    model = BPlanBeteiligung
    table_class = BPlanBeteiligungTable
    template_name = 'xplanung_light/bplanbeteiligung_list.html'
    success_url = reverse_lazy("bplanbeteiligung-list") 

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['bplanid'] = self.kwargs['bplanid']
        context['bplan'] = BPlan.objects.get(pk=self.kwargs['bplanid'])
        return context
    
    def get_queryset(self):
        bplanid = self.kwargs['bplanid']
        if bplanid:
            return self.model.objects.filter(
            bplan=BPlan.objects.get(pk=bplanid)
        )#.order_by('-created')
        else:
            return self.model.objects#.order_by('-created')
        

class BPlanBeteiligungUpdateView(UpdateView):
    model = BPlanBeteiligung
    #fields = ["typ", "name", "attachment"]
    form_class = BPlanBeteiligungForm

    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        context['bplan'] = BPlan.objects.get(pk=bplanid)
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        return form 
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for gemeinde in object.bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                        return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})


class BPlanBeteiligungDeleteView(DeleteView):
    model = BPlanBeteiligung

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            user_orga_admin = []
            for gemeinde in object.bplan.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object
    