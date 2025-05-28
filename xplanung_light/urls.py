from django.urls import path
from xplanung_light import views

urlpatterns = [
    path("", views.home, name="home"),
]