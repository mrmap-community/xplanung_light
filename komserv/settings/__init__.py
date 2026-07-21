import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / '.my_xplanung_light_env.json'

from .base import *

try:
    with open(CONFIG_FILE) as config_file:
        config = json.load(config_file)
        if config['ENV_NAME'] == 'dev':
            from .dev import *
        if config['ENV_NAME'] == 'prod':
            from .prod import *
except FileNotFoundError:
    # If JSON is missing, it safely falls back to base settings
    pass