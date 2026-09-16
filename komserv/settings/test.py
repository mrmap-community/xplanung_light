from pathlib import Path
# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Wichtig: Das dritte parent, weil wir jetzt ein Verzeichnis tiefer sitzen!
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# komserv/settings/test.py – bewusst NICHT in .gitignore, da keine echten Secrets
SECRET_KEY = 'ci-test-key-not-a-real-secret'
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': BASE_DIR / 'db.sqlite3',
        'TEST': {'NAME': str(BASE_DIR / 'test_db.sqlite3')},
    }
}