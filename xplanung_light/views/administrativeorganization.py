from django.views.generic import (UpdateView)
from xplanung_light.models import AdministrativeOrganization
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import AdministrativeOrganizationTable, AdministrativeOrganizationPublishingTable
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import AdministrativeOrganizationUpdateForm
from django.db.models import Subquery, OuterRef
from django.db.models import Count
from dal import autocomplete
from django.core.exceptions import PermissionDenied


class AdministrativeOrganizationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return AdministrativeOrganization.objects.none()
        qs = AdministrativeOrganization.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


class AdministrativeOrganizationPublishingListView(SingleTableView):
    """
    Tabellen View zur Auflistung der Pläne der einzelnen Gebietskörperschaften (AdministrativeOrganization) mit den 
    Zugriffspunkten der jeweiligen die OGC-Dienste 
    """
    model = AdministrativeOrganization
    table_class = AdministrativeOrganizationPublishingTable
    template_name = 'xplanung_light/orga_publishing_list.html'
    success_url = reverse_lazy("orga-publishing-list") 

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = AdministrativeOrganization.objects.filter(bplan__isnull=False).distinct().annotate(num_bplan=Count('bplan'))
        else:
            qs = AdministrativeOrganization.objects.filter(bplan__isnull=False, users=self.request.user).distinct().annotate(num_bplan=Count('bplan'))
        return qs
    

class AdministrativeOrganizationListView(SingleTableView):
    """
    Liste der Organisations-Datensätze.

    Klasse für die Anzeige aller Organisationen, für die ein Nutzer Administrationsberechtigungen hat. 
    """
    model = AdministrativeOrganization
    table_class = AdministrativeOrganizationTable
    template_name = 'xplanung_light/organization_list.html'
    success_url = reverse_lazy("organization-list") 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
        #if True:
            qs = AdministrativeOrganization.objects.annotate(last_changed=Subquery(
                AdministrativeOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').only('id', 'name', 'name_part', 'ls', 'ks', 'gs', 'ts')
        else:
            qs = AdministrativeOrganization.objects.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(last_changed=Subquery(
                AdministrativeOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').only('id', 'name', 'name_part', 'ls', 'ks', 'gs', 'ts')
        return qs


class AdministrativeOrganizationUpdateView(SuccessMessageMixin, UpdateView):
    """
    Editieren eines Organisations-Datensatzes.

    """
    form_class = AdministrativeOrganizationUpdateForm
    model = AdministrativeOrganization
    success_url = reverse_lazy("organization-list") 
    success_message = "Organisation wurde aktualisiert!"

    def get_form(self, form_class=None):
        success_url = self.get_success_url()
        form = super().get_form(form_class)
        return form
    
    def form_valid(self, form):
        object=self.get_object()
        self.success_message = "Organisation *" + object.name + "* aktualisiert!" 
        return super().form_valid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for user in object.organization_users.all():
                if user.user == self.request.user and user.is_admin:                    
                    return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object  