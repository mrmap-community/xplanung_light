from django_filters import FilterSet, CharFilter, ModelChoiceFilter, NumberFilter, BaseInFilter, BooleanFilter
from .models import BPlan, AdministrativeOrganization, FPlan
from django.contrib.gis.geos import Polygon
from django.forms import CheckboxInput
from django.db.models import Q, Exists, OuterRef

def bbox_filter(queryset, value):
    #print("value from bbox_filter: " + value)
    # extract bbox from cs numerical values
    geom = Polygon.from_bbox(value.split(','))
    #print(geom)
    # 7.51461,50.31417,7.51563,50.31544
    return queryset.filter(geltungsbereich__bboverlaps=geom)

# https://django-filter.readthedocs.io/en/stable/guide/usage.html#filtering-the-related-queryset-for-modelchoicefilter
# https://johnnymetz.com/posts/five-ways-to-get-django-objects-with-a-related-object/
def organizations(request):
    if request is None:
            return AdministrativeOrganization.objects.only("pk", "name", "name_part", "type")
    if request.user.is_superuser:
            return AdministrativeOrganization.objects.only("pk", "name", "name_part", "type")
    else:
        return AdministrativeOrganization.objects.filter(users=request.user).only("pk", "name", "name_part", "type")

def bplan_organizations(request):
    if request is None:
        return AdministrativeOrganization.objects.filter(Exists(BPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")
    if request.user.is_superuser:
        return AdministrativeOrganization.objects.filter(Exists(BPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")
    else:
        return AdministrativeOrganization.objects.filter(users=request.user).filter(Exists(BPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")

def fplan_organizations(request):
    if request is None:
        return AdministrativeOrganization.objects.filter(Exists(FPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")
    if request.user.is_superuser:
        return AdministrativeOrganization.objects.filter(Exists(FPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")
    else:
        return AdministrativeOrganization.objects.filter(users=request.user).filter(Exists(FPlan.objects.filter(gemeinde=OuterRef("pk")))).only("pk", "name", "name_part", "type")


# https://stackoverflow.com/questions/68592837/custom-filter-with-django-filters
class BPlanFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    bbox = CharFilter(method='bbox_filter', label='BBOX')
    gemeinde = ModelChoiceFilter(queryset=bplan_organizations)
    in_beteiligung = BooleanFilter(
        widget=CheckboxInput(),
        method='laufende_beteiligung',
        label='Laufendes Beteiligungsverfahren',
    )
    is_public = BooleanFilter(
        widget=CheckboxInput(),
        method='publiziert',
        label='Öffentlich sichtbar',
    )
    
    class Meta:
        model = BPlan
        fields = ["name", "gemeinde", "planart", "bbox"]

    def laufende_beteiligung(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(count_current_beteiligungen__gte=1)
    
    def publiziert(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(public=True)
    
    def bbox_filter(self, queryset, name, value):
        #print("name from DocumentFilter.bbox_filter: " + name)
        return bbox_filter(queryset, value)


class FPlanFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    bbox = CharFilter(method='bbox_filter', label='BBOX')
    gemeinde = ModelChoiceFilter(queryset=fplan_organizations)
    in_beteiligung = BooleanFilter(
        widget=CheckboxInput(),
        method='laufende_beteiligung',
        label='Laufendes Beteiligungsverfahren',
    )
    is_public = BooleanFilter(
        widget=CheckboxInput(),
        method='publiziert',
        label='Öffentlich sichtbar',
    )

    class Meta:
        model = FPlan
        fields = ["name", "gemeinde", "planart", "bbox"]

    def laufende_beteiligung(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(count_current_beteiligungen__gte=1)

    def publiziert(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(public=True)
    
    def bbox_filter(self, queryset, name, value):
        #print("name from DocumentFilter.bbox_filter: " + name)
        return bbox_filter(queryset, value)
    

class NumberInFilter(BaseInFilter, NumberFilter):
    pass


class BPlanFilterHtml(FilterSet):
    pk__in = NumberInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = BPlan
        fields = ["id"] 


class FPlanFilterHtml(FilterSet):
    pk__in = NumberInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = FPlan
        fields = ["id"] 

class BPlanIdFilter(FilterSet):
    bplan_id__in = NumberInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = BPlan
        fields = ["id"] 

class FPlanIdFilter(FilterSet):
    fplan_id__in = NumberInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = FPlan
        fields = ["id"] 