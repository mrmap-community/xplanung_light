from django.urls import path, include
from xplanung_light.views import views
from django.contrib.auth import views as auth_views
from xplanung_light.views.bplan import BPlanCreateView, BPlanUpdateView, BPlanDeleteView, BPlanListView, BPlanDetailView, BPlanListViewHtml
from xplanung_light.views.fplan import FPlanCreateView, FPlanUpdateView, FPlanDeleteView, FPlanListView, FPlanDetailView, FPlanListViewHtml
from xplanung_light.views.fplan import FPlanDetailXPlanLightView, FPlanDetailXPlanLightZipView
from xplanung_light.views.bplan import BPlanDetailXPlanLightView, BPlanDetailXPlanLightZipView
from xplanung_light.views.bplanspezexternereferenz import BPlanSpezExterneReferenzCreateView, BPlanSpezExterneReferenzUpdateView, BPlanSpezExterneReferenzDeleteView, BPlanSpezExterneReferenzListView
from xplanung_light.views.fplanspezexternereferenz import FPlanSpezExterneReferenzCreateView, FPlanSpezExterneReferenzUpdateView, FPlanSpezExterneReferenzDeleteView, FPlanSpezExterneReferenzListView
from xplanung_light.views.bplanbeteiligung import BPlanBeteiligungCreateView, BPlanBeteiligungUpdateView, BPlanBeteiligungDeleteView, BPlanBeteiligungListView
from xplanung_light.views.fplanbeteiligung import FPlanBeteiligungCreateView, FPlanBeteiligungUpdateView, FPlanBeteiligungDeleteView, FPlanBeteiligungListView
from xplanung_light.views.uvp import UvpCreateView, UvpUpdateView, UvpDeleteView, UvpListView
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
    path("bplan/<int:pk>/overview-map/", views.ows_bplan_overview, name="bplan-overview-map"),
    # BPlan HTML List - für GetFeatureInfo
    path("bplan/html-list/", BPlanListViewHtml.as_view(), name="bplan-list-html"),
    # BPlan XPlan Export
    path("bplan/<int:pk>/xplan/", BPlanDetailXPlanLightView.as_view(template_name="xplanung_light/bplan_template_xplanung_light_6.xml"), name="bplan-export-xplan-raster-6"),
    path("bplan/<int:pk>/xplan-zip/", BPlanDetailXPlanLightZipView.as_view(template_name="xplanung_light/bplan_template_xplanung_light_6.xml"), name="bplan-export-xplan-raster-6-zip"),
    path("bplan/<int:pk>/iso19139/", BPlanDetailXPlanLightView.as_view(template_name="xplanung_light/bplan_template_iso19139.xml"), name="bplan-export-iso19139"),
    path("bplan/import/", views.bplan_import, name="bplan-import"),
    path("bplan/import-archiv/", views.bplan_import_archiv, name="bplan-import-archiv"),
    # BPlan Anlagen
    path("bplan/<int:planid>/attachment/create/", BPlanSpezExterneReferenzCreateView.as_view(), name="bplanattachment-create"),
    path("bplan/<int:planid>/attachment/", BPlanSpezExterneReferenzListView.as_view(), name="bplanattachment-list"),
    path("bplan/<int:planid>/attachment/<int:pk>/update/", BPlanSpezExterneReferenzUpdateView.as_view(), name="bplanattachment-update"),
    path("bplan/<int:planid>/attachment/<int:pk>/delete/", BPlanSpezExterneReferenzDeleteView.as_view(), name="bplanattachment-delete"),
    path("bplanattachment/<int:pk>/", views.get_bplan_attachment, name="bplanattachment-download"),
    # BPlan Beteiligungen
    path("bplan/<int:planid>/beteiligung/create/", BPlanBeteiligungCreateView.as_view(), name="bplanbeteiligung-create"),
    path("bplan/<int:planid>/beteiligung/", BPlanBeteiligungListView.as_view(), name="bplanbeteiligung-list"),
    path("bplan/<int:planid>/beteiligung/<int:pk>/update/", BPlanBeteiligungUpdateView.as_view(), name="bplanbeteiligung-update"),
    path("bplan/<int:planid>/beteiligung/<int:pk>/delete/", BPlanBeteiligungDeleteView.as_view(), name="bplanbeteiligung-delete"),
    # BPlan UVP Info
    path("bplan/<int:planid>/uvp/create/", UvpCreateView.as_view(), name="uvp-create"),
    path("bplan/<int:planid>/uvp/", UvpListView.as_view(), name="uvp-list"),
    path("bplan/<int:planid>/uvp/<int:pk>/update/", UvpUpdateView.as_view(), name="uvp-update"),
    path("bplan/<int:planid>/uvp/<int:pk>/delete/", UvpDeleteView.as_view(), name="uvp-delete"),
    # FPlan
    # BPlan CRUD
    path("fplan/", FPlanListView.as_view(), name="fplan-list"),
    path("fplan/create/", FPlanCreateView.as_view(), name="fplan-create"),
    path("fplan/<int:pk>/update/", FPlanUpdateView.as_view(), name="fplan-update"),
    path("fplan/<int:pk>/delete/", FPlanDeleteView.as_view(), name="fplan-delete"),
    path("fplan/<int:pk>/", FPlanDetailView.as_view(), name="fplan-detail"),
    path("fplan/<int:pk>/overview-map/", views.ows_fplan_overview, name="fplan-overview-map"),
    # FPlan HTML List - für GetFeatureInfo
    #path("fplan/html-list/", FPlanListViewHtml.as_view(), name="fplan-list-html"),
    # FPlan XPlan Export
    path("fplan/<int:pk>/xplan/", FPlanDetailXPlanLightView.as_view(template_name="xplanung_light/fplan_template_xplanung_light_6.xml"), name="fplan-export-xplan-raster-6"),
    path("fplan/<int:pk>/xplan-zip/", FPlanDetailXPlanLightZipView.as_view(template_name="xplanung_light/fplan_template_xplanung_light_6.xml"), name="fplan-export-xplan-raster-6-zip"),
    path("fplan/<int:pk>/iso19139/", FPlanDetailXPlanLightView.as_view(template_name="xplanung_light/fplan_template_iso19139.xml"), name="fplan-export-iso19139"),
    path("fplan/import/", views.fplan_import, name="fplan-import"),
    path("fplan/import-archiv/", views.fplan_import_archiv, name="fplan-import-archiv"),
    # FPlan Beteiligungen
    path("fplan/<int:planid>/beteiligung/create/", FPlanBeteiligungCreateView.as_view(), name="fplanbeteiligung-create"),
    path("fplan/<int:planid>/beteiligung/", FPlanBeteiligungListView.as_view(), name="fplanbeteiligung-list"),
    path("fplan/<int:planid>/beteiligung/<int:pk>/update/", FPlanBeteiligungUpdateView.as_view(), name="fplanbeteiligung-update"),
    path("fplan/<int:planid>/beteiligung/<int:pk>/delete/", FPlanBeteiligungDeleteView.as_view(), name="fplanbeteiligung-delete"),
     # FPlan Anlagen
    path("fplan/<int:planid>/attachment/create/", FPlanSpezExterneReferenzCreateView.as_view(), name="fplanattachment-create"),
    path("fplan/<int:planid>/attachment/", FPlanSpezExterneReferenzListView.as_view(), name="fplanattachment-list"),
    path("fplan/<int:planid>/attachment/<int:pk>/update/", FPlanSpezExterneReferenzUpdateView.as_view(), name="fplanattachment-update"),
    path("fplan/<int:planid>/attachment/<int:pk>/delete/", FPlanSpezExterneReferenzDeleteView.as_view(), name="fplanattachment-delete"),
    path("fplanattachment/<int:pk>/", views.get_fplan_attachment, name="fplanattachment-download"),
    # Organisationen
    path("organization/<int:pk>/ows/", views.ows, name="ows"),
    # Organisations XPlan-Liste für GetFeatureInfo - hier müssen alle Plantypen zurückgeliefert werden können
    path("organization/<int:pk>/xplan/html/", views.xplan_html, name="xplan-list-html"),
    # 
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
