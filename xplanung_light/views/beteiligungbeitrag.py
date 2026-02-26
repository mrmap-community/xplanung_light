from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang, AdministrativeOrganization
from xplanung_light.models import FPlanBeteiligung, FPlan, FPlanBeteiligungBeitrag
from xplanung_light.models import ConsentOption
from xplanung_light.forms import BPlanBeteiligungBeitragForm
from django.views.generic import CreateView, ListView, DeleteView, DetailView, UpdateView
from formset.views import FormViewMixin, FormCollectionView, EditCollectionView #, CreateCollectionView
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungBeitragTable, FPlanBeteiligungBeitragTable
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import BPlanBeteiligungCollection, FPlanBeteiligungCollection
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import json
from django.core.exceptions import PermissionDenied
from django.db.models import Subquery, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.core.mail import send_mail, EmailMessage
from django.utils.timezone import datetime
from django.conf import settings

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
        print(f"Typ: {self.plantyp}")
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


class BPlanBeteiligungBeitragDeleteView(SuccessMessageMixin, DeleteView):
    """
    Löschen eines BeteiligungsBeitrag-Records.

    """
    model = BPlanBeteiligungBeitrag
    reference_model = BPlan
    model_name_lower = str(model._meta.model_name).lower()
    success_message = "Beteiligungsbeitrag wurde gelöscht!"

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
                        return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid'])
            raise PermissionDenied("Nutzer hat keine Berechtigungen auf die angeforderten Objekte!")
        else:
            return qs.filter(bplan_beteiligung_id=self.kwargs['beteiligungid'])

    def form_valid(self, form):
        self.success_url = reverse_lazy('bplanbeteiligungbeitrag-list', kwargs={'planid': self.kwargs['planid'], 'beteiligungid': self.kwargs['beteiligungid']})
        return super().form_valid(form)
    

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
            self.reference_model = FPlanPlan
        self.planid = self.kwargs.get('planid') 
            #self.template_name = 'xplanung_light/beteiligungbeitrag_list.html'
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
        # Debugausgabe
        print(f"Typ: {self.plantyp}, ID: {self.planid}")
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
            if self.plantyp == 'bplan':
                activation_url = reverse("bplanbeteiligungbeitrag-activate", args=[planid, self.object.id, beitrag_generic_id])
            if self.plantyp == 'fplan':
                activation_url = None
            # Build complete URLs
            #https://opensource.com/article/22/12/django-send-emails-smtp
            #
            activation_link = f"{activation_url}"
            email = EmailMessage(
                subject=str("Ihre Stellungnahme von " + datetime.today().strftime('%Y-%m-%d') + " zum Plan " + str(planname)),
                body=str("Vielen Dank für Ihre Stellungnahme.\n" \
                "Sie müssen die Stellungnahme noch bestätigen:\n"
                 + self.request.scheme + "://" + self.request.get_host() + activation_link + "\n"
                # + "Dein Team vom " + str(farmshop.title) + "\n" 
                 + "Für telefonische Rückfragen: " + str('test')),
                from_email='test@example.com',
                to=[str(self.object.comments.last().email),],
                #bcc=[str(farmshop.contact_email),],
                reply_to=[str('user@example.com'),]
            )
            email.content_subtype = "html"
            email.send(fail_silently=True)
            # save generic_id to session - where to get it from? - it is not in the database till now!
            self.request.session["beitrag_generic_id"] = str(beitrag_generic_id)
        return result
    

class BPlanBeteiligungBeitragDetailView(DetailView):
    """
    View für die Details zum Beteiligungsbeitrag. Soll nur für den Ersteller und die zuständigen Bearbeiter sichtbar sein!
    Für die Ersteller brauchen wir eine spezielle function based view - damit wir den redirect handhaben können.

    """
    model = BPlanBeteiligungBeitrag
    template_name = 'xplanung_light/bplanbeteiligungbeitrag_detail.html'

    def get_queryset(self):
        qs = super().get_queryset()
        # Zunächst nur admins der Gebietskörperschaften oder superuser
        gemeinden = AdministrativeOrganization.objects.filter(bplan__beteiligungen__comments__in=[self.kwargs['pk']])
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
        print(str(qs.get(pk=self.kwargs['pk']).generic_id))
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
        if 'orga_id' in self.kwargs.keys():
            orga = AdministrativeOrganization.objects.get(pk=self.kwargs['orga_id'])
            context["orga"] = orga
        return context
    
class BeteiligungBeitragDetailView(DetailView):
    """
    View für die Details zum Beteiligungsbeitrag. Soll nur für den Ersteller und die zuständigen Bearbeiter sichtbar sein!
    Für die Ersteller brauchen wir eine spezielle function based view - damit wir den redirect handhaben können.

    """
    model = BPlanBeteiligungBeitrag
    template_name = 'xplanung_light/bplanbeteiligungbeitrag_detail.html'

    def dispatch(self, request, *args, **kwargs):
        # Hier sind die Parameter aus der re_path verfügbar:
        self.plantyp = kwargs.get('plantyp')
        if self.kwargs.get('plantyp') == 'bplan':
            self.model = BPlanBeteiligung
            self.planmodel = BPlan
            self.template_name = 'xplanung_light/bplanbeteiligungbeitrag_detail.html'
            if "orga_id" in kwargs.keys():
                self.orga_id = kwargs.get('orga_id')
        #TODO: Anpassen für FPlan
        self.planid = kwargs.get('planid')
        self.beteiligung_pk = kwargs.get('pk')
        # Debugausgabe
        print(f"Typ: {self.plantyp}, ID: {self.planid}")
        return super().dispatch(request, *args, **kwargs)


    def get_queryset(self):
        qs = super().get_queryset()
        # Zunächst nur admins der Gebietskörperschaften oder superuser
        if self.plantyp == 'bplan':
            gemeinden = AdministrativeOrganization.objects.filter(bplan__beteiligungen__comments__in=[self.kwargs['pk']])
        else:
            gemeinden = None
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
        print(str(qs.get(pk=self.kwargs['pk']).generic_id))
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
        if 'orga_id' in self.kwargs.keys():
            orga = AdministrativeOrganization.objects.get(pk=self.kwargs['orga_id'])
            context["orga"] = orga
        return context
    

class BPlanBeteiligungBeitragActivate(UpdateView):
    model = BPlanBeteiligungBeitrag
    #template_name = 'xplanung_light/bplanbeteiligungbeitrag_activate.html'


    pass