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

**Bankzugang der Kartenebenen: der Dienst erscheint direkt im Mapfile**

Die Kartenebenen verbinden sich unabhängig von Django selbst zur Bank: MapServer öffnet
pro Anfrage (und danach prozessweit cached) eine eigene libpq-Verbindung. Steht der
Bankzugang allein in ``settings.DATABASES``, werden Rechner, Bank, Benutzer, Passwort und
Port in den Mapfile-Text geschrieben — und derselbe Text liegt
``XPLANUNG_LIGHT_CONFIG['mapfile_cache_duration_seconds']`` (Standard 20 Sekunden) lang im
Cache. Ist ein libpq-Dienst aus der obigen ``pg_service.conf`` benannt, lautet die
Verbindungsangabe der Ebene nur noch ``service=<name>``: Passwort und Benutzername kommen
dann im Mapfile nirgends vor.

Genügt eine der beiden Angaben:

.. code-block:: python

   # 1) Djangos eigene Angabe: die Anwendung ist selbst darüber verbunden, und die
   #    Kartenebenen bekommen dieselbe. NAME und OPTIONS['service'] schließen sich
   #    nicht aus, aber NAME darf leer bleiben — die Dienstdatei nennt die Bank.
   DATABASES = {
       'default': {
           'ENGINE': 'django.contrib.gis.db.backends.postgis',
           'NAME': '',
           'OPTIONS': {'service': 'xplanung-light'},
       }
   }

   # 2) Nur für die Kartenebenen, wenn die Anwendung die Bank selbst über Rechner
   #    und Passwort erreicht. Diese Angabe hat Vorrang vor 1) und gilt allein für
   #    die Mapfile-Ebenen:
   XPLANUNG_LIGHT_CONFIG['postgis_pg_service'] = 'karten-lesen'

   # dasselbe ohne Settings-Datei, in der Unit-Datei von Gunicorn:
   # Environment=XPLANUNG_LIGHT_PG_SERVICE=karten-lesen

So sieht ein Dienst in der Datei aus, die die Unit-Datei oben über ``PGSERVICEFILE``
anhilft:

.. code-block:: ini

   # /data/xplanung_light/config/pg_service.conf — Rechte 0644
   [xplanung-light]
   host=/var/run/postgresql
   port=5432
   dbname=xplanung_light
   user=xplanung_anwendung
   # bewusst kein password-Wert: das Geheimnis steht in .pgpass

.. code-block:: text

   # /data/xplanung_light/config/.pgpass — Rechte 0600, Eigentum xplanung_light
   /var/run/postgresql:5432:xplanung_light:xplanung_anwendung:GEHEIMNIS

Zwei Formen der Verbindungsangabe funktionieren dagegen nicht — gemessen mit MapServer 8.4
an PostgreSQL 17/PostGIS 3.5: Ein ``PG:``-Präfix, wie es der OGR-Treiber kennt, versteht
der Verbindungstyp ``POSTGIS`` nicht, und ein ausdrücklich leeres ``password=``-Feld gilt
libpq als Angabe mit leerem Wert und sperrt den Rückgriff auf die ``.pgpass`` aus. In beiden
Fällen erreicht die Ebene die Bank nicht mehr, während die Anwendung selbst weiter läuft —
die Karten bleiben dann leer, ohne dass ein Fehler fällt.

``manage.py check --deploy`` erinnert daran, solange eine Produktionsinstallation mit
Passwort in ``settings.DATABASES`` und ohne Dienst arbeitet
(``xplanung_light.W004``).

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


