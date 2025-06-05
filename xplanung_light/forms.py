from datetime import timedelta
from django.utils import timezone

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User 
from xplanung_light.models import BPlan
from xplanung_light.validators import xplan_content_validator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, Field
from crispy_forms.bootstrap import TabHolder, Tab, AccordionGroup, Accordion
from django.forms import ModelForm

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


class RegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

# https://docs.djangoproject.com/en/5.2/ref/forms/fields/
class GemeindeSelect(forms.Select):

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
        self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
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
                "Pflichtfelder Rheinland-Pfalz",
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
        self.fields['gemeinde'].widget = GemeindeSelect(attrs = {'onchange' : "zoomToExtent(this);"})
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
                "Pflichtfelder Rheinland-Pfalz",
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