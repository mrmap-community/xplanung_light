from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from xplanung_light.models import BPlan

admin.site.register(BPlan, LeafletGeoAdmin)

