from django.urls import path
from xplanung_light import views
from django.contrib.auth import views as auth_views
from xplanung_light.views import BPlanCreateView, BPlanUpdateView, BPlanDeleteView, BPlanListView
from xplanung_light.views import BPlanDetailXmlRasterView

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/login/", auth_views.LoginView.as_view(next_page="home"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="home"), name='logout'),
    # https://dev.to/donesrom/how-to-set-up-django-built-in-registration-in-2023-41hg
    path("register/", views.register, name = "register"),
    path("about/", views.about, name="about"),
    path("bplan/", BPlanListView.as_view(), name="bplan-list"),
    path("bplan/create/", BPlanCreateView.as_view(), name="bplan-create"),
    path("bplan/<int:pk>/update/", BPlanUpdateView.as_view(), name="bplan-update"),
    path("bplan/<int:pk>/delete/", BPlanDeleteView.as_view(), name="bplan-delete"),
    path("bplan/<int:pk>/xplan/", BPlanDetailXmlRasterView.as_view(template_name="xplanung_light/bplan_template_xplanung_raster_6.xml"), name="bplan-export-xplan-raster-6"),
]
