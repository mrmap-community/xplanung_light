from datetime import timedelta, datetime
from django.utils import timezone
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User 
from xplanung_light.models import BPlan, BPlanSpezExterneReferenz, BPlanBeteiligung, AdministrativeOrganization, Uvp, FPlanUvp
from xplanung_light.models import FPlan, FPlanSpezExterneReferenz, FPlanBeteiligung, FPlanBeteiligungBeitrag, FPlanBeteiligungBeitragAnhang
from xplanung_light.models import ContactOrganization, ToebUnit, AdminOrgaUser, RequestForRole
from xplanung_light.models import BPlanBeteiligungToebNotification, FPlanBeteiligungToebNotification
from xplanung_light.models import BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang
from xplanung_light.models import BPlanBeitragStellungnahme, FPlanBeitragStellungnahme
from xplanung_light.models import ConsentOption
from xplanung_light.validators import fplan_upload_file_validator, geotiff_raster_validator, bplan_content_validator, fplan_content_validator, bplan_upload_file_validator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, Field
from crispy_forms.bootstrap import TabHolder, Tab, AccordionGroup, Accordion
from django.forms import ModelForm
from django_select2.forms import Select2MultipleWidget, Select2Widget
from dal import autocomplete
from formset.richtext.widgets import RichTextarea
from formset.widgets import DateInput, DateTimeInput, DatePicker
from captcha.fields import CaptchaField
from formset.utils import FormMixin
from django.core.exceptions import ValidationError
from django_clamd.validators import validate_file_infection
from django.utils.timezone import now
import uuid
from django.db.models import Case, When, Value, CharField, Count
from django.db.models.functions import Concat
#from django.db.models import CharField
#from formset.utils import FormMixin

class BPlanImportForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen Plan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="BPlan GML", validators=[bplan_content_validator, validate_file_infection])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanImportForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Bebauungsplan importieren", "file", "confirm"), Submit("submit", "Hochladen"))


class FPlanImportForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen Plan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="FPlan GML", validators=[fplan_content_validator, validate_file_infection])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(FPlanImportForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Flächennutzungsplan importieren", "file", "confirm"), Submit("submit", "Hochladen"))


class BPlanImportArchivForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen Plan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="BPlan ZIP-Archiv", validators=[bplan_upload_file_validator, validate_file_infection])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanImportArchivForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Bebauungsplanarchiv importieren", "file", "confirm"), Submit("submit", "Hochladen"))


class FPlanImportArchivForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen FPlan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="FPlan ZIP-Archiv", validators=[fplan_upload_file_validator, validate_file_infection])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(FPlanImportArchivForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Flächennutzungsplanarchiv importieren", "file", "confirm"), Submit("submit", "Hochladen"))


class BPlanSpezExterneReferenzForm(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanSpezExterneReferenzForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Anlage hochladen", "typ", "name", "attachment"), Submit("submit", "Hochladen/Aktualisieren"))

    # https://docs.djangoproject.com/en/5.2/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
    def clean(self):
        cleaned_data = super().clean()
        print(self.cleaned_data['typ'])
        # check if karte should be uploaded
        if cleaned_data['typ'] == '1070': # Karte
            # Validierung der Rasterdatei 
            test = geotiff_raster_validator(cleaned_data['attachment'])

    class Meta:
       model = BPlanSpezExterneReferenz
       fields = ["typ", "name", "attachment"] # list of fields you want from model


class FPlanSpezExterneReferenzForm(forms.ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(FPlanSpezExterneReferenzForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Anlage hochladen", "typ", "name", "attachment"), Submit("submit", "Hochladen/Aktualisieren"))

    # https://docs.djangoproject.com/en/5.2/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
    def clean(self):
        cleaned_data = super().clean()
        print(self.cleaned_data['typ'])
        # check if karte should be uploaded
        if cleaned_data['typ'] == '1070': # Karte
            # Validierung der Rasterdatei 
            test = geotiff_raster_validator(cleaned_data['attachment'])

    class Meta:
       model = FPlanSpezExterneReferenz
       fields = ["typ", "name", "attachment"] # list of fields you want from model


class BPlanBeteiligungFormOld(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanBeteiligungFormOld, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['bekanntmachung_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['start_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['end_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        #self.fields['beschreibung'].widget =
        
        
        self.helper.layout = Layout(
            Fieldset("Information zur Beteiligung / Offenlage", 
                "typ",
                Fieldset(
                    "Datumsfelder",
                    Row(
                        Column(
                            "bekanntmachung_datum",
                        ),
                        Column(
                            "start_datum",
                        ),
                        Column(
                            "end_datum",
                        ),
                    ),
                ),
                Fieldset(
                    "Weitere Informationen",
                    "allow_online_beitrag",
                    "beschreibung",
                    "publikation_internet",
                ),
            ),
            Submit("submit", "Anlegen/Aktualisieren")
        )
        
    class Meta:
       model = BPlanBeteiligung
       fields = ["typ", "bekanntmachung_datum", "start_datum", "end_datum", "allow_online_beitrag", "beschreibung", "publikation_internet"] # list of fields you want from model


class FPlanBeteiligungForOld(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(FPlanBeteiligungForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['bekanntmachung_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['start_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['end_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.helper.layout = Layout(
            Fieldset("Information zur Beteiligung / Offenlage", 
                "typ",
                Fieldset(
                    "Datumsfelder",
                    Row(
                        Column(
                            "bekanntmachung_datum",
                        ),
                        Column(
                            "start_datum",
                        ),
                        Column(
                            "end_datum",
                        ),
                    ),
                ),
                Fieldset(
                    "Weitere Informationen",
                    "publikation_internet",
                ),
            ),
            Submit("submit", "Anlegen/Aktualisieren")
        )
        

    class Meta:
       model = FPlanBeteiligung
       fields = ["typ", "bekanntmachung_datum", "start_datum", "end_datum", "publikation_internet"] # list of fields you want from model


"""
Formular zur Verwaltung von Informationen zu durchgeführten UVPs
"""
class UvpForm(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(UvpForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        #self.fields['bekanntmachung_datum'].widget = forms.DateInput(
        #    attrs={
        #        'type': 'date',
        #        'min': str((timezone.now() - timedelta(days=29200)).date()),
        #        'max': str(timezone.now().date() + timedelta(days=30)),
        #        }
        #)
        self.fields['uvp_beginn_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['uvp_ende_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.helper.layout = Layout(
            Fieldset("Information zur Umweltverträglichkeitsprüfung",      
                "typ",
                "uvp_vp",
                "uvp",
                Fieldset(
                    "Datumsfelder",
                    Row(
                        Column(
                            "uvp_beginn_datum",
                        ),
                        Column(
                            "uvp_ende_datum",
                        ),
                        #Column(
                        #    "end_datum",
                        #),
                    ),
                ),
                #Fieldset(
                #    "Weitere Informationen",
                #    "publikation_internet",
                #),
            ),
            Submit("submit", "Anlegen/Aktualisieren")
        )
        

    class Meta:
       model = Uvp
       fields = ["uvp", "uvp_vp", "typ", "uvp_beginn_datum", "uvp_ende_datum"] # list of fields you want from model


"""
Formular zur Verwaltung von Informationen zu durchgeführten UVPs
"""
class FPlanUvpForm(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(FPlanUvpForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        #self.fields['bekanntmachung_datum'].widget = forms.DateInput(
        #    attrs={
        #        'type': 'date',
        #        'min': str((timezone.now() - timedelta(days=29200)).date()),
        #        'max': str(timezone.now().date() + timedelta(days=30)),
        #        }
        #)
        self.fields['uvp'].label = "Umweltprüfung durchgeführt"
        #self.fields['uvp_vp'].label = "Vorprüfung durchgeführt"
        self.fields['uvp'].help_text = "Umweltprüfung durchgeführt"
        #self.fields['uvp_vp'].help_text = "Vorprüfung durchgeführt"

        self.fields['uvp_beginn_datum'].label = "Beginns UP"
        self.fields['uvp_ende_datum'].label = "Ende UP"
        self.fields['uvp_beginn_datum'].help_text = "Datum des Beginns der Umweltprüfung"
        self.fields['uvp_ende_datum'].help_text = "Datum des Beginns der Umweltprüfung"

        self.fields['uvp_beginn_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.fields['uvp_ende_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date() + timedelta(days=30)),
                }
        )
        self.helper.layout = Layout(
            Fieldset("Information zur Umweltprüfung",      
                "typ",
                "uvp_vp",
                "uvp",
                Fieldset(
                    "Datumsfelder",
                    Row(
                        Column(
                            "uvp_beginn_datum",
                        ),
                        Column(
                            "uvp_ende_datum",
                        ),
                        #Column(
                        #    "end_datum",
                        #),
                    ),
                ),
                #Fieldset(
                #    "Weitere Informationen",
                #    "publikation_internet",
                #),
            ),
            Submit("submit", "Anlegen/Aktualisieren")
        )
        

    class Meta:
       model = FPlanUvp
       fields = ["uvp", "typ", "uvp_beginn_datum", "uvp_ende_datum"] # list of fields you want from model


class RegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)
    captcha = CaptchaField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

# https://docs.djangoproject.com/en/5.2/ref/forms/fields/
# https://stackoverflow.com/questions/72004112/how-do-i-use-a-select2-multiple-select-in-a-django-crispy-form
class GemeindeSelect(forms.SelectMultiple):

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            option["attrs"]["bbox"] = value.instance.bbox
        return option

"""
Neue Klasse zur Verbesserung des Formulars der Zuordnung mehrerer Gebietskörperschaften zu einem 
XPlan. Ist abhängig von django-autocomplete-light und select2
"""
class GemeindeSelect2(autocomplete.ModelSelect2Multiple):

    def _init_(self):
        self.url = 'administrativeorganization-autocomplete'


    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            option["attrs"]["bbox"] = value.instance.bbox
        return option
    

class GemeindeSelect3(autocomplete.ModelSelect2Multiple):
    """
    Klasse für den Zugriff auf die Gemeinden ohne die Verwendung der Geometrien - macht das alles etwas schneller
    """
    def _init_(self):
        self.url = 'administrativeorganization-autocomplete'


    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        return option


class OrganizationSelect3Single(autocomplete.ModelSelect2):
    """
    Klasse für den Zugriff auf die Gemeinden ohne die Verwendung der Geometrien - macht das alles etwas schneller
    """
    def _init_(self):
        self.url = 'administrativeorganization-autocomplete'


    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        return option


"""
Neue Klasse zur Verbesserung des Formulars der Zuordnung mehrerer Gebietskörperschaften zu einem 
XPlan. Ist abhängig von django-autocomplete-light und select2
"""
class OrganizationSelect2Single(autocomplete.ModelSelect2):

    def _init_(self):
        self.url = 'administrativeorganization-autocomplete'


    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            option["attrs"]["bbox"] = value.instance.bbox
        return option
    


class BPlanCreateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # https://medium.com/@azzouzhamza13/django-crispy-forms-bootstrap5-00a1eb3ec3c7
        # https://www.youtube.com/watch?v=MZwKoi0wu2Q
        # Validation Problem: https://github.com/django-crispy-forms/django-crispy-forms/issues/623
        # https://stackoverflow.com/questions/64581369/django-crispy-forms-validation-error-in-template
        self.fields['aufstellungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['satzungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['rechtsverordnungs_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['ausfertigungs_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['inkrafttretens_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['untergangs_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': '1960-01-01',
                'max': str(timezone.now().date()),
                }
        )
        # https://forum.djangoproject.com/t/model-choice-field-how-to-add-attributes-to-the-options/37782
        # https://django-autocomplete-light.readthedocs.io/en/master/_modules/dal_select2/widgets.html#ModelSelect2Multiple
        # mixin - erbt von 3 Kassen !
        # alter Weg (einfache Select option Liste):
        # self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
        # Neuer Weg - django-autocomplete-light/select2
        self.fields['gemeinde'].widget = GemeindeSelect2(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        """
        self.helper.layout = Layout(
            TabHolder(
                Tab(
                    "Grunddaten",
                    "gemeinde",
                    "name",
                    "geltungsbereich",
                    "nummer",
                    "planart",
                    ),
                Tab(
                    "Datumsfelder",
                    "inkrafttretens_datum",
                    ),  
                Tab(
                    "Checkboxen",
                    "staedtebaulicher_vertrag",
                    ),   
                ),
                Submit("submit", "Erstellen")
            )
        """
        self.helper.layout = Layout(
            Fieldset(
                "Verwaltung",
                Row(
                    "public",
                ),
            ),
            Fieldset(
                
                "Pflichtfelder XPlanung",
                Row(
                    Column(
                        Field("gemeinde"),
                        "name",
                        "planart",
                        Fieldset(
                            "Pflichtfeld XPlanung-light",
                            Row(
                                "nummer",
                        )),
                    ),
                    Column(
                        "geltungsbereich",
                    ),
                ),
            ),
            Fieldset(
                "Weitere Informationen",
                Row(
                    "massstab",
                ),
                Row(
                    "beschreibung",
                ),
            ),    
            Fieldset(
                "Datumsfelder",
                Row(
                    Column(
                        "aufstellungsbeschluss_datum",
                    ),
                    Column(
                        "satzungsbeschluss_datum",
                    ),
                    Column(
                        "rechtsverordnungs_datum",
                    ),
                    Column(
                        "ausfertigungs_datum",
                    ),
                    Column(
                        "inkrafttretens_datum",
                    ),
                    Column(
                        "untergangs_datum",
                    ),
                ),
            ),
            Fieldset(
                "Marker",
                Row(
                    Column(
                        "staedtebaulicher_vertrag",
                    ),
                    Column(
                        "erschliessungs_vertrag",
                    ),
                    Column(
                        "durchfuehrungs_vertrag",
                    ),
                    Column(
                        "gruenordnungsplan",
                    ),
                ),
            ), 
            Submit("submit", "Erstellen")
        )

    class Meta:
        model = BPlan
        fields = ["name", 
                  "nummer", 
                  "public",
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "massstab",
                  "beschreibung",
                  "aufstellungsbeschluss_datum", 
                  "satzungsbeschluss_datum",
                  "rechtsverordnungs_datum",
                  "ausfertigungs_datum",
                  "inkrafttretens_datum", 
                  "untergangs_datum",
                  "staedtebaulicher_vertrag",
                  "erschliessungs_vertrag",
                  "durchfuehrungs_vertrag",
                  "gruenordnungsplan",
                ]
        # alternative to invokation above - but no possibility to have further attributes?
        #widgets = {
        #    'gemeinde': autocomplete.ModelSelect2Multiple(url='administrativeorganization-autocomplete')
        #}


class BPlanUpdateForm(ModelForm):

    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # https://medium.com/@azzouzhamza13/django-crispy-forms-bootstrap5-00a1eb3ec3c7
        # https://www.youtube.com/watch?v=MZwKoi0wu2Q
        # Validation Problem: https://github.com/django-crispy-forms/django-crispy-forms/issues/623
        # https://stackoverflow.com/questions/64581369/django-crispy-forms-validation-error-in-template
        # Datumsfelder
        self.fields['aufstellungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                'localize': True,
                }
        )
        self.fields['satzungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['rechtsverordnungs_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['ausfertigungs_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['inkrafttretens_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['untergangs_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': '1960-01-01',
                'max': str(timezone.now().date()),
                }
        )
        self.fields['gemeinde'].widget = GemeindeSelect2(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        #self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
        self.helper.layout = Layout(
            Fieldset(
                "Verwaltung",
                Row(
                    "public",
                ),
            ),
            Fieldset(
                "Pflichtfelder XPlanung",
                Row(
                    Column(
                        Field("gemeinde"),
                        "name",
                        "planart",
                        Fieldset(
                            "Pflichtfeld XPlanung-light",
                            Row(
                                "nummer",
                        )),
                    ),
                    Column(
                        "geltungsbereich",
                    ),
                ),
            ),
            Fieldset(
                "Weitere Informationen",
                Row(
                    "massstab",
                ),
                Row(
                    "beschreibung",
                ),
            ),    
            Fieldset(
                "Datumsfelder",
                Row(
                    Column(
                        "aufstellungsbeschluss_datum",
                    ),
                    Column(
                        "satzungsbeschluss_datum",
                    ),
                    Column(
                        "rechtsverordnungs_datum",
                    ),
                    Column(
                        "ausfertigungs_datum",
                    ),
                    Column(
                        "inkrafttretens_datum",
                    ),
                    Column(
                        "untergangs_datum",
                    ),
                ),
            ),
            Fieldset(
                "Marker",
                Row(
                    Column(
                        "staedtebaulicher_vertrag",
                    ),
                    Column(
                        "erschliessungs_vertrag",
                    ),
                    Column(
                        "durchfuehrungs_vertrag",
                    ),
                    Column(
                        "gruenordnungsplan",
                    ),
                ),
            ),   
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = BPlan

        fields = ["name", 
                  "nummer", 
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "massstab",
                  "beschreibung",
                  "public",
                  "aufstellungsbeschluss_datum", 
                  "satzungsbeschluss_datum",
                  "rechtsverordnungs_datum",
                  "ausfertigungs_datum", 
                  "inkrafttretens_datum",  
                  "untergangs_datum",
                  "staedtebaulicher_vertrag",
                  "erschliessungs_vertrag",
                  "durchfuehrungs_vertrag",
                  "gruenordnungsplan",
                ]


class FPlanCreateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # https://medium.com/@azzouzhamza13/django-crispy-forms-bootstrap5-00a1eb3ec3c7
        # https://www.youtube.com/watch?v=MZwKoi0wu2Q
        # Validation Problem: https://github.com/django-crispy-forms/django-crispy-forms/issues/623
        # https://stackoverflow.com/questions/64581369/django-crispy-forms-validation-error-in-template
        self.fields['aufstellungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['planbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['wirksamkeits_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['untergangs_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': '1960-01-01',
                'max': str(timezone.now().date()),
                }
        )
        # https://forum.djangoproject.com/t/model-choice-field-how-to-add-attributes-to-the-options/37782
        # https://django-autocomplete-light.readthedocs.io/en/master/_modules/dal_select2/widgets.html#ModelSelect2Multiple
        # mixin - erbt von 3 Kassen !
        # alter Weg (einfache Select option Liste):
        # self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
        # Neuer Weg - django-autocomplete-light/select2
        self.fields['gemeinde'].widget = GemeindeSelect2(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        """
        self.helper.layout = Layout(
            TabHolder(
                Tab(
                    "Grunddaten",
                    "gemeinde",
                    "name",
                    "geltungsbereich",
                    "nummer",
                    "planart",
                    ),
                Tab(
                    "Datumsfelder",
                    "inkrafttretens_datum",
                    ),  
                Tab(
                    "Checkboxen",
                    "staedtebaulicher_vertrag",
                    ),   
                ),
                Submit("submit", "Erstellen")
            )
        """
        self.helper.layout = Layout(
            Fieldset(
                "Verwaltung",
                Row(
                    "public",
                ),
            ),
            Fieldset(
                "Pflichtfelder XPlanung",
                Row(
                    Column(
                        Field("gemeinde"),
                        "name",
                        "planart",
                    ),
                    Column(
                        "geltungsbereich",
                    ),
                ),
            ),
            Fieldset(
                "Pflichtfelder XPlanung-light",
                Row(
                    "nummer",
                ),
            ),  
            Fieldset(
                "Weitere Informationen",
                Row(
                    "massstab",
                ),
                Row(
                    "beschreibung",
                ),
            ),    
            Fieldset(
                "Datumsfelder",
                Row(
                    Column(
                        "aufstellungsbeschluss_datum",
                    ),
                    Column(
                        "planbeschluss_datum",
                    ),
                    Column(
                        "wirksamkeits_datum",
                    ),
                    Column(
                        "untergangs_datum",
                    ),
                ),
            ),
            Submit("submit", "Erstellen")
        )

    class Meta:
        model = FPlan
        fields = ["name", 
                  "nummer", 
                  "public",
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "massstab",
                  "beschreibung",
                  "aufstellungsbeschluss_datum", 
                  "planbeschluss_datum",
                  "wirksamkeits_datum",
                  "untergangs_datum", 
                ]
        # alternative to invokation above - but no possibility to have further attributes?
        #widgets = {
        #    'gemeinde': autocomplete.ModelSelect2Multiple(url='administrativeorganization-autocomplete')
        #}


class FPlanUpdateForm(ModelForm):

    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # https://medium.com/@azzouzhamza13/django-crispy-forms-bootstrap5-00a1eb3ec3c7
        # https://www.youtube.com/watch?v=MZwKoi0wu2Q
        # Validation Problem: https://github.com/django-crispy-forms/django-crispy-forms/issues/623
        # https://stackoverflow.com/questions/64581369/django-crispy-forms-validation-error-in-template
        # Datumsfelder
        self.fields['aufstellungsbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                'localize': True,
                }
        )
        self.fields['planbeschluss_datum'].widget = forms.DateInput(
            attrs={
                'type': 'date',
                'min': str((timezone.now() - timedelta(days=29200)).date()),
                'max': str(timezone.now().date()),
                }
        )
        self.fields['wirksamkeits_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': '1960-01-01',
                'max': str(timezone.now().date()),
                }
        )
        self.fields['untergangs_datum'].widget = forms.DateInput(          
            attrs={
                'type': 'date',
                'min': '1960-01-01',
                'max': str(timezone.now().date()),
                }
        )
        self.fields['gemeinde'].widget = GemeindeSelect2(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        #self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
        self.helper.layout = Layout(
            Fieldset(
                "Verwaltung",
                Row(
                    "public",
                ),
            ),
            Fieldset(
                "Pflichtfelder XPlanung",
                Row(
                    Column(
                        Field("gemeinde"),
                        "name",
                        "planart",
                    ),
                    Column(
                        "geltungsbereich",
                    ),
                ),
            ),
            Fieldset(
                "Pflichtfelder XPlanung-light",
                Row(
                    "nummer",
                )),
            Fieldset(
                "Weitere Informationen",
                Row(
                    "massstab",
                ),
                Row(
                    "beschreibung",
                ),
            ),    
            Fieldset(
                "Datumsfelder",
                Row(
                    Column(
                        "aufstellungsbeschluss_datum",
                    ),
                    Column(
                        "planbeschluss_datum",
                    ),
                    Column(
                        "wirksamkeits_datum",
                    ),
                    Column(
                        "untergangs_datum",
                    ),
                ),
            ),
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = FPlan

        fields = ["name", 
                  "nummer", 
                  "public",
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "massstab",
                  "beschreibung",
                  "aufstellungsbeschluss_datum", 
                  "planbeschluss_datum",
                  "wirksamkeits_datum",
                  "untergangs_datum",
                ]


class ContactOrganizationCreateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields['gemeinde'].widget = GemeindeSelect3()
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur Kontaktstelle",
                Row(
                    Field("gemeinde"),
                    ),
                Row(
                    Column(
                        "name",
                    ),
                    Column(
                        "unit",
                    ),
                ),
                Row(
                    'person',
                ),
                Row(
                    Column(
                        'email',
                    ),
                    Column(
                        'phone',
                    ),
                    Column(
                        'facsimile',
                    ),
                ),
                Row(
                    'datenschutz_link',
                ),
                Row(
                    'homepage',
                ),
            ),
            Submit("submit", "Erstellen"),
        )

    class Meta:
        model = ContactOrganization

        fields = ["gemeinde", "name", "unit", "person", "email", "phone", "facsimile", "homepage", "datenschutz_link"]


class ContactOrganizationUpdateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields['gemeinde'].widget = GemeindeSelect3()
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur Kontaktstelle",
                Row(
                    Field("gemeinde"),
                ),
                Row(
                    Column(
                        "name",
                    ),
                    Column(
                        "unit",
                    ),
                ),
                Row(
                    'person',
                ),
                Row(
                    Column(
                        'email',
                    ),
                    Column(
                        'phone',
                    ),
                    Column(
                        'facsimile',
                    ),
                ),
                Row(
                    'datenschutz_link',
                ),
                Row(
                    'homepage',
                ),
            ),
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = ContactOrganization

        fields = ["gemeinde", "name", "unit", "person", "email", "phone", "facsimile", "homepage", "datenschutz_link" ]


class ToebMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Überschreibt die Label-Darstellung mit zusätzlichen Annotierungen."""
    def label_from_instance(self, obj):
        emails = self.form._email_map.get(obj.pk, 'keine E-Mails')
        return f"{obj.name} – EMails: ({emails})"


class BPlanBeteiligungToebNotificationCreateForm(ModelForm):
    selected_toebs = ToebMultipleChoiceField(
        queryset=ToebUnit.objects.none(),  
        widget=forms.CheckboxSelectMultiple,
        label="TÖBs auswählen",
    )

    def __init__(self, *args, **kwargs):
        beteiligung = kwargs.pop('beteiligung', None)
        super().__init__(*args, **kwargs)
        self._email_map = {}  # am Form-Objekt speichern
        self.fields['selected_toebs'].form = self

        if beteiligung is not None:
            toebs = ToebUnit.objects.filter(bplan_beteiligungen=beteiligung).prefetch_related('editors')
            for toeb in toebs:
                emails = [
                    user.user.email
                    for user in toeb.editors.all()
                    if user.user.email
                ]
                self._email_map[toeb.pk] = ', '.join(emails)
            self.fields['selected_toebs'].queryset = toebs    


        self.helper = FormHelper(self)
        
        self.helper.layout = Layout(
            Fieldset(
                "TOEB-Benachrichtigung",
                Row(
                        Field("message"),
                    ),
                Row(
                        Field("selected_toebs"),
                    ),
            ),
            Submit("submit", "Versenden"),
        )

    class Meta:
        model = BPlanBeteiligungToebNotification
        fields = ["message", "selected_toebs",]


class FPlanBeteiligungToebNotificationCreateForm(BPlanBeteiligungToebNotificationCreateForm):

    def __init__(self, *args, **kwargs):
        beteiligung = kwargs.pop('beteiligung', None)
        super().__init__(*args, **kwargs)
        self._email_map = {}  # am Form-Objekt speichern
        self.fields['selected_toebs'].form = self

        if beteiligung is not None:
            toebs = ToebUnit.objects.filter(fplan_beteiligungen=beteiligung).prefetch_related('editors')
            for toeb in toebs:
                emails = [
                    user.user.email
                    for user in toeb.editors.all()
                    if user.user.email
                ]
                self._email_map[toeb.pk] = ', '.join(emails)
            self.fields['selected_toebs'].queryset = toebs    


        self.helper = FormHelper(self)
        
        self.helper.layout = Layout(
            Fieldset(
                "TOEB-Benachrichtigung",
                Row(
                        Field("message"),
                    ),
                Row(
                        Field("selected_toebs"),
                    ),
            ),
            Submit("submit", "Versenden"),
        )

    class Meta:
        model = FPlanBeteiligungToebNotification
        fields = ["message", "selected_toebs",]


class ToebUnitCreateForm(ModelForm):
    """
    for crispy-forms
    """

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields['organization'].widget = OrganizationSelect2Single(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur TOEB-Stelle",
                Row(
                    Column(
                        "organization",
                    ),
                    Column(
                        "name",
                    ),
                    Column(
                        "theme",
                    ),
                    Column(
                        "editors",
                    ),
                    ),
                Row(
                    Column(
                       Row('description'),
                    ),
                    Column(
                        "geometry",
                    ),
                ),
                Row(
                    Column(
                        "public",
                    ),
                ),
            ),
            Submit("submit", "Erstellen"),
        )

    class Meta:
        model = ToebUnit
        fields = ["organization", "name", "description", "theme", "public", "geometry", "editors" ]


class ToebUnitUpdateForm(ModelForm):
    """
    for crispy-forms
    """

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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields['organization'].widget = OrganizationSelect2Single(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur TOEB-Stelle",
                Row(
                    Column(
                        "organization",
                    ),
                    Column(
                        "name",
                    ),
                    Column(
                        "theme",
                    ),
                    Column(
                        "editors",
                    ),
                    ),
                Row(
                    Column(
                       Row('description'),
                    ),
                    Column(
                        "geometry",
                    ),
                ),
                Row(
                    Column(
                        "public",
                    ),
                ),
            ),
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = ToebUnit
        fields = ["organization", "name", "description", "theme", "public", "geometry", "editors" ]


class AdministrativeOrganizationUpdateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Fieldset(
                "Zusätzliche Informationen für die Bereitstellung durch die Gebietskörperschaft",
                Row(
                    "coat_of_arms_url",
                ),
                Row(
                    Column(
                        "published_data_license",
                    ),
                    Column(
                        "published_data_license_source_note",
                    ),
                ),
                Row(
                    Column(
                        "published_data_accessrights",
                    ),
                    Column(
                        "published_data_rights",
                    ),
                ),
            ),
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = AdministrativeOrganization

        fields = ["coat_of_arms_url", "published_data_license", "published_data_license_source_note", "published_data_accessrights", "published_data_rights", ]


"""
Neues Formular zur Editierung der Beteiligungsbeiträge - basierend auf django-formset
https://django-formset.fly.dev/model-forms/#
"""

from django.forms.models import ModelForm
#from formset.widgets import DateInput, Selectize, UploadedFileInput
#from formset.widgets.richtext import RichTextarea
#from formset.richtext.widgets import RichTextarea
from django.forms import widgets, fields, BooleanField
from xplanung_light.models import BPlanBeteiligungBeitrag
from formset.fields import Activator
from formset.renderers import ButtonVariant
from formset.widgets import Button
from formset.widgets import UploadedFileInput, DateInput, TextInput

from formset.collection import FormCollection
from formset.renderers.bootstrap import FormRenderer
#from formset.views import FormCollectionView
from django.forms.fields import IntegerField
from django.forms.fields import ChoiceField
from django.forms.widgets import HiddenInput
from formset.widgets import DualSelector
from formset.widgets import DualSortableSelector


class BeteiligungToebDualSortableSelector(DualSortableSelector):
    """
    Spezielle Klasse um den Selektor adptieren zu können
    """
    """
    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)
        # groups ist eine Liste von (group_name, subgroup, index)
        for group_name, subgroup, index in groups:
            for option in subgroup:
                option['label'] = f"* {option['label']}"
        return groups
    """
    def label_from_instance(self, obj):
        """Überschreibt die Label-Darstellung mit zusätzlichen Annotierungen."""
        print(f"label_from_instance aufgerufen für: {obj}") 
        prefix = "* "
        return f"{prefix}{obj.label}"
        #emails = self.form._email_map.get(obj.pk, 'keine E-Mails')
        #return f"{obj.name} – EMails: ({emails})"


class BPlanBeteiligungForm(FormMixin, ModelForm):
    """
    Klasse für das Anlegen und Update von Informationen zum BPlanBeteiligungsverfahren (django-formset).
    Überlegung  ggf. mehrseitiges Formular: https://django-formset.fly.dev/bootstrap/checkout
    https://django-formset.fly.dev/form-stepper/
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...

    """
    default_renderer = FormRenderer(
        form_css_classes = 'row',
        field_css_classes={
            '*': 'mb-2 col-12',
            #'typ': 'mb-2 col-12',
            'bekanntmachung_datum': 'mb-2 col-4',
            'start_datum': 'mb-2 col-4',
            'end_datum': 'mb-2 col-4',
            'allow_online_beitrag': 'mb-2 col-12',
            #'publikation_internet': 'mb-2 col-12',
            #'assigned_toebs': 'mb-2 col-12',
        },
    )

    def __init__(self, *args, **kwargs):
        """
        In der init Funktion kann "OnLoad" beim Update gewisse Elemente deaktivieren.
        """
        super().__init__(*args, **kwargs)
        # Über die lambda Funktion können wir auf weitere Attribute reagieren - Eigene TOEBS und Räumliche Überdeckung
        #self.fields['assigned_toebs'].label_from_instance = lambda obj:  str(obj) if not obj.owned and not obj.intersects else "* " + str(obj)  if obj.owned and not obj.intersects else "+ " + str(obj) if obj.intersects and not obj.owned else "*+ " + str(obj)
        self.fields['assigned_toebs'].label_from_instance = lambda obj:  "~- " + str(obj) if not obj.owned and not obj.intersects else "*- " + str(obj)  if obj.owned and not obj.intersects else "~+ " + str(obj) if obj.intersects and not obj.owned else "*+ " + str(obj)
        self.fields['assigned_toebs'].help_text = "TOEBS - Filter: (*) - eigene, (~) - fremde, (+) - räumliche Überdeckung Zuständigkeitsbereich mit Planung, (-) - keine räumliche Überdeckung"
        is_update = self.instance.pk is not None
        # Bei Update und bereits vorhandene Beiträge -> alles sperren bis auf ...
        if is_update:
            typ = self.instance.typ
            # typ darf bei Update nie geändert werden -> Feld sperren
            self.fields['typ'].disabled = True
            hat_beitraege = BPlanBeteiligungBeitrag.objects.filter(
                bplan_beteiligung=self.instance.pk
            ).exists()
            if hat_beitraege:
                print('Deaktivieren spezieller Felder wenn schon Beteiligungsbeiträge vorhanden sind')
                # Problem - cache? - Deaktivierung des Dualselectors erfolgt erst bei refresh ... - strange
                # TODO klären warum?
                #self.fields['assigned_toebs'].disabled = True
                for field in self.fields.values():
                    field.disabled = True

    def clean(self):
        """
        Hier werden alle Attribute getestet, BEVOR das Formular als valide gilt
        und bevor die View versucht, das Modell zu speichern.
        """
        # Zuerst die Standard-Validierung von Django ausführen
        cleaned_data = super().clean()
        # Prüfen, ob es sich um ein Update oder ein Create handelt
        is_update = self.instance.pk is not None
        is_create = self.instance.pk is None
        if is_update:
            # Nur bei Update
            # Bestimmte Typen dürfen nachträglich nicht mehr geändert werden
            alter_typ = self.instance.typ  # Wert aus der Datenbank vor dem Update
            neuer_typ = cleaned_data.get('typ')
            if alter_typ != neuer_typ:
                self.add_error('typ', "Der Typ des Beteiligungsverfahrens kann nachträglich nicht mehr geändert werden.")
            
            # Test ob es schon Beitraege gibt - falls das der Fall ist, soll die Bearbeitung verhindert werden
            beitraege = BPlanBeteiligungBeitrag.objects.filter(bplan_beteiligung__in=[self.instance.pk])
            if len(beitraege) > 0:
                self.add_error(None, "Es gibt schon Beiträge zum Verfahren - das Verfahren darf daher nicht mehr verändert werden!")
        # Attribute aus den bereinigten Daten auslesen
        start_datum = cleaned_data.get('start_datum')
        end_datum = cleaned_data.get('end_datum')
        typ = cleaned_data.get('typ')
        publikation_internet = cleaned_data.get('publikation_internet')

        # Benutzerdefinierte Test durchführen:
        # Logische Datumsprüfung
        if start_datum and end_datum and start_datum > end_datum:
            # Fehler an ein bestimmtes Feld binden (wird direkt unter dem Feld angezeigt)
            self.add_error('end_datum', "Das Enddatum darf nicht vor dem Startdatum liegen.")

        # Abhängigkeiten prüfen basierend auf deinem 'typ'
        # Passend zu deinen 'df-hide/show' Bedingungen im Frontend:
        #if typ not in ['2000', '20001'] and not publikation_internet:
        #    self.add_error('publikation_internet', "Für diesen Typ ist eine Internet-Publikation erforderlich.")

        # Rückgabe der bereinigten Daten
        return cleaned_data

    class Meta:
        model = BPlanBeteiligung
        fields = ['typ', 'beschreibung', 'bekanntmachung_datum', 'start_datum', 'end_datum' , "allow_online_beitrag", "publikation_internet", "assigned_toebs"]
        widgets = {
            'beschreibung': RichTextarea(),
            'bekanntmachung_datum': DateInput(),
            'start_datum': DateInput(),
            'end_datum': DateInput(),
            #'allow_online_beitrag': widgets.CheckboxInput(attrs={'df-hide': ".typ=='2000' || .typ=='20001'"}),
            'publikation_internet': TextInput(attrs={'df-hide': ".typ=='2000' || .typ=='20001'"}),                         
            'assigned_toebs': BeteiligungToebDualSortableSelector(search_lookup='label__icontains',
                                                   group_field_name='theme_display',
                                                   attrs={'df-show': ".typ=='2000' || .typ=='20001'"}),
        }


class FPlanBeteiligungForm(FormMixin, ModelForm):
    """
    Neue Klasse für das Anlegen und Update von Informationen zum FPlanBeteiligungsverfahren - diesmal mit django-formset
    Überlegung  mehrseitiges Formular: https://django-formset.fly.dev/bootstrap/checkout
    https://django-formset.fly.dev/form-stepper/
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...
    """

    default_renderer = FormRenderer(
        form_css_classes = 'row',
        field_css_classes={
            '*': 'mb-2 col-12',
            #'typ': 'mb-2 col-12',
            'bekanntmachung_datum': 'mb-2 col-4',
            'start_datum': 'mb-2 col-4',
            'end_datum': 'mb-2 col-4',
            'allow_online_beitrag': 'mb-2 col-12',
            #'publikation_internet': 'mb-2 col-12',
            #'assigned_toebs': 'mb-2 col-12',
        },
    )

    def __init__(self, *args, **kwargs):
        """
        In der init Funktion kann beim Update gewisse Elemente deaktivieren.
        """
        super().__init__(*args, **kwargs)
        self.fields['assigned_toebs'].label_from_instance = lambda obj:  "~- " + str(obj) if not obj.owned and not obj.intersects else "*- " + str(obj)  if obj.owned and not obj.intersects else "~+ " + str(obj) if obj.intersects and not obj.owned else "*+ " + str(obj)
        self.fields['assigned_toebs'].help_text = "TOEBS - Filter: (*) - eigene, (~) - fremde, (+) - räumliche Überdeckung Zuständigkeitsbereich mit Planung, (-) - keine räumliche Überdeckung"
        is_update = self.instance.pk is not None
        # Bei Update und bereits vorhandene Beiträge -> alles sperren bis auf ...
        if is_update:
            typ = self.instance.typ
            # typ darf bei Update nie geändert werden -> Feld sperren
            self.fields['typ'].disabled = True
            hat_beitraege = FPlanBeteiligungBeitrag.objects.filter(
                fplan_beteiligung=self.instance.pk
            ).exists()
            if hat_beitraege:
                print('Deaktivieren spezieller Felder wenn schon Beteiligungsbeiträge vorhanden sind')
                # Problem - cache? - Deaktivierung des Dualselectors erfolgt erst bei refresh ... - strange
                # TODO klären warum?
                #self.fields['assigned_toebs'].disabled = True
                for field in self.fields.values():
                    field.disabled = True

    def clean(self):
        """
        Hier werden alle Attribute getestet, BEVOR das Formular als valide gilt
        und bevor die View versucht, das Modell zu speichern.
        """
        # Zuerst die Standard-Validierung von Django ausführen
        cleaned_data = super().clean()
        # Prüfen, ob es sich um ein Update oder ein Create handelt
        is_update = self.instance.pk is not None
        is_create = self.instance.pk is None
        if is_update:
            # Nur bei Update
            # Bestimmte Typen dürfen nachträglich nicht mehr geändert werden
            alter_typ = self.instance.typ  # Wert aus der Datenbank vor dem Update
            neuer_typ = cleaned_data.get('typ')
            if alter_typ != neuer_typ:
                self.add_error('typ', "Der Typ des Beteiligungsverfahrens kann nachträglich nicht mehr geändert werden.")
            
            # Test ob es schon Beitraege gibt - falls das der Fall ist, soll die Bearbeitung verhindert werden
            beitraege = FPlanBeteiligungBeitrag.objects.filter(fplan_beteiligung__in=[self.instance.pk])
            if len(beitraege) > 0:
                self.add_error(None, "Es gibt schon Beiträge zum Verfahren - das Verfahren darf daher nicht mehr verändert werden!")
        # Attribute aus den bereinigten Daten auslesen
        start_datum = cleaned_data.get('start_datum')
        end_datum = cleaned_data.get('end_datum')
        typ = cleaned_data.get('typ')
        publikation_internet = cleaned_data.get('publikation_internet')

        # Benutzerdefinierte Test durchführen:
        # Logische Datumsprüfung
        if start_datum and end_datum and start_datum > end_datum:
            # Fehler an ein bestimmtes Feld binden (wird direkt unter dem Feld angezeigt)
            self.add_error('end_datum', "Das Enddatum darf nicht vor dem Startdatum liegen.")

        # Abhängigkeiten prüfen basierend auf deinem 'typ'
        # Passend zu deinen 'df-hide/show' Bedingungen im Frontend:
        #if typ not in ['2000', '20001'] and not publikation_internet:
        #    self.add_error('publikation_internet', "Für diesen Typ ist eine Internet-Publikation erforderlich.")

        # Rückgabe der bereinigten Daten
        return cleaned_data

    class Meta:
        model = FPlanBeteiligung
        fields = ['typ', 'beschreibung', 'bekanntmachung_datum', 'start_datum', 'end_datum' , "allow_online_beitrag", "publikation_internet", "assigned_toebs"]
        widgets = {
            'beschreibung': RichTextarea(),
            'bekanntmachung_datum': DateInput(),
            'start_datum': DateInput(),
            'end_datum': DateInput(),
            #'allow_online_beitrag': widgets.CheckboxInput(attrs={'df-hide': ".typ=='2000' || .typ=='20001'"}),
            'publikation_internet': TextInput(attrs={'df-hide': ".typ=='2000' || .typ=='20001'"}), 
            'assigned_toebs': BeteiligungToebDualSortableSelector(search_lookup='label__icontains',
                                                   group_field_name='theme_display',
                                                   attrs={'df-show': ".typ=='2000' || .typ=='20001'"}),
        }


class BPlanBeitragStellungnahmeForm(ModelForm):
    """
    Klasse für das Anlegen und Update von Stellungnahmen.
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...

    """
    # Temporäres Feld für die Auswahl
    beruecksichtigung = forms.MultipleChoiceField(
        choices=BPlanBeitragStellungnahme.TAGS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Berücksichtigung",
    )
   
    class Meta:
        model = BPlanBeitragStellungnahme
        fields = ["bezug_beitrag", "stellungnahme", "beruecksichtigung", "beitrag"]
        widgets = {
            'beitrag': HiddenInput(),
        }
        """
        
        widgets = {
            'beschreibung': RichTextarea(),
            'bekanntmachung_datum': DateInput(),
            'start_datum': DateInput(),
            'end_datum': DateInput(),
        }
        """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initial-Wert aus JSONField setzen
        if self.instance and self.instance.pk:
            self.fields['beruecksichtigung'].initial = self.instance.beruecksichtigung


class FPlanBeitragStellungnahmeForm(BPlanBeitragStellungnahmeForm):
    """
    """
    # Temporäres Feld für die Auswahl
    beruecksichtigung = forms.MultipleChoiceField(
        choices=FPlanBeitragStellungnahme.TAGS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Berücksichtigung",
    )
   
    class Meta:
        model = FPlanBeitragStellungnahme
        fields = ["bezug_beitrag", "stellungnahme", "beruecksichtigung", "beitrag"]
        widgets = {
            'beitrag': HiddenInput(),
        }
   

class CaptchaForm(forms.Form):
    consent = forms.BooleanField(required=True, label="Ich habe die Datenschutzbestimmungen der Gebietskörperschaft, sowie die Hinweise zum Datenschutz und den Nutzungsbedingungen der Plattform gelesen und akzeptiere sie.")
    captcha = CaptchaField()


class GastBeitragAuthenticateForm(ModelForm):
    captcha = CaptchaField()
    class Meta:
        model = BPlanBeteiligungBeitrag
        fields = ['email']


"""
Klasse für das Formular zum Hochladen der Anhänge eines Beteiligungsbeitrags
https://django-formset.fly.dev/model-collections/
Das Model wird nur für das schon vorgegebene id Feld genutzt.
Die url lautet in dem Fall: /plan/<int:planid/beteiligung/<int:pk>/beitrag/create/
"""
class BPlanBeteiligungFormFormset(ModelForm):
    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )
    """
    submit = Activator(
        label="Erstellen",
        widget=Button(
            action='disable -> spinner -> delay(200) -> submit -> reload !~ scrollToError',
            button_variant=ButtonVariant.PRIMARY,
            icon_path='formset/icons/send.svg',
        ),
    )
    """

    class Meta:
        model = BPlanBeteiligung
        fields = ['id']

"""
Das Gleiche für FPläne
"""
class FPlanBeteiligungFormFormset(ModelForm):
    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )

    class Meta:
        model = FPlanBeteiligung
        fields = ['id']


"""
Einfache ModelForm für das BPlanBeteiligungBeitragBeitrag-Objekt
Zunächst nur soll nur das Feld beschreibung editierbar sein.
Und das über ein RichtText-widget - mal sehen, ob das so ok ist - ggf. muessen wir das Model-Field ändern.
"""
class BPlanBeteiligungBeitragForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.fields['name'].required = True
        self.fields['typ'].initial = 1000
        self.fields['email'].required = True
        self.fields['eingangsdatum'].initial = datetime.now().date()


    class Meta:
        model = BPlanBeteiligungBeitrag
        fields = ['name', 'email', 'eingangsdatum', 'titel', 'beschreibung', 'typ']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'typ': HiddenInput(),
            'eingangsdatum': HiddenInput(),
        }

"""
Die gleiche Klasse für FPläne
"""
class FPlanBeteiligungBeitragForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.fields['name'].required = True
        self.fields['typ'].initial = 1000
        self.fields['email'].required = True
        self.fields['eingangsdatum'].initial = datetime.now().date()


    class Meta:
        model = FPlanBeteiligungBeitrag
        fields = ['name', 'email', 'eingangsdatum', 'titel', 'beschreibung', 'typ']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'typ': HiddenInput(),
            'eingangsdatum': HiddenInput(),
        }


"""
Einfache ModelForm für das BPlanBeteiligungBeitragAnhang-Objekt
"""
class BPlanBeteiligungBeitragAnhangForm(ModelForm):

    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )
    attachment = fields.FileField(
        label="Anhang",
        widget=UploadedFileInput(attrs={
            'max-size': 1024 * 1024,
        }),
        help_text="Please do not upload files larger than 1MB",
        required=True,
        validators=[validate_file_infection],
    )
    """
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Falls kein neues File hochgeladen wurde (attachment ist im cleaned_data leer 
        # oder nur ein String-Pfad), behalte das alte File bei.
        if not self.cleaned_data.get('attachment'):
            # Wir holen den Wert direkt vom ursprünglichen Objekt
            instance.attachment = self.instance.attachment
        
        if commit:
            instance.save()
        return instance
    """

    class Meta:
        model = BPlanBeteiligungBeitragAnhang
        fields = ['id', 'name', 'typ', 'attachment']#,'beitrag']
    

"""
Für FPläne
"""
class FPlanBeteiligungBeitragAnhangForm(ModelForm):

    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )
    
    attachment = fields.FileField(
        label="Anhang",
        widget=UploadedFileInput(attrs={
            'max-size': 1024 * 1024,
        }),
        help_text="Please do not upload files larger than 1MB",
        required=True,
        validators=[validate_file_infection],
    )
    
    class Meta:
        model = FPlanBeteiligungBeitragAnhang
        fields = ['id', 'name', 'typ', 'attachment']


"""
Collection für die über ein ForeignKey mit dem BPlanBeteiligungBeitrag-Objekt verbundenen BPlanBeteiligungBeitragAnhang-Objekte.
"""
class BPlanBeteiligungBeitragAnhangCollection(FormCollection):
    legend = "Anlagen"
    add_label = "Anlage hinzufügen"
    related_field = 'beitrag'
    attachment = BPlanBeteiligungBeitragAnhangForm()
    #beitrag = BPlanBeteiligungBeitragCollection()
    min_siblings = 0
    max_siblings = 4

    def retrieve_instance(self, data):
        #print(f"DEBUG: retrieve_instance aufgerufen mit ID: {data.get('id')}")
        #print(f"DEBUG: Aktuelle Instanz der Collection (Beitrag): {self.instance}")
        if data := data.get('attachment'):
            try:
                return self.instance.attachments.get(id=data.get('id') or 0)
            except (AttributeError, BPlanBeteiligungBeitragAnhang.DoesNotExist, ValueError):
                return BPlanBeteiligungBeitragAnhang(beitrag=self.instance)


"""
Für FPläne
"""
class FPlanBeteiligungBeitragAnhangCollection(FormCollection):
    legend = "Anlagen"
    add_label = "Anlage hinzufügen"
    related_field = 'beitrag'
    attachment = FPlanBeteiligungBeitragAnhangForm()
    min_siblings = 0
    max_siblings = 4

    def retrieve_instance(self, data):
        if data := data.get('attachment'):
            try:
                return self.instance.attachments.get(id=data.get('id') or 0)
            except (AttributeError, FPlanBeteiligungBeitragAnhang.DoesNotExist, ValueError):
                return FPlanBeteiligungBeitragAnhang(beitrag=self.instance)


"""
Collection für die über ein ForeignKey mit dem BPlanBeteiligung-Objekt verbundenen BPlanBeteiligungBeitrag-Objekte.
"""
class BPlanBeteiligungBeitragCollection(FormCollection):
    #print("Instantierung BPlanBeteiligungBeitragCollection")
    legend = "Ihr Beitrag"
    add_label = "Beitrag hinzufügen"
    related_field = 'bplan_beteiligung' # hier wird der related_name des verbundenen Objketes genutzt!
    beitrag = BPlanBeteiligungBeitragForm()
    attachments = BPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)
    min_siblings = 1
    max_siblings = 1

    def retrieve_instance(self, data):
        if data := data.get('beitrag'):
            try:
                return self.instance.beitrag.get(id=data.get('id') or 0)
            except (AttributeError, BPlanBeteiligungBeitrag.DoesNotExist, ValueError):
                #print("BPlanBeteiligungBeitrag nicht gefunden!")
                return BPlanBeteiligungBeitrag(bplan_beteiligung=self.instance)


"""
Für FPläne
"""
class FPlanBeteiligungBeitragCollection(FormCollection):
    #print("Instantierung FPlanBeteiligungBeitragCollection")
    legend = "Ihr Beitrag"
    add_label = "Beitrag hinzufügen"
    related_field = 'fplan_beteiligung' # hier wird der related_name des verbundenen Objketes genutzt!
    beitrag = FPlanBeteiligungBeitragForm()
    attachments = FPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)
    min_siblings = 1
    max_siblings = 1

    def retrieve_instance(self, data):
        if data := data.get('beitrag'):
            try:
                return self.instance.beitrag.get(id=data.get('id') or 0)
            except (AttributeError, FPlanBeteiligungBeitrag.DoesNotExist, ValueError):
                #print("BPlanBeteiligungBeitrag nicht gefunden!")
                return FPlanBeteiligungBeitrag(fplan_beteiligung=self.instance)


class BeteiligungEinwilligungsoptionenForm(forms.Form):
    """
    Falls man die Einwilligungsoptionen später alle getrennt im Formular auflisten will
    """
    # Hier noch die Pflichtfelder zuden Einwilligungsfragen mit aufnehmen
    def __init__(self, *args, **kwargs):
        today = datetime.now().date()
        einwilligungsfragen = ConsentOption.objects.filter(obsolete=False, mandatory=True, valid_from__lte=today, valid_until__gte=today, type='commentator')
        super().__init__(*args, **kwargs)

        for instance in einwilligungsfragen:
            self.fields[str(uuid.uuid4())] = forms.BooleanField(label=instance.title, required=True)


class BPlanBeteiligungCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    bplan_beteiligung = BPlanBeteiligungFormFormset()
    beitrag = BPlanBeteiligungBeitragCollection()
    captcha = CaptchaForm()


"""
Für FPläne
"""
class FPlanBeteiligungCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    bplan_beteiligung = FPlanBeteiligungFormFormset()
    beitrag = FPlanBeteiligungBeitragCollection()
    captcha = CaptchaForm()


"""
Klassen für die Verwaltung aller Einträge - auch der analogen.
Zunächst die Standard ModelForms für die Beitrag Objekte
"""

class BPlanBeteiligungBeitragGenericForm(ModelForm):

    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['email'].required = False
        # Bestehende Choices abrufen und filtern
        original_choices = self.fields['typ'].choices
        # Beispiel: Nur '2000', '3000' und '4000' behalten
        filtered_choices = [c for c in original_choices if c[0] in ['2000', '3000', '4000']]
        self.fields['typ'].choices = filtered_choices
        if not self.instance.pk:
            self.fields['eingangsdatum'].initial = None
            #self.fields['eingangsdatum'].widget.attrs.pop('value', None)
            # Instanz-Default überschreiben damit Django kein value rendert
            #self.instance.eingangsdatum = None

    # in der save Funktion kann man die Instanz einfach anpassen - hidden fields sind nicht sinnvoll
    def save(self, commit=True):
        instance = super().save(commit=False)
        #print("save ausgeführt - jetzt überschreiben ...")
        instance.approved = True
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()

        eingangsdatum = cleaned_data.get('eingangsdatum')
        bplan_beteiligung = cleaned_data.get('bplan_beteiligung')

        if eingangsdatum and bplan_beteiligung:
            if eingangsdatum > bplan_beteiligung.end_datum:
                self.add_error(
                    'eingangsdatum',
                    "Der Beitrag darf nicht nach Ablauf der Frist eingegangen sein!"
                )

        return cleaned_data

    class Meta:
        model = BPlanBeteiligungBeitrag
        fields = ['id', 'typ', 'eingangsdatum', 'name', 'email', 'titel', 'beschreibung', 'bplan_beteiligung']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'bplan_beteiligung': HiddenInput(),
            'eingangsdatum': widgets.DateInput(attrs={'type': 'date', 'pattern': r'\d{4}-\d{2}-\d{2}'}),
        }


class FPlanBeteiligungBeitragGenericForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['email'].required = False
        # Bestehende Choices abrufen und filtern
        original_choices = self.fields['typ'].choices
        # Beispiel: Nur '2000', '3000' und '4000' behalten
        filtered_choices = [c for c in original_choices if c[0] in ['2000', '3000', '4000']]
        self.fields['typ'].choices = filtered_choices

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.approved = True
        if commit:
            instance.save()
        return instance

    class Meta:
        model = FPlanBeteiligungBeitrag
        fields = ['typ', 'eingangsdatum', 'name', 'email', 'titel', 'beschreibung', 'approved']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'eingangsdatum': widgets.DateInput(attrs={'type': 'date', 'pattern': r'\d{4}-\d{2}-\d{2}'}),
            #'approved': HiddenInput(),
        }

"""
Andere Formulare für die TOEB-Beiträge
"""
class BPlanBeteiligungBeitragToebForm(ModelForm):

    id = IntegerField(
        required=False,
        widget=HiddenInput,
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.fields['name'].required = True
        #self.fields['email'].required = False
        # Bestehende Choices abrufen und filtern
        #original_choices = self.fields['typ'].choices
        # Beispiel: Nur '2000', '3000' und '4000' behalten
        #filtered_choices = [c for c in original_choices if c[0] in ['2000', '3000', '4000']]
        #self.fields['typ'].choices = filtered_choices

    # in der save Funktion kann man die Instanz einfach anpassen - hidden fields sind nicht sinnvoll
    def save(self, commit=True):
        instance = super().save(commit=False)
        #print("save ausgeführt - jetzt überschreiben ...")
        instance.approved = True
        if commit:
            instance.save()
        return instance

    class Meta:
        model = BPlanBeteiligungBeitrag
        fields = ['id', 'titel', 'email', 'beschreibung', 'bplan_beteiligung']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'bplan_beteiligung': HiddenInput(),
            'email': HiddenInput(),
        }


class FPlanBeteiligungBeitragToebForm(BPlanBeteiligungBeitragToebForm):

    class Meta:
        model = FPlanBeteiligungBeitrag
        fields = ['id', 'titel', 'email', 'beschreibung', 'fplan_beteiligung']
        widgets = {
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
            'fplan_beteiligung': HiddenInput(),
            'email': HiddenInput(),
        }

"""
Formular Collections für den generischen Fall - Sicht des Sachbearbeiters - er hat alle Freiheiten verschiedene 
Typen von Beiträgen zu erfassen - hier schliessen wir die Online-Varianten aus- da diese ja nicht vom Sachbearbeiter
abgeändert werden dürfen.
Wichtig ist hier zu klären, wie die Formulare aus einer Instanz befüllt werden können.

"""

class BPlanBeteiligungBeitragGenericCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    legend = "Beitrag"
    beitrag = BPlanBeteiligungBeitragGenericForm()
    attachments = BPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)

    #def retrieve_initial_dict(self, name, instance):
    #    initial = super().retrieve_initial_dict(name, instance)
    #    if name == 'beitrag' and not instance.pk:
    #        initial['eingangsdatum'] = datetime.date.today().isoformat()
    #    return initial

"""
Für FPläne
"""
class FPlanBeteiligungBeitragGenericCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    legend = "Beitrag"
    add_label = "Beitrag hinzufügen"
    beitrag = FPlanBeteiligungBeitragGenericForm()
    attachments = FPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)

"""
Für TOEB-Beiträge
"""
class BPlanBeteiligungBeitragToebCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    legend = "Beitrag"
    beitrag = BPlanBeteiligungBeitragToebForm()
    attachments = BPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)

"""
Für FPläne
"""
class FPlanBeteiligungBeitragToebCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    legend = "Beitrag"
    add_label = "Beitrag hinzufügen"
    beitrag = FPlanBeteiligungBeitragToebForm()
    attachments = FPlanBeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)


"""
Generisches Formulare
Für BPläne
"""
class BPlanBeteiligungGenericCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    bplan_beteiligung = BPlanBeteiligungFormFormset()
    beitrag = BPlanBeteiligungBeitragGenericCollection()
    #captcha = CaptchaForm()

"""
Für FPläne
"""
class FPlanBeteiligungGenericCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    fplan_beteiligung = FPlanBeteiligungFormFormset()
    beitrag = FPlanBeteiligungBeitragGenericCollection()
    #captcha = CaptchaForm()


"""
Für TOEB-Beiträge
"""
class BPlanBeteiligungToebCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    bplan_beteiligung = BPlanBeteiligungFormFormset()
    beitrag = BPlanBeteiligungBeitragToebCollection()


"""
Für FPläne
"""
class FPlanBeteiligungToebCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    fplan_beteiligung = FPlanBeteiligungFormFormset()
    beitrag = FPlanBeteiligungBeitragToebCollection()


class RequestForRoleCreateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.fields['organizations'].widget = GemeindeSelect3()
        
        self.helper.layout = Layout(
            Fieldset(
                'Antrag Rollenzuweisung',
                Row(
                    Column(
                        Field("role"),
                    ),
                    Column(
                        Field("organizations"),
                    ),
                ),
            ), 
            Submit("submit", "Antrag stellen")
        )

    class Meta:
        model = RequestForRole
        fields = ["role", "organizations"]


class RequestForRoleRefuseForm(ModelForm):
    """
    ModelForm für das Zurückweisen eines Antrags auf Zuweisung einer Rolle
    """
    default_renderer = FormRenderer(
        field_css_classes={
            'editing_note': 'mb-2 col-4',
        },
    )

    class Meta:
        model = RequestForRole
        fields = ["editing_note"]
        """
        widgets = {
            'editing_note': forms.CharField(widget=forms.Textarea),
        }
        """


class RequestForRoleConfirmForm(ModelForm):
    """
    ModelForm für das Genehmigen eines Antrags auf Zuweisung einer Rolle
    """
    default_renderer = FormRenderer(
        field_css_classes={
            'editing_note': 'mb-2 col-4',
        },
    )

    class Meta:
        model = RequestForRole
        fields = ["editing_note"]
        """
        widgets = {
            'editing_note': forms.CharField(widget=forms.Textarea),
        }
        """


from formset.richtext.controls import DialogControl
from formset.richtext.dialogs import SimpleLinkDialogForm
from formset.richtext import controls

class ConsentOptionForm(ModelForm):
    """
    Klasse für die Verwaltung von Zustimmungsoptionen - nutzt django-formset wegen Support für RichText-Field.
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...

    """
    default_renderer = FormRenderer(
        form_css_classes='row',
        field_css_classes={
            '*': 'mb-2 col-12',
            
            'valid_from': 'mb-2 col-4',
            'valid_until': 'mb-2 col-8',
            #'start_datum': 'mb-2 col-4',
            #'end_datum': 'mb-2 col-4',
            #'allow_online_beitrag': 'mb-2 col-4',
            #'publikation_internet': 'mb-2 col-4',
        },
    )

    class Meta:
        model = ConsentOption
        fields = ['type', 'title', 'description', 'mandatory', 'opt_out', 'valid_from', 'valid_until', 'validity_period']
        widgets = {
            'description': RichTextarea(attrs={'cols': '80', 'rows': '3'}, control_elements=[
                    controls.Heading(),
                    controls.Underline(),
                    controls.BulletList(),
                    controls.OrderedList(),
                    controls.Bold(),
                    controls.Italic(),
                    DialogControl(SimpleLinkDialogForm())
                ]),
            'valid_from': DateInput(attrs={
                'min': now().isoformat(),
                #'max': (now() + timedelta(weeks=2)).isoformat(),
            }),
            'valid_until': DateInput(),
        }

from formset.widgets import Selectize

class OrganizationUserAssignmentFormAdmin(FormMixin, forms.Form):
    default_renderer = FormRenderer(
        form_css_classes = 'row',
        field_css_classes={
            #'*': 'mb-2 col-12',
        },
    )
    organization = forms.ModelChoiceField(
        queryset=AdministrativeOrganization.objects.all().only('name', 'name_part', 'id', 'type'),
        label="Organisation",
        #widget=forms.Select(attrs={
        widget = Selectize(
            search_lookup='name__icontains',
            attrs={
            'class': 'form-select',
            'df-change': 'reload'  # Lädt Nutzer-Listen beim Wechsel neu
        })
    )
    admins = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().annotate(full_name=Concat('username', Value(' ('), 'email', Value(')'), output_field=CharField())),
        required=False,
        label="Nutzer",
        widget=DualSelector(
            search_lookup='full_name__icontains',
            attrs={
                'data-role': 'is_admin'
            }
        ),
        help_text="Nutzer - Rolle 'Admin' Zuweisung"
    )

    def __init__(self, *args, **kwargs):
        #print("admin form")
        organization_id = kwargs.pop('organization_id', None)
        super().__init__(*args, **kwargs)
        # Label überschreiben
        self.fields['admins'].label_from_instance = lambda obj: obj.full_name
        
        if organization_id:
            # Bereits zugewiesene Nutzer als initial values setzen
            org_users = AdminOrgaUser.objects.filter(
                organization__id=organization_id, is_admin=True
            )
            org_users_initial = AdminOrgaUser.objects.filter(
                organization__id=organization_id, is_admin=True
            ).values_list('user__id')
            self.fields['admins'].initial = User.objects.filter(
                id__in=org_users_initial,
            )
            self.fields['organization'].initial = AdministrativeOrganization.objects.get(pk=organization_id)

    def save(self):
        """Speichert die Nutzer-Rollen-Zuweisungen"""
        organization = self.cleaned_data['organization']
        admins = self.cleaned_data['admins']
        
        # Alle existierenden admin Zuweisungen für diese Organisation löschen
        AdminOrgaUser.objects.filter(organization=organization, is_admin=True).delete()
        
        # Admins erstellen oder anpassen
        for user in admins:
            if not AdminOrgaUser.objects.filter(
                organization=organization,
                user=user
            ).exists():
                AdminOrgaUser.objects.create(
                    organization=organization,
                    user=user,
                    is_admin=True,
                    is_toeb_reporter=False
                )
            else:
                org_user = AdminOrgaUser.objects.get(
                    organization=organization,
                    user=user
                )
                org_user.is_admin = True
                org_user.save()
        
        return organization


class OrganizationUserAssignmentFormToebReporter(FormMixin, forms.Form):
    default_renderer = FormRenderer(
        form_css_classes = 'row',
        field_css_classes={
            #'*': 'mb-2 col-12',
        },
    )
    organization = forms.ModelChoiceField(
        #queryset=AdministrativeOrganization.objects.all().only('name', 'name_part', 'id', 'type'),
        queryset=AdministrativeOrganization.objects.none(),
        label="Organisation",
        #widget=forms.Select(attrs={
        widget = Selectize(
            search_lookup='name__icontains',
            attrs={
            'class': 'form-select',
            'df-change': 'reload'  # Lädt Nutzer-Listen beim Wechsel neu
        })
    )
    toeb_reporter = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().annotate(full_name=Concat('username', Value(' ('), 'email', Value(')'), output_field=CharField())),
        required=False,
        label="Nutzer",
        widget=DualSelector(
            search_lookup='full_name__icontains',
            attrs={
                'data-role': 'is_toeb_reporter'
            }
        ),
        help_text="Nutzer - Rolle 'TOEB-Reporter' Zuweisung"
    )

    def __init__(self, *args, **kwargs):
        #print("toeb reporter form")
        organization_id = kwargs.pop('organization_id', None) 
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Label überschreiben
        self.fields['toeb_reporter'].label_from_instance = lambda obj: obj.full_name
        # Organisationen filtern, für die der User is_admin ist
        if user is not None:
            if user.is_superuser:
                self.fields['organization'].queryset = AdministrativeOrganization.objects.all().only(
                    'name', 'name_part', 'id', 'type'
                )
            else:
                self.fields['organization'].queryset = AdministrativeOrganization.objects.filter(
                    admin_orga_users__user=user,
                    admin_orga_users__is_admin=True
                ).only('name', 'name_part', 'id', 'type').distinct()
        else:
            self.fields['organization'].queryset = AdministrativeOrganization.objects.none()        
        if organization_id:
            # Bereits zugewiesene Nutzer als initial values setzen
            org_users = AdminOrgaUser.objects.filter(
                organization__id=organization_id, is_toeb_reporter=True
            )
            org_users_initial = AdminOrgaUser.objects.filter(
                organization__id=organization_id, is_toeb_reporter=True
            ).values_list('user__id')
            self.fields['toeb_reporter'].initial = User.objects.filter(
                id__in=org_users_initial,
            )
            self.fields['organization'].initial = AdministrativeOrganization.objects.get(pk=organization_id)

    def save(self):
        """Speichert die Nutzer-Rollen-Zuweisungen"""
        organization = self.cleaned_data['organization']
        toeb_reporter = self.cleaned_data['toeb_reporter']
        
        # Alle existierenden admin Zuweisungen für diese Organisation löschen
        AdminOrgaUser.objects.filter(organization=organization, is_toeb_reporter=True).delete()
        
        # Toeb Reporter erstellen oder anpassen
        for user in toeb_reporter:
            if not AdminOrgaUser.objects.filter(
                organization=organization,
                user=user
            ).exists():
                AdminOrgaUser.objects.create(
                    organization=organization,
                    user=user,
                    is_admin=False,
                    is_toeb_reporter=True
                )
            else:
                org_user = AdminOrgaUser.objects.get(
                    organization=organization,
                    user=user
                )
                org_user.is_toeb_reporter = True
                org_user.save()
        
        return organization
    

class UserOrganizationFormRoles(FormMixin, forms.Form):
    default_renderer = FormRenderer(
        form_css_classes = 'row',
        field_css_classes={
            #'*': 'mb-2 col-12',
        },
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all().only('username', 'email', 'id').annotate(full_name=Concat('username', Value(' ('), 'email', Value(')'), output_field=CharField())),
        label="Nutzer",
        widget = Selectize(
            search_lookup='username__icontains',
            attrs={
            'class': 'form-select',
            'df-change': 'reload'  # Lädt Nutzer-Listen beim Wechsel neu
        })
    )

    def __init__(self, *args, **kwargs):
        user_id = kwargs.pop('user_id', None)
        self.user_id = user_id
        super().__init__(*args, **kwargs)
        # Label überschreiben
        self.fields['user'].label_from_instance = lambda obj: obj.full_name
        
        if user_id:
            self.user_id = user_id
            self.fields['user'].initial = User.objects.get(pk=user_id)
