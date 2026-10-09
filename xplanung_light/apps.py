import logging
import os
import tempfile

import mapscript
from django.apps import AppConfig

# Instanziierung für das aktuelle Modul
logger = logging.getLogger(__name__)


class XplanungLightConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'xplanung_light'
    mapserver_config = None

    def ready(self):
        mapserver_version = mapscript.msGetVersionInt()
        if mapserver_version > 80000:
            with tempfile.NamedTemporaryFile(mode='w', delete_on_close=False, suffix='.conf') as tmp:
                tmp.write("CONFIG\nEND")
                tmp.close()
                tmp_path = tmp.name
                os.environ['MAPSERVER_CONFIG_FILE'] = tmp_path
                self.mapserver_config = mapscript.configObj()
