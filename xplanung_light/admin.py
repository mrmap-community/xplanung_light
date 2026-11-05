from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from leaflet.admin import LeafletGeoAdmin
from simple_history.admin import SimpleHistoryAdmin

from xplanung_light.models import (AdministrativeOrganization, BPlan, BPlanBeteiligung, ConsentOption,
                                   ContactOrganization, License, UserProfile, Uvp)

# from formset.admin import ModelAdmin - erst in späteren Versionen verfügbar
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


class UserAdmin(BaseUserAdmin):
    list_filter = BaseUserAdmin.list_filter + ("last_login",)  # pyright: ignore[reportOperatorIssue]
    list_display = BaseUserAdmin.list_display + ("last_login",)  # pyright: ignore[reportOperatorIssue]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class RichtextAdmin(SimpleHistoryAdmin):
    # Herausnehmen der Richtext Felder - hierfür benötigen wir spezielle django-formset forms
    exclude = ["beschreibung"]


admin.site.register(BPlanBeteiligung, RichtextAdmin)


class HistoryGeoAdmin(SimpleHistoryAdmin, LeafletGeoAdmin):
    pass


admin.site.register(BPlan, HistoryGeoAdmin)
admin.site.register(License, HistoryGeoAdmin)
admin.site.register(Uvp, HistoryGeoAdmin)
admin.site.register(ContactOrganization, HistoryGeoAdmin)
admin.site.register(AdministrativeOrganization, HistoryGeoAdmin)
admin.site.register(AdminOrgaUser)

# https://docs.djangoproject.com/en/4.2/topics/auth/customizing/
# Define an inline admin descriptor for Employee model
# which acts a bit like a singleton


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "UserProfiles"


# admin.site.register(BPlanBeteiligung, SimpleHistoryAdmin)
# admin.site.register(ConsentOption)
