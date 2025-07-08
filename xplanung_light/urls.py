from django.urls import path, include
from xplanung_light import views
from django.contrib.auth import views as auth_views
from xplanung_light.views import BPlanCreateView, BPlanUpdateView, BPlanDeleteView, BPlanListView
from xplanung_light.views import BPlanSpezExterneReferenzCreateView, BPlanSpezExterneReferenzUpdateView, BPlanSpezExterneReferenzDeleteView, BPlanSpezExterneReferenzListView
from xplanung_light.views import BPlanBeteiligungCreateView, BPlanBeteiligungUpdateView, BPlanBeteiligungDeleteView, BPlanBeteiligungListView
from xplanung_light.views import BPlanDetailXPlanLightView, BPlanDetailXPlanLightZipView
from xplanung_light.views import AdministrativeOrganizationPublishingListView
from xplanung_light.views import AdministrativeOrganizationAutocomplete
from xplanung_light.views import ContactOrganizationCreateView, ContactOrganizationListView, ContactOrganizationUpdateView, ContactOrganizationDeleteView
from django.urls import re_path as url

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/login/", auth_views.LoginView.as_view(next_page="home"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="home"), name='logout'),
    # https://dev.to/donesrom/how-to-set-up-django-built-in-registration-in-2023-41hg
    path("register/", views.register, name = "register"),
    path("about/", views.about, name="about"),
    # BPlan CRUD
    path("bplan/", BPlanListView.as_view(), name="bplan-list"),
    path("bplan/create/", BPlanCreateView.as_view(), name="bplan-create"),
    path("bplan/<int:pk>/update/", BPlanUpdateView.as_view(), name="bplan-update"),
    path("bplan/<int:pk>/delete/", BPlanDeleteView.as_view(), name="bplan-delete"),
    # BPlan XPlan Export
    path("bplan/<int:pk>/xplan/", BPlanDetailXPlanLightView.as_view(template_name="xplanung_light/bplan_template_xplanung_light_6.xml"), name="bplan-export-xplan-raster-6"),
    path("bplan/<int:pk>/xplan-zip/", BPlanDetailXPlanLightZipView.as_view(template_name="xplanung_light/bplan_template_xplanung_light_6.xml"), name="bplan-export-xplan-raster-6-zip"),
    path("bplan/<int:pk>/iso19139/", BPlanDetailXPlanLightView.as_view(template_name="xplanung_light/bplan_template_iso19139.xml"), name="bplan-export-iso19139"),
    path("bplan/import/", views.bplan_import, name="bplan-import"),
    path("bplan/import-archiv/", views.bplan_import_archiv, name="bplan-import-archiv"),
    # BPlan Anlagen
    path("bplan/<int:bplanid>/attachment/create/", BPlanSpezExterneReferenzCreateView.as_view(), name="bplanattachment-create"),
    path("bplan/<int:bplanid>/attachment/", BPlanSpezExterneReferenzListView.as_view(), name="bplanattachment-list"),
    path("bplan/<int:bplanid>/attachment/<int:pk>/update/", BPlanSpezExterneReferenzUpdateView.as_view(), name="bplanattachment-update"),
    path("bplan/<int:bplanid>/attachment/<int:pk>/delete/", BPlanSpezExterneReferenzDeleteView.as_view(), name="bplanattachment-delete"),
    path("bplanattachment/<int:pk>/", views.get_bplan_attachment, name="bplanattachment-download"),
    # BPlan Beteiligungen
    path("bplan/<int:bplanid>/beteiligung/create/", BPlanBeteiligungCreateView.as_view(), name="bplanbeteiligung-create"),
    path("bplan/<int:bplanid>/beteiligung/", BPlanBeteiligungListView.as_view(), name="bplanbeteiligung-list"),
    path("bplan/<int:bplanid>/beteiligung/<int:pk>/update/", BPlanBeteiligungUpdateView.as_view(), name="bplanbeteiligung-update"),
    path("bplan/<int:bplanid>/beteiligung/<int:pk>/delete/", BPlanBeteiligungDeleteView.as_view(), name="bplanbeteiligung-delete"),
    # Organisationen
    path("organization/<int:pk>/ows/", views.ows, name="ows"),
    path("organization/publishing/", AdministrativeOrganizationPublishingListView.as_view(), name="organization-publishing-list"),
    url(
        r'^administrativeorganization-autocomplete/$',
        AdministrativeOrganizationAutocomplete.as_view(),
        name='administrativeorganization-autocomplete',
    ),
    # Kontaktorganisationen
    path("contactorganization/create/", ContactOrganizationCreateView.as_view(), name="contactorganization-create"),
    path("contactorganization/", ContactOrganizationListView.as_view(), name="contactorganization-list"),
    path("contactorganization/<int:pk>/update/", ContactOrganizationUpdateView.as_view(), name="contactorganization-update"),
    path("contactorganization/<int:pk>/delete/", ContactOrganizationDeleteView.as_view(), name="contactorganization-delete"),
    # Dokumentation
    path('docs/', include('docs.urls')),
]
