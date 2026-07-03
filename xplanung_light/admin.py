from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin
from xplanung_light.models import BPlan, AdministrativeOrganization, License, ContactOrganization, Uvp, ConsentOption, BPlanBeteiligung
from simple_history.admin import SimpleHistoryAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from xplanung_light.models import UserProfile
#from formset.admin import ModelAdmin - erst in späteren Versionen verfügbar
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

class RichtextAdmin(SimpleHistoryAdmin):
   """
   Herausnehmen der Richtext Felder - hierfür benötigen wir spezielle django-formset forms
   """
   def get_form(self, request, obj=None, **kwargs):
        self.exclude = []
        self.exclude.append('beschreibung')
        return super().get_form(request, obj, **kwargs)


admin.site.register(BPlanBeteiligung, RichtextAdmin)


class HistoryGeoAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
   pass


admin.site.register(BPlan, HistoryGeoAdmin)
admin.site.register(License, HistoryGeoAdmin)
admin.site.register(Uvp, HistoryGeoAdmin)
admin.site.register(ContactOrganization, HistoryGeoAdmin)
admin.site.register(AdministrativeOrganization, HistoryGeoAdmin)
admin.site.register(AdminOrgaUser)

#https://docs.djangoproject.com/en/4.2/topics/auth/customizing/
# Define an inline admin descriptor for Employee model
# which acts a bit like a singleton
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "UserProfiles"


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)



#admin.site.register(BPlanBeteiligung, SimpleHistoryAdmin)
#admin.site.register(ConsentOption)