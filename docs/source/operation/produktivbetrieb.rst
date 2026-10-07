Produktivbetrieb
================

**Empfohlene Betriebssysteme**

* `Debian`_ 11:

* `Debian`_ 12:

* `Debian`_ 13:

.. _Debian: https://www.debian.org/index.de.html

**Datenbank**

`PostGIS`_ - Installation als deb-Paket - siehe github README.

.. _PostGIS: https://postgis.net/

**clamav**

`ClamAV`_ - der Virenscanner wird als deb-Paket installiert und läuft als daemon im Hintergrund.

.. _ClamAV: https://www.clamav.net/

**Gunicorn (WSGI/ASGI)**

`Gunicorn`_ wird so konfiguriert, dass es einen Unix-Domain-Socket verwendet. Es wird über pip in der venv-Umgebung installiert und über systemd gesteuert.

.. _Gunicorn: https://gunicorn.org/

.. note::

   Restart erfordert **zwei** Befehle:

   .. code-block:: shell
      :linenos:

      sudo systemctl daemon-reload
      sudo systemctl restart gunicorn

.. note::

   Ausgabe der Fehlermeldungen:

   .. code-block:: shell
      :linenos:

      sudo journalctl -u gunicorn

**nginx (Reverse Proxy)**

`Nginx`_ läuft als Reverse Proxy und verteilt die Anfragen für die statischen Inhalte und das aktive Framework. Installation als deb-Paket.

.. _Nginx: https://nginx.org/

**PostgreSQL**

Die Datenbankverbindungsparameter sollten aus Sicherheitsgründen nicht direkt in der settings.py abgelegt werden.
Da sich unter Linux gunicorn anbietet, sollte man die notwendigen Umgebungsvariablen in der **/etc/systemd/system/gunicorn.service** setzen.

.. code-block:: ini 

   [Unit]
   Description=gunicorn daemon
   Requires=gunicorn.socket
   After=network.target
   [Service]
   User=xplanung_light
   Group=www-data
   WorkingDirectory=/data/xplanung_light/

   # Hier werden die Umgebungsvariablen optimalerweise gesetzt:
   Environment=PGSERVICEFILE=/data/xplanung_light/config/pg_service.conf
   Environment=PGPASSFILE=/data/xplanung_light/config/.pgpass
   Environment=MAPSERVER_CONFIG_FILE=/data/xplanung_light/config/mapserver.conf

   ExecStart=/data/xplanung_light/.venv/bin/gunicorn \
            --log-file /tmp/gunicorn.log \
            --workers 3 \
            --bind unix:/run/gunicorn.sock \
            komserv.wsgi:application

   [Install]
   WantedBy=multi-user.target

https://docs.djangoproject.com/en/6.1/ref/databases/#postgresql-connection-settings

**Sicherheitsvergleich: Django Settings vs. Externe Konfigurationsdateien**
(Gemini - 2026-10-07)

.. list-table:: Direkter Sicherheitsvergleich
   :widths: 30 35 35
   :header-rows: 1

   * - Sicherheitsaspekt
     - Passwort in Django ``settings.py``
     - Externe ``pg_service.conf`` + ``.pgpass``
   * - **Sichtbarkeit bei App-Crashes**
     - **Hoch** (wird oft im Stacktrace/Log im Klartext ausgegeben)
     - **Keine** (wird isoliert von ``libpq`` auf C-Ebene verarbeitet)
   * - **Auslesbar bei Django-RCE-Lücke**
     - **Ja** (einfach über ``settings.DATABASES`` abfragbar)
     - **Nein** (Python-Prozess liest die Datei nicht direkt ein)
   * - **Gefahr von Git-Leaks**
     - **Medium** (Trotz ``.env`` hohes Risiko durch Fehlkonfiguration)
     - **Sehr gering** (Liegt in Systempfaden weit ab vom Quellcode)
   * - **Erzwungene Dateirechte**
     - **Nein** (Django startet auch mit unsicheren Dateirechten wie ``0644``)
     - **Ja** (Datenbankverbindung schlägt bei falscher Permission sofort fehl)

**Weitere Infos**

* https://www.howtoforge.de/anleitung/so-installierst-du-das-django-framework-unter-debian-11/
* https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu#step-6-testing-gunicorn-s-ability-to-serve-the-project
* https://serverfault.com/questions/1166209/apache2-forward-gunicorn-socket-error
* https://medium.com/building-the-system/gunicorn-3-means-of-concurrency-efbb547674b7
* https://serverfault.com/questions/517596/static-file-permissions-with-nginx-gunicorn-and-django
* https://codingnomads.com/django-debug-gunicorn-service


