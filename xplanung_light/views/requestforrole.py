from django.views.generic import CreateView, UpdateView, DeleteView, ListView
from xplanung_light.models import RequestForRole, AdministrativeOrganization
from xplanung_light.forms import RequestForRoleCreateForm
from django.contrib.auth.mixins import LoginRequiredMixin
from xplanung_light.tables import RequestForRoleTable, RequestForRoleAdminTable
from django_tables2 import SingleTableView
from django.db.models import Subquery, OuterRef, Q, Count, F
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from xplanung_light.views.user import ExtentUserOrgaInfo

class RequestForRoleCreateView(ExtentUserOrgaInfo, LoginRequiredMixin, CreateView):
    """
    Antragsformular um eine Benutzerrolle zugeteilt
    zu bekommen.
    """

    form_class = RequestForRoleCreateForm
    model = RequestForRole
    model_name_lower = str(model._meta).lower()
    template_name = 'xplanung_light/requestforrole_form.html'
    # copy fields to form class - cause form class will handle the form now!
    #fields = ["organizations", ]
    #success_url = reverse_lazy(model_name_lower + "-list") 
    def get_form(self, form_class=None):
        """
        Liefert das Formular für den BPlanCreateView. Beim Select Field für die Gemeinden, werden nur die Gemeinden angezeigt, für die der Nutzer
        nicht schon 
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            form.fields['organizations'].queryset = form.fields['organizations'].queryset.only("pk", "name", "type", "name_part")
        else:
            """
            Wir excluden ggf. hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *admin_orga_users* und auf die Eigenschaft *is_admin*,
            da der Nutzer dann ja schon die admin Rolle hat.
            """

            #pending_requested_orgas = AdministrativeOrganization.objects.filter(pending_admin_requests__owned_by_user=self.request.user).distinct()
            
            # TODO queryset ggf. anpassen
            #form.fields['organizations'].queryset = form.fields['organizations'].queryset.exclude(admin_orga_users__user=self.request.user, admin_orga_users__is_admin=True).exclude(id__in = pending_requested_orgas).only("pk", "name", "type", "name_part")
            form.fields['organizations'].queryset = form.fields['organizations'].queryset.only("pk", "name", "type", "name_part")
        
        return form
    
    def form_valid(self, form):
        form.instance.owned_by_user = self.request.user
        # Versand einer EMail an den Zentraladmin Account - dann weiß er Bescheid, dass etwas zu tun ist
        antragsliste_link = self.request.build_absolute_uri(reverse("requestforrole-admin-list"))
        if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https']:
            antragsliste_link = antragsliste_link.replace('http://', 'https://')
        subject = str("XPlanung-light - Antrag auf Zuweisung einer " + form.instance.get_role_display() + "-Rolle eingegangen")
        html_content = render_to_string("xplanung_light/email/role_antrag_eingang.html", context={"antragsliste_link": antragsliste_link, },)
        text_content = render_to_string("xplanung_light/email/role_antrag_eingang.txt", context={"antragsliste_link": antragsliste_link, },)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],
            to=[str(settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']),],
            #bcc=[str(farmshop.contact_email),],
            reply_to=[settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],]
        )
        #email.content_subtype = "text"
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("requestforrole-list")


class RequestForRoleListView(ExtentUserOrgaInfo, LoginRequiredMixin, SingleTableView):
    """
    View für die Anzeige einer Liste von Anträgen für die Organisationsrolle
    """
    model = RequestForRole
    table_class = RequestForRoleTable
    template_name = "xplanung_light/requestforrole_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = RequestForRole.objects.prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForRole.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = RequestForRole.objects.filter(owned_by_user=self.request.user).distinct().prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForRole.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        return qs


class RequestForRoleAdminListView(ExtentUserOrgaInfo, LoginRequiredMixin, SingleTableView):
    """
    View für die Anzeige einer Liste von Anträgen für die Organisationsadmin-Rolle (Sicht Zentraladmin)
    """
    model = RequestForRole
    table_class = RequestForRoleAdminTable
    template_name = "xplanung_light/requestforroleadmin_list.html"

    """
    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = RequestForRole.objects.prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForRole.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            # Nur die Anträge für Orgas anzeigen, für die der Nutzer die Admin-Rolle hat (muss für alle Organisationen gelten - da die Anträge für mehrere gestelt werden können)
            user_admin_orgas = AdministrativeOrganization.objects.filter(admin_orga_users__user=self.request.user, admin_orga_users__is_admin=True)
            qs = RequestForRole.objects.filter(organizations__in=user_admin_orgas).distinct().prefetch_related('organizations').annotate(last_changed=Subquery(
                RequestForRole.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        return qs
    """
    # Count ist hier schneller als der doppelte Ausschluss mit zweimal exclude - es werden nur Antrage für TOEB-Reporter zugelassen
    def get_queryset(self):
        base_qs = RequestForRole.objects.prefetch_related('organizations').annotate(
            last_changed=Subquery(
                RequestForRole.history.filter(id=OuterRef("pk"))
                .order_by('-history_date')
                .values('history_date')[:1]
            )
        ).order_by('-last_changed')

        if self.request.user.is_superuser:
            qs = base_qs
        else:
            user = self.request.user
            qs = base_qs.annotate(
                total_orgas=Count('organizations', distinct=True),
                admin_orgas=Count(
                    'organizations',
                    filter=Q(
                        organizations__admin_orga_users__user=user,
                        organizations__admin_orga_users__is_admin=True,
                    ),
                    distinct=True,
                ),
            ).filter(total_orgas=F('admin_orgas'), total_orgas__gt=0).filter(role='TR')

        return qs


class RequestForRoleDeleteView(ExtentUserOrgaInfo, LoginRequiredMixin, DeleteView):
    """
    View für das Löschen eines Antrags für die Organisationsrolle
    """
    model = RequestForRole
    template_name = "xplanung_light/requestforrole_confirm_delete.html"
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
        if self.request.user.is_superuser == True:
            return reverse_lazy("requestforrole-list")
        else:
            return reverse_lazy("requestforrole-admin-list")