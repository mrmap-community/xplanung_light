import json
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / '.my_xplanung_light_env.json'

from .base import *

if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as config_file:
        config = json.load(config_file)
        env = config.get('ENV_NAME')
        
        if env == 'dev':
            from .dev import *
        elif env == 'prod':
            from .prod import *
else:
    # Hilft beim Debuggen unter Gunicorn: Zeigt im Log, wo gesucht wurde
    print(f"WARNUNG: Umgebungskonfiguration nicht gefunden unter: {CONFIG_FILE}")
    raise ImproperlyConfigured(
        f"Umgebungskonfiguration fehlt: {CONFIG_FILE}. "
        "Ohne explizite dev/prod-Config wird aus Sicherheitsgründen nicht gestartet."
    )