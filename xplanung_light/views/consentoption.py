from django.http import  HttpResponseRedirect
from django.views.generic import (CreateView, UpdateView, DeleteView)
from xplanung_light.models import ConsentOption
from xplanung_light.forms import ConsentOptionForm
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import ConsentOptionTable
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from formset.views import FormViewMixin
from datetime import datetime

class ConsentOptionCreateView(FormViewMixin, SuccessMessageMixin, CreateView):
    model = ConsentOption
    form_class = ConsentOptionForm
    template_name = "xplanung_light/consentoption_form.html"
    extra_context = None

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_form(self, form_class=None):
        """
        Liefert das Formular für die ConsentOption, wenn Nutzer superuser ist.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            return form
        else:
            return False

    def form_valid(self, form):
        if self.request.user.is_superuser:
            return super().form_valid(form)
        form.add_error(None, "Nutzer ist nicht der zentrale Administrator!")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("consentoption-list")
    

class ConsentOptionUpdateView(FormViewMixin, SuccessMessageMixin, UpdateView):
    model = ConsentOption
    form_class = ConsentOptionForm
    template_name = "xplanung_light/consentoption_form.html"
    extra_context = None

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_form(self, form_class=None):
        """
        Liefert das Formular für die ConsentOption, wenn Nutzer superuser ist.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            return form
        else:
            return False
    
    def form_valid(self, form):
        if self.request.user.is_superuser:
            #TODO:  Test, ob die Zustimmungsoption schon von irgendwem akzeptiert wurde, falls das so ist, darf sie nicht mehr gelöscht werden!
            return super().form_valid(form)
        form.add_error(None, "Nutzer ist nicht der zentrale Administrator!")
        return super().form_invalid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser:                
            return object
        else:
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")

    def get_success_url(self):
        return reverse_lazy("consentoption-list")
    
    
class ConsentOptionListView(SingleTableView):
    model = ConsentOption
    table_class = ConsentOptionTable
    template_name = "xplanung_light/consentoption_list.html"


class ConsentOptionDeleteView(SuccessMessageMixin, DeleteView):
    model = ConsentOption
    success_message = "Zustimmungsoption wurde gelöscht!"
    template_name = "xplanung_light/consentoption_confirm_delete.html"

    def form_valid(self, form):
        success_url = self.get_success_url()
        if self.request.user.is_superuser:
            object = self.get_object()
        else:
            messages.add_message(self.request, messages.WARNING, "Nutzer ist kein Administrator - Zustimmungsoption kann nicht gelöscht werden!")
            return HttpResponseRedirect(success_url)
        self.object.delete()
        messages.add_message(self.request, messages.SUCCESS, "Zustimmungsoption " + self.object.title + " wurde gelöscht!")
        return HttpResponseRedirect(success_url)

    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser:
            #TODO:  Test, ob die Zustimmungsoption schon von irgendwem akzeptiert wurde, falls das so ist, darf sie nicht mehr gelöscht werden!
            pass
        else:      
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def get_success_url(self):
        return reverse_lazy("consentoption-list")