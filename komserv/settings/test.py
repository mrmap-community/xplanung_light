from pathlib import Path
# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Wichtig: Das dritte parent, weil wir jetzt ein Verzeichnis tiefer sitzen!
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# komserv/settings/test.py – bewusst NICHT in .gitignore, da keine echten Secrets.
# Der Wert ist ein Platzhalter ohne Bewandtnis: hier laufen keine echten Sitzungen.
# (Bewusst kein 'django-insecure'-Präfix und länger als 50 Zeichen, damit weder die
# mitgeführten Prüfungen der App noch 'check --deploy' in jedem Testlauf anschlagen.)
SECRET_KEY = 'testlauf-platzhalter-schluessel-ohne-bewandtnis-8173456789abcdef'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': BASE_DIR / 'db.sqlite3',
        'TEST': {'NAME': str(BASE_DIR / 'test_db.sqlite3')},
    }
}
REQUESTS_PROXIES = None