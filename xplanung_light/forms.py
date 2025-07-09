from datetime import timedelta
from django.utils import timezone

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User 
from xplanung_light.models import BPlan, BPlanSpezExterneReferenz, BPlanBeteiligung, AdministrativeOrganization
from xplanung_light.models import ContactOrganization
from xplanung_light.validators import xplan_content_validator, xplan_upload_file_validator, geotiff_raster_validator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, Field
from crispy_forms.bootstrap import TabHolder, Tab, AccordionGroup, Accordion
from django.forms import ModelForm
from django_select2.forms import Select2MultipleWidget
from dal import autocomplete

class BPlanImportForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen Plan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="BPlan GML", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanImportForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Bebauungsplan importieren", "file", "confirm"), Submit("submit", "Hochladen"))

class BPlanImportArchivForm(forms.Form):
    confirm = forms.BooleanField(label="Vorhandenen Plan überschreiben", initial=False, required=False)
    file = forms.FileField(required=True, label="BPlan ZIP-Archiv", validators=[xplan_upload_file_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanImportArchivForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(Fieldset("Bebauungsplanarchiv importieren", "file", "confirm"), Submit("submit", "Hochladen"))


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


class BPlanBeteiligungForm(forms.ModelForm):
    #typ = forms.CharField(required=True, label="Typ des Anhangs")
    #name = forms.CharField
    #attachment = forms.FileField(required=True, label="Anlage", validators=[xplan_content_validator])
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super(BPlanBeteiligungForm, self).__init__(*args, **kwargs)
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
       model = BPlanBeteiligung
       fields = ["typ", "bekanntmachung_datum", "start_datum", "end_datum", "publikation_internet"] # list of fields you want from model


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
        self.fields['inkrafttretens_datum'].widget = forms.DateInput(          
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
                            "inkrafttretens_datum",
                        ),
                        Column(
                            "ausfertigungs_datum",
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
            ),
            Submit("submit", "Erstellen")
        )

    class Meta:
        model = BPlan
        fields = ["name", 
                  "nummer", 
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "aufstellungsbeschluss_datum", 
                  "satzungsbeschluss_datum",
                  "rechtsverordnungs_datum",
                  "inkrafttretens_datum", 
                  "ausfertigungs_datum", 
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
        self.fields['inkrafttretens_datum'].widget = forms.DateInput(          
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
        self.fields['gemeinde'].widget = GemeindeSelect2(attrs = {'onchange' : "zoomToSelectedOptionsExtent(this);"})
        #self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
        self.helper.layout = Layout(
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
                            "inkrafttretens_datum",
                        ),
                        Column(
                            "ausfertigungs_datum",
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
            ),
            Submit("submit", "Aktualisieren")
        )

    class Meta:
        model = BPlan

        fields = ["name", 
                  "nummer", 
                  "geltungsbereich", 
                  "gemeinde", 
                  "planart",
                  "aufstellungsbeschluss_datum", 
                  "satzungsbeschluss_datum",
                  "rechtsverordnungs_datum",
                  "inkrafttretens_datum", 
                  "ausfertigungs_datum", 
                  "staedtebaulicher_vertrag",
                  "erschliessungs_vertrag",
                  "durchfuehrungs_vertrag",
                  "gruenordnungsplan",
                ]
        

class ContactOrganizationCreateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur Kontaktstelle",
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
                    'homepage',
                ),
            ),
            Submit("submit", "Erstellen"),
        )

    class Meta:
        model = ContactOrganization

        fields = ["name", "unit", "person", "email", "phone", "facsimile", "homepage", ]


class ContactOrganizationUpdateForm(ModelForm):
    """
    for crispy-forms
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Fieldset(
                "Informationen zur Kontaktstelle",
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
                    'homepage',
                ),
            ),
            Submit("submit", "Aktualisieren"),
        )

    class Meta:
        model = ContactOrganization

        fields = ["name", "unit", "person", "email", "phone", "facsimile", "homepage", ]