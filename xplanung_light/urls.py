from django.urls import path, include
from xplanung_light.views import views
from django.contrib.auth import views as auth_views
from xplanung_light.views.bplan import BPlanCreateView, BPlanUpdateView, BPlanDeleteView, BPlanListView, BPlanDetailView, BPlanListViewHtml
from xplanung_light.views.bplan import BPlanDetailXPlanLightView, BPlanDetailXPlanLightZipView
from xplanung_light.views.bplanspezexternereferenz import BPlanSpezExterneReferenzCreateView, BPlanSpezExterneReferenzUpdateView, BPlanSpezExterneReferenzDeleteView, BPlanSpezExterneReferenzListView
from xplanung_light.views.bplanbeteiligung import BPlanBeteiligungCreateView, BPlanBeteiligungUpdateView, BPlanBeteiligungDeleteView, BPlanBeteiligungListView
from xplanung_light.views.administrativeorganization import AdministrativeOrganizationPublishingListView, AdministrativeOrganizationAutocomplete, AdministrativeOrganizationListView, AdministrativeOrganizationUpdateView
from xplanung_light.views.contactorganization import ContactOrganizationCreateView, ContactOrganizationListView, ContactOrganizationUpdateView, ContactOrganizationDeleteView
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
    path("bplan/<int:pk>/", BPlanDetailView.as_view(), name="bplan-detail"),
    # BPlan HTML List - für GetFeatureInfo
    path("bplan/html-list/", BPlanListViewHtml.as_view(), name="bplan-list-html"),
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
    # Organisationen für die der Nutzer is_amin=True hat
    path("organization/", AdministrativeOrganizationListView.as_view(), name="organization-list"),
    path("organization/<int:pk>/update/", AdministrativeOrganizationUpdateView.as_view(), name="organization-update"),
    # Kontaktorganisationen
    path("contact/create/", ContactOrganizationCreateView.as_view(), name="contact-create"),
    path("contact/", ContactOrganizationListView.as_view(), name="contact-list"),
    path("contact/<int:pk>/update/", ContactOrganizationUpdateView.as_view(), name="contact-update"),
    path("contact/<int:pk>/delete/", ContactOrganizationDeleteView.as_view(), name="contact-delete"),
    # Dokumentation
    path('docs/', include('docs.urls')),
]
