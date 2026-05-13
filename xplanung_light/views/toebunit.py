from django.http import  HttpResponseRedirect
from django.views.generic import (CreateView, UpdateView, DeleteView, ListView, DetailView)
from xplanung_light.models import ToebUnit
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import ToebUnitTable
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import ToebUnitCreateForm, ToebUnitUpdateForm
from django.db.models import Subquery, OuterRef
from django.contrib.gis.db.models import Extent
from django.core.exceptions import PermissionDenied
from leaflet.forms.widgets import LeafletWidget
from django.db import transaction
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db.models import Case, When, Value, CharField

class ToebUnitCreateView(SuccessMessageMixin, CreateView):
    model = ToebUnit
    form_class = ToebUnitCreateForm

    """
    def get_queryset(self):
        qs = super(self).get_queryset()
        qs = qs.annotate(
            theme_display=Case(
                *[
                    When(theme=value, then=Value(label))
                    for value, label in ToebUnit.THEME_CLASS_CHOICES
                ],
                output_field=CharField(),
            )
        )
        return qs
    """

    def get_form(self, form_class=None):
        """
        Liefert das Formular für den ToebUnitCreateView. Beim Select Field für die Organisationen, werden nur die angezeigt, für die der Nutzer
        das Attribut is_admin = True hat.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            form.fields['organization'].queryset = form.fields['organization'].queryset.annotate(bbox=(Extent("geometry"))).only("pk", "name", "type", "name_part")
            form.fields['editors'].queryset = form.fields['editors'].queryset.filter(is_toeb_reporter=True)
        else:
            """
            Wir filtern hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*
            
            """
            form.fields['organization'].queryset = form.fields['organization'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(bbox=(Extent("geometry"))).only("pk", "name", "type", "name_part")
            form.fields['editors'].queryset = form.fields['editors'].queryset.filter(is_toeb_reporter=True, organization_users__user=self.request.user)
        # Geometriefeld hinzufügen
        form.fields['geometry'].widget = LeafletWidget(attrs={'geom_type': 'MultiPolygon', 'map_height': '400px', 'map_width': '90%','MINIMAP': True})
        # Herausnehmen der organizationn, die schon eine Kontaktstelle zugewiesen bekommen haben
        #form.fields['organization'].queryset = form.fields['organization'].queryset.filter(contacts__isnull = True)
        return form
    
    @transaction.atomic
    def form_valid(self, form):
        # 1. Objekt instanziieren, aber noch nicht in die DB schreiben
        self.object = form.save(commit=False)
        # 2. Hauptobjekt speichern (erzeugt die ID)
        self.object.save()
        # 3. M2M-Beziehungen explizit sichern (schlägt dies fehl, gibt es einen Rollback zu Schritt 2)
        form.save_m2m()
        # 4. Standard-Weiterleitung ausführen
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("toebunit-list")


class ToebUnitUpdateView(SuccessMessageMixin, UpdateView):
    model = ToebUnit
    form_class = ToebUnitUpdateForm
    template_name = "xplanung_light/toebunit_form_update.html"
    
    """
    def get_queryset(self):
        qs = super(self).get_queryset()
        qs = qs.annotate(
            theme_display=Case(
                *[
                    When(theme=value, then=Value(label))
                    for value, label in ToebUnit.THEME_CLASS_CHOICES
                ],
                output_field=CharField(),
            )
        )
        return qs
    """

    def get_form(self, form_class=None):
        #success_url = self.get_success_url()
        form = super().get_form(form_class)
        #object = self.get_object()
        if self.request.user.is_superuser:
            form.fields['organization'].queryset = form.fields['organization'].queryset.annotate(bbox=(Extent("geometry"))).only("pk", "name", "type", "name_part")
            form.fields['editors'].queryset = form.fields['editors'].queryset.filter(is_toeb_reporter=True)
        else:
            form.fields['organization'].queryset = form.fields['organization'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(bbox=(Extent("geometry"))).only("pk", "name", "type", "name_part")
            form.fields['editors'].queryset = form.fields['editors'].queryset.filter(is_toeb_reporter=True, organization_users__user=self.request.user)
        # Erweitern der organizationn, die noch keinem Kontakt zugewiesen wurden, mit denen, die schon am Record vorhanden sind 
        # https://studygyaan.com/django/combining-multiple-querysets-in-django-with-examples
        #form.fields['organization'].queryset = form.fields['organization'].queryset.filter(contacts__isnull = True).only("pk", "name", "type") | object.organization.get_queryset().only("pk", "name", "type")
        form.fields['geometry'].widget = LeafletWidget(attrs={'geom_type': 'MultiPolygon', 'map_height': '400px', 'map_width': '90%','MINIMAP': True})
        return form
    
    def form_valid(self, form):
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator der Organisation eingetragen ist
            organization = form.cleaned_data['organization']
            user_is_admin = False
            for user in organization.organization_users.all():
                if user.user == self.request.user and user.is_admin:
                    user_is_admin = True                         
                    return super().form_valid(form)
            if user_is_admin == False:
                form.add_error("organization", "Nutzer ist kein Administrator für die der TOEB-Stelle zugewiesenen Organisation - TOEB-Stelle kann nicht aktualisiert werden!")
                return super().form_invalid(form)
        self.success_message = "TOEB-Stelle *" + form.cleaned_data['name'] + "* aktualisiert!" 
        return super().form_valid(form)
    
    def clean(self):
        cleaned_data = super().clean()
        organization = cleaned_data.get("organization")
        editors = cleaned_data.get("editors")
        if organization and editors:
            invalid_editors = editors.exclude(
                organization=organization
            )
            if invalid_editors.exists():
                raise ValidationError(
                    "Alle Sachbearbeiter müssen zur "
                    "gleichen Organisation gehören."
                )
            invalid_reporters = editors.exclude(
                is_toeb_reporter=True
            )
            if invalid_reporters.exists():
                raise ValidationError(
                    "Alle Sachbearbeiter müssen "
                    "TOEB-Reporter sein."
                )
        return cleaned_data

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related("organization")
        )

    def get_object(self):
        object = super().get_object()
        #object = self.object
        if self.request.user.is_superuser == False:
            organization = object.organization
            for user in organization.organization_users.all():
                if user.user == self.request.user and user.is_admin:                    
                    return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object 

    def get_success_url(self):
        return reverse_lazy("toebunit-list")


class ToebUnitListView(SuccessMessageMixin, SingleTableView):
    model = ToebUnit
    table_class = ToebUnitTable
    template_name = "xplanung_light/toebunit_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = ToebUnit.objects.prefetch_related('organization').annotate(last_changed=Subquery(
                ToebUnit.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = ToebUnit.objects.filter(organization__organization_users__user=self.request.user, organization__organization_users__is_admin=True).distinct().prefetch_related('organization').annotate(last_changed=Subquery(
                ToebUnit.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        
        return qs


class ToebUnitDeleteView(SuccessMessageMixin, DeleteView):
    model = ToebUnit
    success_message = "TOEB-Stelle wurde gelöscht!"
    template_name = "xplanung_light/toebunit_confirm_delete.html"

    def form_valid(self, form):
        success_url = self.get_success_url()
        if self.request.user.is_superuser == False:
            object = self.get_object()
            organization = object.organization
            user_is_admin = False
            for user in organization.organization_users.all():
                if user.user == self.request.user and user.is_admin:
                    user_is_admin = True 
            if user_is_admin == False:
                messages.add_message(self.request, messages.WARNING, "Nutzer ist kein Administrator der angegebenen Organisation - TOEB-Stelle kann nicht gelöscht werden!")
                return HttpResponseRedirect(success_url)
        self.object.delete()
        messages.add_message(self.request, messages.SUCCESS, "TOEB-Stelle " + self.object.name + " wurde gelöscht!")
        return HttpResponseRedirect(success_url)

    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            organization = object.organization
            user_is_admin = False
            for user in organization.organization_users.all():
                if user.user == self.request.user and user.is_admin:
                    user_is_admin = True 
            if user_is_admin == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def get_success_url(self):
        return reverse_lazy("toebunit-list")
