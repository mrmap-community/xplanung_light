from django.views.generic import ListView, CreateView, DetailView
from xplanung_light.models import BPlan, BPlanBeteiligung, AdministrativeOrganization
from xplanung_light.models import FPlanBeteiligung, FPlan, ContactOrganization
from xplanung_light.models import ConsentOption, AdminOrgaUser, ToebUnit
from xplanung_light.models import BPlanBeteiligungToebNotification, FPlanBeteiligungToebNotification
from formset.views import FormViewMixin, FormCollectionView, EditCollectionView
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungToebNotificationTable, FPlanBeteiligungToebNotificationTable
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import BPlanBeteiligungCollection, FPlanBeteiligungCollection, BPlanBeteiligungToebNotificationCreateForm, FPlanBeteiligungToebNotificationCreateForm
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.db.models import Count
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
from django.db import transaction
from xplanung_light.views.user import ExtentUserOrgaInfo
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone

class BeteiligungToebNotificationListView(ExtentUserOrgaInfo, SingleTableView):
    """
    ListView zur Anzeige der BeteiligungToebNotification-Records. Hier Die Klasse entscheidet je nach URL, 
    um welchen Plantyp es sich handelt.
    """
    # Default Werte für Initialiisierung - werden durch dispatch Funktion überschrieben
    model = BPlanBeteiligungToebNotification
    parent_model = BPlanBeteiligung
    reference_model = BPlan
    table_class = BPlanBeteiligungToebNotificationTable
    reference_model_name_lower = 'bplan'
    
    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungToebNotification
            self.parent_model = BPlanBeteiligung
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungToebNotification
            self.parent_model = FPlanBeteiligung
            self.table_class = FPlanBeteiligungToebNotificationTable
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beteiligungtoebnotification_list.html'
        self.beteiligungid = kwargs.get('beteiligungid')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        """
        Docstring for get_queryset
        
        :param self: Description
        :param kwargs: Description
        """
        qs = super().get_queryset().annotate(
                    last_changed=Subquery(
                        self.model.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )
                )
        plan = self.reference_model.objects.get(pk=self.kwargs['planid'])
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.admin_orga_users.all():
                    if user.user == self.request.user and user.is_admin:   
                        # Zugriff wird erteilt
                        if self.plantyp == 'bplan':                    
                            return qs.filter(bplanbeteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
                        if self.plantyp == 'fplan':                    
                            return qs.filter(fplanbeteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
            raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
        else:
            if self.plantyp == 'bplan': 
                return qs.filter(bplanbeteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
            if self.plantyp == 'fplan': 
                return qs.filter(fplanbeteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
        

    def get_context_data(self, **kwargs):
        """
        Docstring for get_context_data
        
        :param self: Description
        :param kwargs: Description
        """
        #planid = self.kwargs['planid']
        #beteiligungid = self.kwargs['beteiligungid']
        context = super().get_context_data(**kwargs)
        context["plan"] = self.reference_model.objects.get(pk=self.planid)
        context["plantyp"] = self.plantyp
        context["beteiligung"] = self.parent_model.objects.get(pk=self.beteiligungid)
        if context["beteiligung"].bekanntmachung_datum <= timezone.now().date() and context["beteiligung"].end_datum >= timezone.now().date():
            context["status"] = 1
        else:
            context["status"] = 0
        return context

    
class BeteiligungToebNotificationCreateView(ExtentUserOrgaInfo, CreateView):
    """
    View für Abbildung des kombinierten Fomulars über django-formsets EditCollectionView - das Formular ist nur für die Öffentlichkeit gedacht
    https://django-formset.fly.dev/model-collections/

    """
    # Initialisierung der Attribute - werden in dispatch Funktion überschrieben!
    plantyp = None
    model = BPlanBeteiligungToebNotification
    form_class = BPlanBeteiligungToebNotificationCreateForm
    planmodel = None
    beteiligungid = None
    parent_model = BPlanBeteiligung
    template_name = 'xplanung_light/beteiligungtoebnotification_form.html'
    #success_url = reverse_lazy("beteiligungnotification-list", { plantyp='bplan', }) 

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungToebNotification
            self.planmodel = BPlan
            self.parent_model = BPlanBeteiligung
            #self.template_name = 'xplanung_light/beteiligungtoebnotification_form.html'
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungToebNotification
            self.planmodel = FPlan
            self.parent_model = FPlanBeteiligung
            self.form_class = FPlanBeteiligungToebNotificationCreateForm
            #self.template_name = 'xplanung_light/beteiligungtoebnotification_form.html'
            #self.form_class = BeteiligungToebNotificationCreateForm
        self.planid = kwargs.get('planid')
        self.beteiligungid = kwargs.get('beteiligungid')
        return super().dispatch(request, *args, **kwargs)

    #def get_queryset(self):
    #    qs = super().get_queryset()
        # Check Zeitrahmen des Verfahrens
    #    print(str(beteiligung.bekanntmachung_datum))
    #    beteiligung = self.parent_model.objects.get(pk=self.beteiligungid)
    #    if not (beteiligung.bekanntmachung_datum <= timezone.now().date() and beteiligung.end_datum >= timezone.now().date()):
    #        raise PermissionDenied("Benachrichtigungen außerhalb des Zeitrahmens sind nicht möglich!")
    #    return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        beteiligungmodel = (
            BPlanBeteiligung if self.plantyp == 'bplan' else FPlanBeteiligung
        )
        kwargs['beteiligung'] = get_object_or_404(
            beteiligungmodel,
            pk=self.beteiligungid
        )
        if not (kwargs['beteiligung'].bekanntmachung_datum <= timezone.now().date() and kwargs['beteiligung'].end_datum >= timezone.now().date()):
            raise PermissionDenied("Benachrichtigungen außerhalb des Zeitrahmens sind nicht möglich!")
        return kwargs
    
    def form_valid(self, form):
        if self.plantyp == 'bplan':
            form.instance.bplanbeteiligung_id = self.beteiligungid
        if self.plantyp == 'fplan':
            form.instance.fplanbeteiligung_id = self.beteiligungid   
        beteiligungmodel = (
            BPlanBeteiligung if self.plantyp == 'bplan' else FPlanBeteiligung
        )
        beteiligung = get_object_or_404(
            beteiligungmodel,
            pk=self.beteiligungid
        )
        form.instance.start = timezone.now()
        # send mail
        if self.plantyp == 'bplan':
            plan = BPlan.objects.get(id=self.planid)
        if self.plantyp == 'fplan':
            plan = FPlan.objects.get(id=self.planid)
        # Auslesen der Kontaktstellen Informationen
        contacts = ContactOrganization.objects.filter(gemeinde__id__in=plan.gemeinde.values_list('id', flat=True)).distinct()
        responsible_orgas = plan.gemeinde
        cleaned_data = form.cleaned_data
        # Identifikation der EMail-Adressen der Sachbearbeiter
        toebs = cleaned_data.get("selected_toebs")
        # Zusätzliche Speicherung in json - ggf. später als Protokoll
        # 
        result = []
        for toeb in toebs:
            result_toeb = {}
            result_toeb['name'] = str(toeb)
            result_toeb['email'] = []
            # Eine EMail pro TOEB - es kann sein, dass ein User mehrere Mails bekommt, wenn er für mehrere TOEBs die Rolle Reporter hat!
            if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https']:
                direct_url = self.request.build_absolute_uri(reverse("beteiligungbeitrag-toeb-create", args=[self.plantyp, self.planid, beteiligung.id, toeb.id])).replace('http://', 'https://')
            else:
                direct_url = self.request.build_absolute_uri(reverse("beteiligungbeitrag-toeb-create", args=[self.plantyp, self.planid, beteiligung.id, toeb.id]))
            if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https']:
                list_url = self.request.build_absolute_uri(reverse("toebbeteiligungen-list")).replace('http://', 'https://')
            else:
                list_url = self.request.build_absolute_uri(reverse("toebbeteiligungen-list"))
            direct_link = f"{direct_url}"
            list_link = f"{list_url}"
            subject = str("Benachrichtigung zur " + beteiligung.get_typ_display() + " vom " + datetime.today().strftime('%Y-%m-%d') + " - Frist: " + str(beteiligung.end_datum) )
            html_content = render_to_string("xplanung_light/email/toeb_benachrichtigung.html", context={"plan": plan, "beteiligung": beteiligung, "direct_link": direct_link, "list_link": list_link, "contacts": contacts, "orgas": responsible_orgas, "toeb": toeb, "metadata_contact": settings.XPLANUNG_LIGHT_CONFIG['metadata_contact'],},)
            text_content = render_to_string("xplanung_light/email/toeb_benachrichtigung.txt", context={"plan": plan, "beteiligung": beteiligung, "direct_link": direct_link, "list_link": list_link, "contacts": contacts,  "orgas": responsible_orgas, "toeb": toeb, "metadata_contact": settings.XPLANUNG_LIGHT_CONFIG['metadata_contact'],},)
            for editor in toeb.editors.all():
                if editor.user.email:
                    result_toeb['email'].append(editor.user.email)
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=text_content,
                        from_email=settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],
                        to=[str(editor.user.email),],
                        #bcc=[str(farmshop.contact_email),],
                        reply_to=[settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],]
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send(fail_silently=True)
            result.append(result_toeb)
        result_json = json.dumps(result)
        #print(result_json)
        form.instance.protocol = result
        form.instance.end = timezone.now()
        # ...
        return super().form_valid(form)
    
    def get_success_url(self):
        """
        Wenn das Versenden erfolgreich war, wird auf die Liste der Notifications
        weitergeleitet.
        """
        return reverse_lazy("beteiligungnotification-list", kwargs={'plantyp': self.plantyp, 'planid': self.planid, 'beteiligungid': self.beteiligungid})
    

