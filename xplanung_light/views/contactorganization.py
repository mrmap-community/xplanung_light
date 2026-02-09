from django.http import  HttpResponseRedirect
from django.views.generic import (CreateView, UpdateView, DeleteView)
from xplanung_light.models import ContactOrganization
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import ContactOrganizationTable
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import ContactOrganizationCreateForm, ContactOrganizationUpdateForm
from django.db.models import Subquery, OuterRef
from django.contrib.gis.db.models import Extent
from django.core.exceptions import PermissionDenied


class ContactOrganizationCreateView(SuccessMessageMixin, CreateView):
    model = ContactOrganization
    form_class = ContactOrganizationCreateForm
    template_name = "xplanung_light/contact_form.html"

    def get_form(self, form_class=None):
        """
        Liefert das Formular für den BPlanCreateView. Beim Select Field für die Gemeinden, werden nur die Gemeinden angezeigt, für die der Nutzer
        das Attribut is_admin = True hat.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.only("pk", "name", "type", "name_part")
        else:
            """
            Wir filtern hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*
            
            """
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).only("pk", "name", "type", "name_part")
        # Herausnehmen der Gemeinden, die schon eine Kontaktstelle zugewiesen bekommen haben
        form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(contacts__isnull = True)
        return form

    def form_valid(self, form):
        # TODO check if contact for gemeinde already exist!
        for gemeinde in form.cleaned_data['gemeinde']:
            if gemeinde.contacts.all().count() >= 1:
                form.add_error("gemeinde", "Die Gemeinde *" + str(gemeinde) + "* hat schon eine Kontaktstelle angegeben: " + str(gemeinde.contacts.first())+ " - mehrere sind nicht zulässig!")
                return super().form_invalid(form)
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator für jede Gemeinde eingetragen ist
            for gemeinde in form.cleaned_data['gemeinde']:
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                if user_is_admin == False:
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für die der Kontaktorganisation zugewiesene Gemeinde *" + str(gemeinde) + "* - Kontaktorganisation kann nicht angelegt werden!")
                    return super().form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("contact-list")
    

class ContactOrganizationUpdateView(SuccessMessageMixin, UpdateView):
    model = ContactOrganization
    form_class = ContactOrganizationUpdateForm
    template_name = "xplanung_light/contact_form_update.html"

    def get_form(self, form_class=None):
        success_url = self.get_success_url()
        form = super().get_form(form_class)
        object = self.get_object()
        #form.fields['gemeinde'].queryset = 
        if self.request.user.is_superuser:
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.only("pk", "name", "type")
        else:
            # Deaktivieren des Gemeinde Fields - falls auch noch andere Gemeinde am Plan hängt, für die der aktuelle Nutzer kein admin ist
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                form.fields['gemeinde'].disabled = True
                form.fields['gemeinde'].label = "Gemeinden sind nicht editierbar (Nutzer ist nicht Administrator aller Gemeinden)"
            else:
                """
                Wir filtern hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*
                """
                form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).only("pk", "name", "type")
        # Erweitern der Gemeinden, die noch keinem Kontakt zugewiesen wurden, mit denen, die schon am Record vorhanden sind 
        # https://studygyaan.com/django/combining-multiple-querysets-in-django-with-examples
        form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(contacts__isnull = True).only("pk", "name", "type") | object.gemeinde.get_queryset().only("pk", "name", "type")
        return form
    
    def form_valid(self, form):
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator eine der Gemeinden eingetragen ist
            for gemeinde in form.cleaned_data['gemeinde']:
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True                         
                        return super().form_valid(form)
                if user_is_admin == False:
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für eine der der Kontaktorganisation zugewiesenen Gemeinde - Kontaktorganisation kann nicht aktualisiert werden!")
                    return super().form_invalid(form)
        self.success_message = "Kontaktorganisation *" + form.cleaned_data['name'] + "* aktualisiert!" 
        return super().form_valid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for gemeinde in object.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                    
                        return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object 

    def get_success_url(self):
        return reverse_lazy("contact-list")
    
    
class ContactOrganizationListView(SingleTableView):
    model = ContactOrganization
    table_class = ContactOrganizationTable
    template_name = "xplanung_light/contact_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
        #if True:
            qs = ContactOrganization.objects.prefetch_related('gemeinde').annotate(last_changed=Subquery(
                ContactOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = ContactOrganization.objects.filter(gemeinde__organization_users__user=self.request.user, gemeinde__organization_users__is_admin=True).distinct().prefetch_related('gemeinde').annotate(last_changed=Subquery(
                ContactOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        
        return qs


class ContactOrganizationDeleteView(SuccessMessageMixin, DeleteView):
    model = ContactOrganization
    success_message = "Kontaktorganisation wurde gelöscht!"
    template_name = "xplanung_light/contact_confirm_delete.html"

    def form_valid(self, form):
        success_url = self.get_success_url()
        if self.request.user.is_superuser == False:
            object = self.get_object()
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                messages.add_message(self.request, messages.WARNING, "Nutzer ist kein Administrator für alle der Kontaktorganisation zugewiesene Gemeinde(n) - Kontaktorganisation kann nicht gelöscht werden!")
                return HttpResponseRedirect(success_url)
        self.object.delete()
        messages.add_message(self.request, messages.SUCCESS, "Kontaktorganisation " + self.object.name + " wurde gelöscht!")
        return HttpResponseRedirect(success_url)

    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def get_success_url(self):
        return reverse_lazy("contact-list")