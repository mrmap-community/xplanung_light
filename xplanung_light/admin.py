from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from xplanung_light.models import BPlan, AdministrativeOrganization, License, ContactOrganization, Uvp
from simple_history.admin import SimpleHistoryAdmin
# https://django-organizations.readthedocs.io/en/latest/cookbook.html#extending-the-base-admin-classes
"""
from organizations.base_admin import (
    BaseOwnerInline,
    BaseOrganizationAdmin,
    BaseOrganizationUserAdmin,
    BaseOrganizationOwnerAdmin,
)
"""
from xplanung_light.models import AdminOrgaUser

class HistoryGeoAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
   pass


admin.site.register(BPlan, HistoryGeoAdmin)
admin.site.register(License, HistoryGeoAdmin)
admin.site.register(Uvp, HistoryGeoAdmin)
admin.site.register(ContactOrganization, HistoryGeoAdmin)
admin.site.register(AdministrativeOrganization, HistoryGeoAdmin)
admin.site.register(AdminOrgaUser)
