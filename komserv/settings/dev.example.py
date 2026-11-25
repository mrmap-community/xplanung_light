from komserv.settings.base import INSTALLED_APPS, MIDDLEWARE
import os

DEBUG = True

# Django default Logging
# https://docs.djangoproject.com/en/6.1/ref/logging/#default-logging-definition

ALLOWED_HOSTS = []

# Debug-Toolbar: in base.py bewusst nicht mehr enthalten, hier selbst ergänzen.
# Die beiden Grundlagen-Listen muss man sich zuerst holen — dev.py wird als eigenes
# Settings-Modul geladen, die Werte aus base.py liegen dort nicht einfach im Namespace.

INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1', '::1']

# Geocoder BKG
BKG_GEOCODER_CONFIG = {
    'base_url': 'https://sg.geodatenzentrum.de/gdz_geokodierung__',
    'api_key': '{api_key}',
}

REQUESTS_PROXIES = {}
