from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from xplanung_light.models import BPlan, AdministrativeOrganization

admin.site.register(BPlan, LeafletGeoAdmin)
admin.site.register(AdministrativeOrganization, LeafletGeoAdmin)
