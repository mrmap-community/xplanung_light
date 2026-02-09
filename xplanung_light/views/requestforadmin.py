from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from xplanung_light.models import RequestForOrganizationAdmin, AdministrativeOrganization
from xplanung_light.forms import RequestForOrganizationAdminCreateForm
from django.contrib.auth.mixins import LoginRequiredMixin
from xplanung_light.tables import RequestForOrganizationAdminTable, RequestForOrganizationAdminAdminTable
from django_tables2 import SingleTableView
from django.db.models import Subquery, OuterRef, Q
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

class RequestForOrganizationAdminCreateView(LoginRequiredMixin, CreateView):
    """
    Antragsformular um eine Organisationsadminrolle zugeteilt
    zu bekommen.
    """

    form_class = RequestForOrganizationAdminCreateForm
    model = RequestForOrganizationAdmin
    model_name_lower = str(model._meta).lower()
    template_name = 'xplanung_light/requestforadmin_form.html'
    # copy fields to form class - cause form class will handle the form now!
    #fields = ["organizations", ]
    #success_url = reverse_lazy(model_name_lower + "-list") 
    def get_form(self, form_class=None):
        """
        Liefert das Formular für den BPlanCreateView. Beim Select Field für die Gemeinden, werden nur die Gemeinden angezeigt, für die der Nutzer
        nicht schon admin ist.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            form.fields['organizations'].queryset = form.fields['organizations'].queryset.only("pk", "name", "type", "name_part")
        else:
            """
            Wir excluden hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*,
            da der Nutzer dann ja schon die admin Rolle hat.
            """
            #pending_requests = RequestForOrganizationAdmin.objects.filter(owned_by_user=self.request.user)
            
            #pending_requested_orgas = pending_requests.organizations.all()

            pending_requested_orgas = AdministrativeOrganization.objects.filter(pending_admin_requests__owned_by_user=self.request.user).distinct()
            form.fields['organizations'].queryset = form.fields['organizations'].queryset.exclude(organization_users__user=self.request.user, organization_users__is_admin=True).exclude(id__in = pending_requested_orgas).only("pk", "name", "type", "name_part")
        return form
    
    def form_valid(self, form):
        form.instance.owned_by_user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("requestforadmin-list")


class RequestForOrganizationAdminListView(LoginRequiredMixin, SingleTableView):
    """
    View für die Anzeige einer Liste von Anträgen für die Organisationsadmin-Rolle
    """
    model = RequestForOrganizationAdmin
    table_class = RequestForOrganizationAdminTable
    template_name = "xplanung_light/requestforadmin_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = RequestForOrganizationAdmin.objects.prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForOrganizationAdmin.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = RequestForOrganizationAdmin.objects.filter(owned_by_user=self.request.user).distinct().prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForOrganizationAdmin.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        return qs


class RequestForOrganizationAdminAdminListView(LoginRequiredMixin, SingleTableView):
    """
    View für die Anzeige einer Liste von Anträgen für die Organisationsadmin-Rolle (Sicht Zentraladmin)
    """
    model = RequestForOrganizationAdmin
    table_class = RequestForOrganizationAdminAdminTable
    template_name = "xplanung_light/requestforadmin_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = RequestForOrganizationAdmin.objects.prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForOrganizationAdmin.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = RequestForOrganizationAdmin.objects.filter(owned_by_user=self.request.user).distinct().prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForOrganizationAdmin.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        return qs


class RequestForOrganizationAdminDeleteView(LoginRequiredMixin, DeleteView):
    """
    View für das Löschen eines Antrags für die Organisationsadmin-Rolle
    """
    model = RequestForOrganizationAdmin
    template_name = "xplanung_light/requestforadmin_confirm_delete.html"
    success_message = "Antrag wurde gelöscht!"

    def form_valid(self, form):
        success_url = self.get_success_url()
        if self.request.user.is_superuser == True or self.object.owned_by_user == self.request.user:
            messages.add_message(self.request, messages.SUCCESS, "Antrag " + str(self.object.id) + " wurde gelöscht!")
            return super().form_valid(form)
        else:
            return super().form_invalid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == True or object.owned_by_user == self.request.user:
            return object
        else:
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
    
    def get_success_url(self):
        return reverse_lazy("requestforadmin-list")