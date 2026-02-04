from datetime import timedelta
from django.utils import timezone

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User 
from xplanung_light.models import BPlan, BPlanSpezExterneReferenz, BPlanBeteiligung, AdministrativeOrganization, Uvp, FPlanUvp
from xplanung_light.models import FPlan, FPlanSpezExterneReferenz, FPlanBeteiligung
from xplanung_light.models import ContactOrganization
from xplanung_light.models import BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang
from xplanung_light.validators import fplan_upload_file_validator, geotiff_raster_validator, bplan_content_validator, fplan_content_validator, bplan_upload_file_validator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, Field
from crispy_forms.bootstrap import TabHolder, Tab, AccordionGroup, Accordion
from django.forms import ModelForm
from django_select2.forms import Select2MultipleWidget
from dal import autocomplete
from formset.richtext.widgets import RichTextarea
from captcha.fields import CaptchaField
from formset.utils import FormMixin
from django.core.exceptions import ValidationError
from django_clamd.validators import validate_file_infection

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
from django.forms import widgets, fields
from xplanung_light.models import BPlanBeteiligungBeitrag
from formset.fields import Activator
from formset.renderers import ButtonVariant
from formset.widgets import Button
from formset.widgets import UploadedFileInput, DateInput

from formset.collection import FormCollection
from formset.renderers.bootstrap import FormRenderer
#from formset.views import FormCollectionView
from django.forms.fields import IntegerField
from django.forms.fields import ChoiceField
from django.forms.widgets import HiddenInput

class BPlanBeteiligungForm(ModelForm):
    """
    Neue Klasse für das Anlegen und Update von Informationen zum BPlanBeteiligungsverfahren - diesmal mit django-formset
    Überlegung  mehrseitiges Formular: https://django-formset.fly.dev/bootstrap/checkout
    https://django-formset.fly.dev/form-stepper/
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...

    """
    default_renderer = FormRenderer(
        
        field_css_classes={
            'typ': 'mb-2 col-12',
            
            'bekanntmachung_datum': 'mb-2 col-4',
            'start_datum': 'mb-2 col-4',
            'end_datum': 'mb-2 col-4',
            'allow_online_beitrag': 'mb-2 col-4',
            'publikation_internet': 'mb-2 col-4',
        },
    )

    class Meta:
        model = BPlanBeteiligung
        fields = ['typ', 'beschreibung', 'bekanntmachung_datum', 'start_datum', 'end_datum' , "allow_online_beitrag", "publikation_internet"]
        widgets = {
            'beschreibung': RichTextarea(),
            'bekanntmachung_datum': DateInput(),
            'start_datum': DateInput(),
            'end_datum': DateInput(),
        }


class FPlanBeteiligungForm(ModelForm):
    """
    Neue Klasse für das Anlegen und Update von Informationen zum FPlanBeteiligungsverfahren - diesmal mit django-formset
    Überlegung  mehrseitiges Formular: https://django-formset.fly.dev/bootstrap/checkout
    https://django-formset.fly.dev/form-stepper/
    Problem bei Firefox unter debian: Richtext Formular Elemente bleiben nicht an fester Position ...

    """
   
    class Meta:
        model = FPlanBeteiligung
        fields = ['typ', 'beschreibung', 'bekanntmachung_datum', 'start_datum', 'end_datum' , "allow_online_beitrag", "publikation_internet"]
        widgets = {
            'beschreibung': RichTextarea(),
            'bekanntmachung_datum': DateInput(),
            'start_datum': DateInput(),
            'end_datum': DateInput(),
        }


class CaptchaForm(forms.Form):
    consent = forms.BooleanField(required=True, label="Ich habe die Datenschutzbestimmungen gelesen und akzeptiere sie.")
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
Die url lautet in dem Fall: /plan/<int:planid/beteiligung/<int;pk>/beitrag/create/
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
Einfache ModelForm für das BPlanBeteiligungBeitragBeitrag-Objekt
Zunächst nur soll nur das Feld beschreibung editierbar sein.
Und das über ein RichtText-widget - mal sehen, ob das so ok ist - ggf. muessen wir das Model-Field ändern.
"""
class BPlanBeteiligungBeitragForm(ModelForm):

    class Meta:
        model = BPlanBeteiligungBeitrag
        fields = ['email', 'titel', 'beschreibung']
        widgets = {
            #'beschreibung': widgets.Textarea(attrs={'cols': '80', 'rows': '3'}),
            'beschreibung': RichTextarea(attrs={'cols': '80', 'rows': '3'}),
        }


"""
Einfache ModelForm für das BPlanBeteiligungBeitragAnhang-Objekt
"""
class BeteiligungBeitragAnhangForm(ModelForm):

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
        model = BPlanBeteiligungBeitragAnhang
        fields = ['id', 'name', 'typ', 'attachment']


"""
Collection für die über ein ForeignKey mit dem BPlanBeteiligungBeitrag-Objekt verbundenen BPlanBeteiligungBeitragAnhang-Objekte.
"""
class BeteiligungBeitragAnhangCollection(FormCollection):
    legend = "Anlagen"
    add_label = "Anlage hinzufügen"
    related_field = 'beitrag'
    attachment = BeteiligungBeitragAnhangForm()
    #beitrag = BPlanBeteiligungBeitragCollection()
    min_siblings = 0
    max_siblings = 4

    def retrieve_instance(self, data):
        if data := data.get('attachment'):
            try:
                return self.instance.attachment.get(id=data.get('id') or 0)
            except (AttributeError, BPlanBeteiligungBeitragAnhang.DoesNotExist, ValueError):
                return BPlanBeteiligungBeitragAnhang(name=data.get('name'), attachment=data.get('attachment'), beitrag=self.instance)


"""
Collection für die über ein ForeignKey mit dem BPlanBeteiligung-Objekt verbundenen BPlanBeteiligungBeitrag-Objekte.
"""
class BPlanBeteiligungBeitragCollection(FormCollection):
    legend = "Ihr Beitrag"
    add_label = "Beitrag hinzufügen"
    related_field = 'bplan_beteiligung' # hier wird der releted_name des verbundenen Objketes genutzt!
    beitrag = BPlanBeteiligungBeitragForm()
    attachments = BeteiligungBeitragAnhangCollection()  # attribute name MUST match related_name (see note below)
    min_siblings = 1
    max_siblings = 1

    def retrieve_instance(self, data):
        if data := data.get('beitrag'):
            try:
                return self.instance.beitrag.get(id=data.get('id') or 0)
            except (AttributeError, BPlanBeteiligungBeitrag.DoesNotExist, ValueError):
                #print("BPlanBeteiligungBeitrag nicht gefunden!")
                return BPlanBeteiligungBeitrag(beschreibung=data.get('beschreibung'), bplan_beteiligung=self.instance)


class BPlanBeteiligungCollection(FormCollection):
    default_renderer = FormRenderer(field_css_classes='mb-3')
    bplan_beteiligung = BPlanBeteiligungFormFormset()
    beitrag = BPlanBeteiligungBeitragCollection()
    captcha = CaptchaForm()

    
