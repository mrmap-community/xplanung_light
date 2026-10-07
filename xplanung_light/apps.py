from django.apps import AppConfig
import os
import mapscript
import tempfile
import logging
# Instanziierung für das aktuelle Modul
logger = logging.getLogger(__name__)


class XplanungLightConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'xplanung_light'
    mapserver_config = None

    def ready(self):
        mapserver_version = mapscript.msGetVersionInt()
        if mapserver_version > 80000:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.conf') as tmp:
                tmp.write("CONFIG\nEND")
                tmp_path = tmp.name
            os.environ['MAPSERVER_CONFIG_FILE'] = tmp_path
            self.mapserver_config = mapscript.configObj()
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.error(
                    'Kann die temporäre Mapserver Konfigurationsdatei nicht löschen')
