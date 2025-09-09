from django_filters import FilterSet, CharFilter, ModelChoiceFilter, NumberFilter, BaseInFilter
from .models import BPlan, AdministrativeOrganization, FPlan
from django.contrib.gis.geos import Polygon
from django.db.models import Q

def bbox_filter(queryset, value):
    #print("value from bbox_filter: " + value)
    # extract bbox from cs numerical values
    geom = Polygon.from_bbox(value.split(','))
    #print(geom)
    # 7.51461,50.31417,7.51563,50.31544
    return queryset.filter(geltungsbereich__bboverlaps=geom)

# https://django-filter.readthedocs.io/en/stable/guide/usage.html#filtering-the-related-queryset-for-modelchoicefilter
def organizations(request):
    #print("organizations invoked")
    if request is None:
        return AdministrativeOrganization.objects.only("pk", "name", "name_part", "type")
    if request.user.is_superuser:
        return AdministrativeOrganization.objects.only("pk", "name", "name_part", "type")
    else:
        return AdministrativeOrganization.objects.filter(users=request.user).only("pk", "name", "name_part", "type")

# https://stackoverflow.com/questions/68592837/custom-filter-with-django-filters
class BPlanFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    bbox = CharFilter(method='bbox_filter', label='BBOX')
    gemeinde = ModelChoiceFilter(queryset=organizations)

    class Meta:
        model = BPlan
        fields = ["name", "gemeinde", "planart", "bbox"]


    def bbox_filter(self, queryset, name, value):
        #print("name from DocumentFilter.bbox_filter: " + name)
        return bbox_filter(queryset, value)


class FPlanFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains')
    bbox = CharFilter(method='bbox_filter', label='BBOX')
    gemeinde = ModelChoiceFilter(queryset=organizations)

    class Meta:
        model = FPlan
        fields = ["name", "gemeinde", "planart", "bbox"]


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