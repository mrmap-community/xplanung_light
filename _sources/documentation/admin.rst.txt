##############
Administration
##############

**********************************
Verwaltung der Zustimmungsoptionen
**********************************

Im System lassen sich Zustimmungsoptionen (consent options) deklarieren. Sie beziehen sich auf eine Rolle und werden
im Programm an verschiedenen Stellen abgefragt.

Anwendungsfälle

* Registrierung - TBD
* Formular für Stellungnahme 
* Nutzungsbedingungen des Systems

.. image:: ../media/xplanung_light_admin_consentoptions.png

************************************
Freigabe von Administrationsanfragen
************************************

.. image:: ../media/xplanung_light_admin_request_admin_list.png

.. image:: ../media/xplanung_light_admin_request_admin_confirm.png

***********************
Django Admin Oberfläche
***********************

.. image:: ../media/xplanung_light_admin_admin.png

Verwaltung standardisierter Lizenzen
####################################

.. image:: ../media/xplanung_light_admin_licenses.png

***************************************
Konfiguration in den Settings
***************************************

.. code-block:: python
   :caption: Auszug aus den `settings.py <https://github.com/mrmap-community/xplanung_light/blob/master/komserv/settings.py>`_
   :linenos:

    XPLANUNG_LIGHT_CONFIG = {
        'metadata_contact': {
            'organization_name': 'Musterorganisation Metadaten / Dienste',
            'person_name': 'Max Mustermann',
            'email': 'maximilian.mustermann@example.com',
            'phone': '01111/11111',
            'facsimile': '01111/11111-0',
            'homepage': 'https://www.example.com',
            'address': 'Musterstraße 10',
            'city': 'Musterstadt',
            'postcode': '11111',
        },
        'version': '0.0.1',
        'metadata_keywords': ['bebauungsplan', 'kommunal', ],
        'mapfile_cache_duration_seconds': 20,
        "mapfile_force_online_resource_https": False,
        "further_base_layers": [
            #{"name": "dop20rp", "title": "DOP20 RP", "url": "https://geo4.service24.rlp.de/wms/rp_dop20.fcgi?", "attribution": "Lizenz ...", "layer_name": "rp_dop20"},
            {"name": "topplusfarbe", "title": "TopPlus Farbe", "url": "https://sgx.geodatenzentrum.de/wms_topplus_open?", "attribution": "Lizenz ...", "layer_name": "web"},
            {"name": "topplusfarbegrau", "title": "TopPlus Grau", "url": "https://sgx.geodatenzentrum.de/wms_topplus_open?", "attribution": "Lizenz ...", "layer_name": "web_grau"},   
        ],
        "overlay_layers": [
            {"name": "likarp", "title": "Liegenschaftskarte RP", "url": "https://geo5.service24.rlp.de/wms/liegenschaften_rp.fcgi?", "attribution": "Lizenz ...", "layer_name": "Flurstueck"},
            #{"name": "topplusfarbegrau", "title": "TopPlus Grau", "url": "https://sgx.geodatenzentrum.de/wms_topplus_open?", "attribution": "Lizenz ...", "layer_name": "web_grau"},   
        ],
    }
