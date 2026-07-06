from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView
from xplanung_light.models import AdminOrgaUser, AdministrativeOrganization, User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.views.user import ExtentUserOrgaInfo
from formset.views import FormViewMixin, IncompleteSelectResponseMixin
from django.core.exceptions import PermissionDenied
# claude hilfe:
# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from formset.views import FormView
from formset.views import FormViewMixin
from xplanung_light.forms import OrganizationUserAssignmentFormAdmin, OrganizationUserAssignmentFormToebReporter, UserOrganizationFormRoles

# django-formset 
class OrganizationUserFormViewAdmin(ExtentUserOrgaInfo, LoginRequiredMixin, FormView):
    form_class = OrganizationUserAssignmentFormAdmin
    template_name = 'xplanung_light/manage_users.html'
    success_url = '/organization/manage-users/admin/'
    #extra_context = None

    #def get_initial(self):
        #print(self.extra_context['role'])
        #if self.extra_context['role'] == 'toeb_reporter':
        #    self.form_class = OrganizationUserAssignmentFormToebReporter
        #    self.success_url = '/organization/manage-users-toeb-reporter/'
        #    return
        #return super().get_initial()

    def get_initial(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Nutzer ist kein Zentraladmin - Zuweisung ist nicht möglich!")
        return super().get_initial()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header'] = "Admin"
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization_id'] = self.request.GET.get('organization')
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.add_error("organization", "Nutzer ist kein Zentraladmin - Zuweisung ist nicht möglich!")
            return super().form_invalid(form)
        organization = form.save()
        self.organization = organization
        messages.success(
            self.request,
            f'Nutzer-Zuweisungen für {organization.name} erfolgreich gespeichert.'
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        organization_id = getattr(self, 'organization', None) and self.organization.id
        if organization_id:
            return f'{self.success_url}?organization={organization_id}'
        return self.success_url


class OrganizationUserFormViewToebReporter(ExtentUserOrgaInfo, LoginRequiredMixin, FormView):
    """
    Klasse um Nutzern die TOEB-Reporter Rolle zuzuweisen. Die View kann sowohl vom Zentraladmin, als auch den admins einzelner Orgas genutzt werden.
    Wichtig: Benutzernamen und EMail-Adressen aller Nutzer sind sichtbar. Das muss in den Nutzungsbedingungen dokumentiert sein!
    """
    form_class = OrganizationUserAssignmentFormToebReporter
    template_name = 'xplanung_light/manage_users.html'
    success_url = '/organization/manage-users/toeb-reporter/'

    def get_initial(self):
        # Middleware ergänzt request schon um user_is_admin Eigenschaft  
        if not self.request.user.is_superuser and not self.request.user_is_admin:
            raise PermissionDenied("Nutzer ist weder Zentraladmin, noch hat er die Admin-Rolle für eine Organisation - Zuweisung ist nicht möglich!")
        return super().get_initial()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header'] = "TOEB-Reporter"
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization_id'] = self.request.GET.get('organization')
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser and not self.request.user_is_admin:
            form.add_error("organization", "Nutzer ist weder Zentraladmin, noch hat er die Admin-Rolle für eine Organisation - Zuweisung ist nicht möglich!")
            return super().form_invalid(form)
        if form.is_valid():
            organization = form.cleaned_data['organization']
            if not (self.request.user.is_superuser or AdminOrgaUser.objects.filter(
                organization=organization, user=self.request.user, is_admin=True
            ).exists()):
                raise PermissionDenied("Keine Berechtigung für diese Organisation")
            organization = form.save()    
            self.organization = organization
            """
            Prüfen, ob ein Nutzer ausgeschlossen wurde - passiert in der save-Methode der Form - die Eigenschaften werden da gesetzt und hier abgerufen
            """
            # Prüfen, ob im Formular Nutzer ausgeschlossen wurden
            any_excluded = getattr(form, 'some_user_excluded', False)
            excluded_users = User.objects.filter(id__in=getattr(form, 'org_users_single_toebunit', []))
            excluded_users_string = ""
            for excluded_user in excluded_users:
                excluded_users_string = excluded_user.username + " (" + excluded_user.email + ")" + " | "
            excluded_users_string = excluded_users_string.strip(' | ')
            if any_excluded:
                messages.warning(self.request, 'Manche Nutzer konnten nicht angepasst werden, da sie der letzte TOEB-Reporter in einem laufenden Verfahren sind: ' + excluded_users_string)
        messages.success(
            self.request,
            f'Nutzer-Zuweisungen für {organization.name} erfolgreich gespeichert.'
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        organization_id = getattr(self, 'organization', None) and self.organization.id

        if organization_id:
            return f'{self.success_url}?organization={organization_id}'
        return self.success_url

class UserOrganizationFormViewRoles(ExtentUserOrgaInfo, LoginRequiredMixin, FormView):
    form_class = UserOrganizationFormRoles
    template_name = 'xplanung_light/manage_users.html'
    success_url = '/organization/manage-users/roles/'

    def get_initial(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Nutzer ist kein Zentraladmin - Zuweisung ist nicht möglich!")
        return super().get_initial()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header'] = "Nutzer und Rollen"
        if self.request.GET.get('user'):
            context['adminorgauser'] = AdminOrgaUser.objects.filter(user__id = self.request.GET.get('user'))
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user_id'] = self.request.GET.get('user')
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.add_error("user", "Nutzer ist kein Zentraladmin - Zuweisung ist nicht möglich!")
            return super().form_invalid(form)
        user = form.save()
        messages.success(
            self.request,
            f'Rollen für Nutzer {user.username} erfolgreich selektiert.'
        )
        return super().form_valid(form)