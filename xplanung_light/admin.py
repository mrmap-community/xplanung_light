from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from xplanung_light.models import BPlan, AdministrativeOrganization, License
from simple_history.admin import SimpleHistoryAdmin

class HistoryGeoAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
   pass

admin.site.register(BPlan, HistoryGeoAdmin)
admin.site.register(License, HistoryGeoAdmin)
admin.site.register(AdministrativeOrganization, HistoryGeoAdmin)
