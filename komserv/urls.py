"""
URL configuration for komserv project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from debug_toolbar.toolbar import debug_toolbar_urls
from organizations.backends import invitation_backend
from django.urls import re_path as url

urlpatterns = [
    url(r'^accounts/', include('organizations.urls')),
    url(r'^invitations/', include(invitation_backend().get_urls())),
    path("", include("xplanung_light.urls")),
    path('admin/', admin.site.urls)
]
urlpatterns += staticfiles_urlpatterns() + debug_toolbar_urls()