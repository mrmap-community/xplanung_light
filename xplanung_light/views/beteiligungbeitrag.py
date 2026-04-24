from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang, AdministrativeOrganization
from xplanung_light.models import FPlanBeteiligung, FPlan, FPlanBeteiligungBeitrag, ContactOrganization
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import ConsentOption
from xplanung_light.forms import BPlanBeteiligungBeitragForm
from xplanung_light.forms import BPlanBeteiligungGenericCollection, FPlanBeteiligungGenericCollection
from xplanung_light.forms import BPlanBeteiligungBeitragGenericCollection, FPlanBeteiligungBeitragGenericCollection
from django.views.generic import CreateView, ListView, DeleteView, DetailView, UpdateView
from formset.views import FormViewMixin, FormCollectionView, EditCollectionView
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungBeitragTable, FPlanBeteiligungBeitragTable
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import BPlanBeteiligungCollection, FPlanBeteiligungCollection
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


class XPlanBeteiligungBeitragCreateView(CreateView):
    """
    Anlagen eines BPlanBeteiligungBeitrag-Datensatzes über Formular.

    """
    #form_class = BPlanCreateForm


class BeteiligungBeitragListView(SingleTableView):
    """
    ListView zur Anzeige der BeteiligungBeitrag-Records. Hier Die Klasse entscheidet je nach URL, um welchen Plantyp es sich handelt.

    """
    # Default Werte für Initialiisierung - werden durch dispatch Funktion überschrieben
    model = BPlanBeteiligungBeitrag
    parent_model = BPlanBeteiligung
    reference_model = BPlan
    table_class = BPlanBeteiligungBeitragTable
    reference_model_name_lower = 'bplan'
    
    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungBeitrag
            self.parent_model = BPlanBeteiligung
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungBeitrag
            self.parent_model = FPlanBeteiligung
            self.table_class = FPlanBeteiligungBeitragTable
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beteiligungbeitrag_list.html'
        #TODO: Anpassen für FPlan
        self.beteiligungid = kwargs.get('beteiligungid')
        # Debugausgabe
        #print(f"Typ: {self.plantyp}")
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
                ).annotate(
                    count_stellungnahmen=Count(
                        'stellungnahmen', distinct=True
                    )
        )
        plan = self.reference_model.objects.get(pk=self.kwargs['planid'])
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:   
                        # Zugriff wird erteilt
                        if self.plantyp == 'bplan':                    
                            return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
                        if self.plantyp == 'fplan':                    
                            return qs.filter(fplan_beteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
            raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
        else:
            if self.plantyp == 'bplan': 
                return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')
            if self.plantyp == 'fplan': 
                return qs.filter(fplan_beteiligung_id=self.kwargs['beteiligungid']).order_by('-last_changed')


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
        return context


class BeteiligungBeitragDeleteView(SuccessMessageMixin, DeleteView):
    """
    Löschen eines BeteiligungsBeitrag-Records.

    """
    model = BPlanBeteiligungBeitrag
    reference_model = BPlan
    model_name_lower = str(model._meta.model_name).lower()
    success_message = "Beteiligungsbeitrag wurde gelöscht!"

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungBeitrag
            self.reference_model = BPlan
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungBeitrag
            self.reference_model = FPlan
        self.planid = self.kwargs.get('planid') 
        self.template_name = 'xplanung_light/beteiligungbeitrag_confirm_delete.html'
        #TODO: Anpassen für FPlan
        self.beteiligungid = kwargs.get('beteiligungid')
        # Debugausgabe
        print(f"Typ: {self.plantyp}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        """
        Docstring for get_queryset
        
        :param self: Description
        :param kwargs: Description
        """
        qs = super().get_queryset()
        plan = self.reference_model.objects.get(pk=self.kwargs['planid'])
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:   
                        # Zugriff wird erteilt 
                        if self.plantyp == 'bplan':                    
                            return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid'])
            raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
        else:
            if self.plantyp == 'bplan':  
                return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid'])

    def form_valid(self, form):
        self.success_url = reverse_lazy('beteiligungbeitrag-list', kwargs={'plantyp': self.plantyp, 'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return super().form_valid(form)

    
class BeteiligungBeitragCreateView(EditCollectionView):
    """
    View für Abbildung des kombinierten Fomulars über django-formsets EditCollectionView
    https://django-formset.fly.dev/model-collections/

    """
    # Initialisierung der Attribute - werden in dispatch Funktion überschrieben!
    plantyp = None
    model = BPlanBeteiligung
    collection_class = BPlanBeteiligungCollection
    planmodel = None
    beteiligung_pk = None
    orga_id = None
    template_name = 'xplanung_light/beteiligungbeitrag_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligung
            self.planmodel = BPlan
            self.collection_class = BPlanBeteiligungCollection
            self.template_name = 'xplanung_light/beteiligungbeitrag_form.html'
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligung
            self.planmodel = FPlan
            self.collection_class = FPlanBeteiligungCollection
            self.template_name = 'xplanung_light/beteiligungbeitrag_form.html'
        if "orga_id" in kwargs.keys():
            self.orga_id = kwargs.get('orga_id')
        #TODO: Anpassen für FPlan
        self.planid = kwargs.get('planid')
        self.beteiligung_pk = kwargs.get('pk')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """
        Überschreiben der Initialisierung um einen Zusatzparameter abzufangen, der erlaubt mitzubekommen, über welche Gebietskörperschaft das 
        Formular angefragt wurde. Da ein Plan von mehreren Gebietskörperschaften publiziert werden kann, ist das sonst nicht eindeutig.
        
        :param self: Description
        """
        # Ausgabe der aktuellen Session variablen:
        #for key, value in self.request.session.items():
        #    print(key + ': ' + value)

        if 'orga_id' in self.kwargs.keys():
            self.success_url = reverse('organization-bauleitplanung-list', kwargs={'pk': self.kwargs['orga_id']})
        else:
            self.success_url = reverse('beteiligungbeitrag-list', kwargs={'plantyp': self.kwargs['plantyp'], 'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['pk']})
        return super().get_initial()
    
    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben, weil wir die Stellungnahmen nur für Pläne ermöglichen, für die
        der Anbieter das zugelassen hat.
        
        :param self: Description
        :param kwargs: Description
        """
        context = super().get_context_data(**kwargs)
        context["plantyp"] = self.kwargs['plantyp']
        context["plan"] = self.planmodel.objects.get(pk=self.kwargs['planid'])
        # try except logic
        beteiligung = None
        try:
            beteiligung = self.model.objects.get(pk=self.kwargs['pk'], allow_online_beitrag=True)
        except:
            pass
        context["beteiligung"] = beteiligung
        if 'orga_id' in self.kwargs.keys():
            orga = AdministrativeOrganization.objects.get(pk=self.kwargs['orga_id'])
            context["orga"] = orga
        consent_options = None
        try:
            today = datetime.now().date()
            consent_options = ConsentOption.objects.filter(obsolete=False, mandatory=True, valid_from__lte=today, valid_until__gte=today, type='commentator')
        except:
            pass
        context["consent_options"] = consent_options
        return context

    def form_collection_invalid(self, form_collection):
        if 'captcha' in form_collection._errors['captcha'].keys():
            form_collection._errors['captcha']['captcha_1'] = form_collection._errors['captcha']['captcha']
        return JsonResponse(form_collection._errors, status=422, safe=False)
    
    def form_collection_valid(self, form_collection):
        result = super().form_collection_valid(form_collection)
        # Nach der Speicherung
        if result:
            beitrag_generic_id = self.object.comments.last().generic_id
            if self.plantyp == 'bplan':
                planid = self.object.bplan.id
                planname = self.object.bplan.name
            if self.plantyp == 'fplan':
                planid = self.object.fplan.id
                planname = self.object.fplan.name
            # Benachrichtigung des Nutzers mit Link zur Aktivierung
            # Die gespeicherte Instanz (object) beinhaltet alle beitragsobjekte - nicht nur den konkreten Beitrag 
            # Bauen des Aktivierungslinks
            if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https']:
                activation_url = self.request.build_absolute_uri(reverse("beteiligungbeitrag-activate", args=[self.plantyp, planid, self.object.id, beitrag_generic_id])).replace('http://', 'https://')
            else:
                activation_url = self.request.build_absolute_uri(reverse("beteiligungbeitrag-activate", args=[self.plantyp, planid, self.object.id, beitrag_generic_id]))
            # Build complete URLs
            #https://opensource.com/article/22/12/django-send-emails-smtp
            #
            if self.plantyp == 'bplan':
                plan = BPlan.objects.get(id=planid)
            if self.plantyp == 'fplan':
                plan = FPlan.objects.get(id=planid)
            # Auslesen der Kontaktstellen Informationen
            contacts = ContactOrganization.objects.filter(gemeinde__id__in=plan.gemeinde.values_list('id', flat=True)).distinct()
            activation_link = f"{activation_url}"
            subject = str("Ihre Online-Stellungnahme vom " + datetime.today().strftime('%Y-%m-%d') + " zum Plan \"" + str(planname) + "\"")
            html_content = render_to_string("xplanung_light/email/beteiligungsbeitrag_activate.html", context={"end_datum": self.object.end_datum.strftime('%Y-%m-%d'), "activation_link": activation_link, "contacts": contacts, "metadata_contact": settings.XPLANUNG_LIGHT_CONFIG['metadata_contact'],},)
            text_content = render_to_string("xplanung_light/email/beteiligungsbeitrag_activate.txt", context={"end_datum": self.object.end_datum.strftime('%Y-%m-%d'), "activation_link": activation_link, "contacts": contacts, "metadata_contact": settings.XPLANUNG_LIGHT_CONFIG['metadata_contact'],},)
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],
                to=[str(self.object.comments.last().email),],
                #bcc=[str(farmshop.contact_email),],
                reply_to=[settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email'],]
            )
            #email.content_subtype = "text"
            email.attach_alternative(html_content, "text/html")

            email.send(fail_silently=True)
            # TODO: Kontakstellen über eingegangene Beteiligung informieren

            # save generic_id to session - where to get it from? - it is not in the database till now!
            self.request.session["beitrag_generic_id"] = str(beitrag_generic_id)
        return result
    

class BeteiligungBeitragGenericCreateView(FormCollectionView):
    """
    Der generische CreateView ist für die Sachbearbeiter gedacht und dient zur Erfassung der Beiträge die
    nicht über das Online-Formular erfasst wurden. 
    In django-formset 1.7.8 gibt es noch keine CreateCollectionView, man muss das Speichern selbst implementieren.
    """
    # Initialisierung der Attribute - werden in dispatch Funktion überschrieben!
    plantyp = None
    # Modell der zu erstellenden Instanz
    model = BPlanBeteiligungBeitrag
    # Modell des Beteiligungsverfahrens zu der der Beitrag eingereicht wird
    model_parent = BPlanBeteiligung
    # django-formset CollectionClass für das dynamsiche Formular
    collection_class = BPlanBeteiligungCollection
    planmodel = None
    reference_model_name_lower = None
    beteiligung_pk = None
    template_name = 'xplanung_light/beteiligungbeitrag_generic_form.html'
    extra_context = None

    def get_initial(self):
        """
        :param self: Description
        """
        # 'beitrag' ist der Name der Form in Ihrer Collection
        # 'beteiligung' ist das Feld des Foreign Keys
        initial = super().get_initial()
        #print(initial)
        initial.update({
            'beitrag': {
                self.kwargs['plantyp'] + "_" + 'beteiligung': str(self.kwargs['beteiligungid'])
            }
        })
        # Url zu der nach dem Erstellen der Instanz weitergeleitet wird
        self.success_url = reverse('beteiligungbeitrag-list', kwargs={'plantyp': self.kwargs['plantyp'], 'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return initial

    def dispatch(self, request, *args, **kwargs):
        """
        Hier sind die Parameter aus der re_path verfügbar. Die Klasse wird je nach Plantyp abgeändert.
        """
        self.beteiligung_pk = kwargs.get('beteiligungid')
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungBeitrag
            self.model_parent = BPlanBeteiligung
            self.planmodel = BPlan
            self.reference_model_name_lower = 'bplan'
            self.collection_class = BPlanBeteiligungBeitragGenericCollection
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungBeitrag
            self.model_parent = FPlanBeteiligung
            self.planmodel = FPlan
            self.reference_model_name_lower = 'fplan'
            self.collection_class = FPlanBeteiligungBeitragGenericCollection
        self.planid = kwargs.get('planid')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben, um weitere Informationen (Plan/Beteiligung) in das Formular zu übernehmen und 
        um auf den Plantyp reagieren zu können.
        
        :param self: Description
        :param kwargs: Description
        """
        context = super().get_context_data(**kwargs)
        context["plantyp"] = self.kwargs['plantyp']
        plan = self.planmodel.objects.get(pk=self.kwargs['planid'])
        context["plan"] = plan
        #debug
        #print("get_context_data: plan name: " + plan.name)
        beteiligung = None
        try:
            beteiligung = self.model_parent.objects.get(pk=self.kwargs['beteiligungid'])
        except:
            pass
        context["beteiligung"] = beteiligung
        # Extra Context - hier wird definiert, ob create oder update aufgerufen wurde
        context['extra_context'] = self.extra_context
        # Berechtigungsprüfung
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                         context[self.reference_model_name_lower] = plan
                         return context
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        # Übergabe des Planobjekts - warum unter bplan/fplan - kann ggf. raus
        context[self.reference_model_name_lower] = plan
        return context
    
    # Zum testen, was als json übetragen wird
    #def post(self, request, *args, **kwargs):
        # Die Daten liegen im Body des Requests
        #raw_data = json.loads(request.body)
        #print(raw_data)  # JSON-Objekt
        #return super().post(request, *args, **kwargs)

    def form_collection_valid(self, form_collection):
        """
        In der älteren Version von django-formset - 1.7.8 muss man das Objekt noch 
        eigenständig abspeichern.
        """
        parent_pk = self.kwargs.get('beteiligungid')
        holders = form_collection.valid_holders
        # 1. Hauptobjekt speichern
        # Ersetze 'beitrag_form' durch den Namen in deiner Haupt-Collection
        beitrag_form = holders.get('beitrag')
        beitrag_instance = None
        if beitrag_form:
            if beitrag_form.instance.pk:
                # Der Beitrag wird immer neu angelegt
                beitrag_form.instance.pk = None
                beitrag_form.instance._state.adding = True
            beitrag_instance = beitrag_form.save(commit=False)
            # Überschrieben der beteiligungsid (zur Sicherheit - hier braucht man eine instanz, keine id!):
            #setattr(beitrag_instance, self.plantyp + '_beteiligung', parent_pk)
            # beitrag_instance.parent_id = parent_pk 
            beitrag_instance.save()
            beitrag_form.save_m2m()
            #print(f"Beitrag gespeichert: ID {beitrag_instance.pk}")
             # 2. Anhänge speichern
            anhang_collection_holder = holders.get('attachments') # Name in deiner Haupt-Collection
            # Wenn es keine Liste ist, hat es ein eigenes valid_holders Attribut
            if hasattr(anhang_collection_holder, 'valid_holders'):
                # Bei Collections mit siblings ist valid_holders oft eine Liste von Dicts
                siblings = anhang_collection_holder.valid_holders
                # Jetzt prüfen, ob diese 'valid_holders' die Liste sind
                if isinstance(siblings, list):
                    for sib_dict in siblings:
                        # 'attachment' ist der Name in BeteiligungBeitragAnhangCollection
                        form = sib_dict.get('attachment')
                        if form:
                            instance = form.save(commit=False)
                            instance.beitrag = beitrag_instance
                            instance.save()
                else:
                    # Falls es doch eine einfache Collection ohne Siblings ist
                    form = siblings.get('attachment')
                    if form:
                        instance = form.save(commit=False)
                        instance.beitrag = beitrag_instance
                        instance.save()
            return super().form_collection_valid(form_collection)


class BeteiligungBeitragGenericUpdateView(EditCollectionView):
    """
    Der generische CreateView ist für die Sachbearbeiter gedacht und dient zur Erfassung der Beiträge die
    nicht über das Online-Formular erfasst wurden. pk ist in Url vorhanden.
    """
    # Initialisierung der Attribute - werden in dispatch Funktion überschrieben!
    plantyp = None
    model = BPlanBeteiligungBeitrag
    beteiligung_model = BPlanBeteiligung
    collection_class = BPlanBeteiligungGenericCollection
    reference_model_name_lower = 'bplan'
    planmodel = None
    beteiligung_pk = None
    template_name = 'xplanung_light/beteiligungbeitrag_generic_form.html'
    extra_context = None

    def get_initial(self):
        """
        :param self: Description
        """
        self.success_url = reverse('beteiligungbeitrag-list', kwargs={'plantyp': self.kwargs['plantyp'], 'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return super().get_initial()

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligungBeitrag
            self.beteiligung_model = BPlanBeteiligung
            self.planmodel = BPlan
            self.reference_model_name_lower = 'bplan'
            self.collection_class = BPlanBeteiligungBeitragGenericCollection
        if self.kwargs.get('plantyp') == 'fplan':
            self.model = FPlanBeteiligungBeitrag
            self.beteiligung_model = FPlanBeteiligung
            self.planmodel = FPlan
            self.reference_model_name_lower = 'fplan'
            self.collection_class = FPlanBeteiligungBeitragGenericCollection
        #TODO: Anpassen für FPlan
        self.planid = kwargs.get('planid')
        self.beteiligung_pk = kwargs.get('beteiligungid')
        self.pk = kwargs.get('pk')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben, weil wir die Stellungnahmen nur für Pläne ermöglichen, für die
        der Anbieter das zugelassen hat.
        
        :param self: Description
        :param kwargs: Description
        """
        context = super().get_context_data(**kwargs)
        context["plantyp"] = self.kwargs['plantyp']
        plan = self.planmodel.objects.get(pk=self.kwargs['planid'])
        context["plan"] = plan
        beteiligung = None
        try:
            beteiligung = self.beteiligung_model.objects.get(pk=self.kwargs['beteiligungid'])
        except:
            pass
        context["beteiligung"] = beteiligung
        #context["beitrag"] = self.get_object()
        context['extra_context'] = self.extra_context
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in plan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                         context[self.reference_model_name_lower] = plan
                         return context
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        context[self.reference_model_name_lower] = plan
        return context
    
    # Zum testen, was als json übetragen wird
    """
    def post(self, request, *args, **kwargs):
        # Die Daten liegen im Body des Requests
        raw_data = json.loads(request.body)
        print(raw_data)  # JSON-Objekt
        return super().post(request, *args, **kwargs)
    """


class BeteiligungBeitragDetailView(DetailView):
    """
    View für die Details zum Beteiligungsbeitrag. Soll nur für den Ersteller und die zuständigen Bearbeiter sichtbar sein!
    Für die Ersteller brauchen wir eine spezielle function based view - damit wir den redirect handhaben können.

    """
    model = BPlanBeteiligungBeitrag
    template_name = 'xplanung_light/beteiligungbeitrag_detail.html'

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        if self.plantyp == 'bplan':
            self.model = BPlanBeteiligungBeitrag
            self.planmodel = BPlan
            #self.template_name = 'xplanung_light/bplanbeteiligungbeitrag_detail.html'
        if self.plantyp == 'fplan':
            self.model = FPlanBeteiligungBeitrag
            self.planmodel = FPlan
            #self.template_name = 'xplanung_light/beteiligungbeitrag_detail.html'
        if "orga_id" in kwargs.keys():
            self.orga_id = kwargs.get('orga_id')
        else:
            self.orga_id = None
        #TODO: Anpassen für FPlan
        self.planid = kwargs.get('planid')
        self.beteiligung_pk = kwargs.get('pk')
        # Debugausgabe
        print("BeteiligungBeitragDetailView - dispatch")
        print(f"Typ: {self.plantyp}, ID: {self.planid}")
        return super().dispatch(request, *args, **kwargs)


    def get_queryset(self):
        qs = super().get_queryset()
        # Zunächst nur admins der Gebietskörperschaften oder superuser
        if self.plantyp == 'bplan':
            gemeinden = AdministrativeOrganization.objects.filter(bplan__beteiligungen__comments__in=[self.kwargs['pk']])
        if self.plantyp == 'fplan':
            gemeinden = AdministrativeOrganization.objects.filter(fplan__beteiligungen__comments__in=[self.kwargs['pk']])
        access_allowed = False
        if self.request.user.is_superuser == False:
            for gemeinde in gemeinden:
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:   
                        # Zugriff wird erteilt                     
                        access_allowed = True
        else:
            access_allowed = True
        # Außerdem kann ein Nutzer den Beitrag sehen, wenn er sich vorher authentifiziert hat - Test, ob beitrag_generic_id in session des users
        # TODO - andere Views für edit und delete erstellen! - Per generic_id und vorheriger Authentifizierung
        #print(str(qs.get(pk=self.kwargs['pk']).generic_id))
        if 'beitrag_generic_id' in self.request.session.keys():
            print("session['beitrag_generic_id']: " + self.request.session['beitrag_generic_id'])
        else:
            print("session['beitrag_generic_id'] not defined!")
        if self.request.user.is_anonymous:
            if 'beitrag_generic_id' in self.request.session.keys():
                if self.request.session['beitrag_generic_id'] == str(qs.get(pk=self.kwargs['pk']).generic_id):
                    print('beitrag id steht in session!')
                    access_allowed = True
        if not access_allowed:
            #return redirect("bplanbeteiligungbeitrag-authenticate", planid=self.kwargs['planid'], beteiligungid=self.kwargs['beteiligungid'], generic_id=str(qs.get(pk=self.kwargs['pk']).generic_id))
            # Have to return an instance - nicht wie eine function based view!
            # raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
            qs = qs.filter(pk=0)
        qs = qs.annotate(
                    last_changed=Subquery(
                        self.model.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )
                )
        return qs

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben, weil wir ggf. noch die Organisation aus der URL hinzunehmen müssen. 
        Die ist nicht immer eindeutig - je nachdem über welchen Endpunkt der Nutzer eingestiegen ist.
        
        :param self: Description
        :param kwargs: Description
        """
        context = super().get_context_data(**kwargs)

        context['plantyp'] = self.plantyp
        if self.orga_id:
            orga = AdministrativeOrganization.objects.get(pk=self.orga_id)
            context["orga"] = orga
        context['beitrag'] = self.object
        context['plantyp'] = self.plantyp
        if self.plantyp =='bplan':
            context['beteiligung'] = self.object.bplan_beteiligung
            context['plan'] = self.object.bplan_beteiligung.bplan
        if self.plantyp =='fplan':
            context['beteiligung'] = self.object.fplan_beteiligung
            context['plan'] = self.object.fplan_beteiligung.fplan
        return context
