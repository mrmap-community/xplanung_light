Produktivbetrieb
================

**Empfohlene Betriebssysteme**

* `Debian`_ 13:

.. _Debian: https://www.debian.org/index.de.html

**Datenbank**

`PostGIS`_ - Installation als deb-Paket - siehe github README.

.. _PostGIS: https://postgis.net/

**clamav**

`ClamAV`_ - der Virenscanner wird als deb-Paket installiert und läuft als daemon im Hintergrund.

.. _ClamAV: https://www.clamav.net/

**Gunicorn (WSGI)**

`Gunicorn`_ wird so konfiguriert, dass es einen Unix-Domain-Socket verwendet. Es wird über pip in der venv-Umgebung installiert und über systemd gesteuert.

.. _Gunicorn: https://gunicorn.org/

.. note::

   Restart erfordert **zwei** Befehle:

   .. code-block:: shell

      sudo systemctl daemon-reload
      sudo systemctl restart gunicorn

.. note::

   Ausgabe der Fehlermeldungen:

   .. code-block:: shell

      sudo journalctl -u gunicorn

**nginx (Reverse Proxy)**

`Nginx`_ läuft als Reverse Proxy und verteilt die Anfragen für die statischen Inhalte und das aktive Framework. Installation als deb-Paket.

.. _Nginx: https://nginx.org/

**PostgreSQL**

Die Datenbankverbindungsparameter sollten aus Sicherheitsgründen nicht direkt in der settings.py abgelegt werden.
Da sich unter Linux gunicorn anbietet, sollte man die notwendigen Umgebungsvariablen in der **/etc/systemd/system/gunicorn.service** setzen.
Das Beispiel findet sich in der konkreten Anleitung weiter unten.

https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-connection-settings

**Sicherheitsvergleich: Django Settings vs. Externe Konfigurationsdateien**

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
     - **Ja** Die Datei muss für den Dienstnutzer lesbar sein; das Passwort steht aber nicht im Quelltext und läuft daher nicht über die logs.
   * - **Gefahr von Git-Leaks**
     - **Medium** (Trotz ``.env`` hohes Risiko durch Fehlkonfiguration)
     - **Sehr gering** (Liegt in Systempfaden weit ab vom Quellcode)
   * - **Erzwungene Dateirechte**
     - **Nein** (Django startet auch mit unsicheren Dateirechten wie ``0644``)
     - **Ja** (Datenbankverbindung schlägt bei falscher Permission sofort fehl)

**DB-Zugang für Mapserver**

Die Kartenebenen verbinden sich unabhängig von Django selbst mit der DB: MapServer öffnet
pro Anfrage (und danach prozessweit cached) eine eigene libpq-Verbindung. Steht der
Bankzugang allein in ``settings.DATABASES``, werden Rechner, DB, Benutzer, Passwort und
Port in den Mapfile-Text geschrieben — und derselbe Text liegt
``XPLANUNG_LIGHT_CONFIG['mapfile_cache_duration_seconds']`` (Standard 20 Sekunden) lang im
Cache. 

Das kann zu einem Sicherheitsrisiko führen. Produktiv stehen sowohl die DB Verbindung für den Mapserver, als auch die
für Django in eigenen Konfigurationsfiles. 

``manage.py check --deploy`` erinnert daran, solange eine Produktionsinstallation mit
Passwort in ``settings.DATABASES`` und ohne Dienst arbeitet
(``xplanung_light.W004``).

**Wichtig zu beachten**: Beim Bau der Mapserver-Mapfiles ist zu beachten, dass ein ``PG:``-Präfix und ein leeres ``password=`` nicht funktionieren: 
Der Layer kann sich so nicht mit der DB verbinden. Die Anwendung läuft zwar, die Kartenbilder bleiben aber leer und das ohne Fehlermeldung. 
Richtig ist nur ``CONNECTION "service=<name>"``.

Konkrete Anleitung Debian 13 (netinstall)
-----------------------------------------

Wir gehen davon aus, dass wir auf der Maschine root-Rechte haben.

Verwendete Komponenten
++++++++++++++++++++++

* nginx
* postgresql
* gunicorn
* python-venv

Für den Betrieb nutzen wir verschiedene Komponenten aus den Standardpaketen von Debian. Die 
werden einfach über apt installiert.

.. code-block:: shell

   apt install nginx git rsync binutils libproj-dev gdal-bin spatialite-bin \
   libsqlite3-mod-spatialite python3-mapscript git clamav-daemon clamav-freshclam \
   python3.13-venv python3-dev libpq-dev build-essential libmagic-dev \
   postgresql-17 postgresql-17-postgis-3 postgresql-server-dev-17 python3-psycopg2

Nutzer
++++++

Für die Datenbank gibt es unter Debian schon den postgres als Zentraladmin. Hier benötigen wir nur eine Rolle.
Der App-Server gunicorn läuft unter dem neu anzulegenden Nutzer **xplanung_light** und nginx standardmäßig unter 
**www-data**.

.. code-block:: shell

   sudo useradd -M -s /bin/bash xplanung_light

Verzeichnisse
+++++++++++++

.. code-block:: shell

   # Verzeichnis für Datenbank
   mkdir -p /data/xplanung_light_db
   # Verzeichnis für log-files
   mkdir /data/xplanung_light_log
   chown -R xplanung_light /data/xplanung_light_log
   sudo chgrp -R www-data /data/xplanung_light_log
   # Verzeichnis für uploads
   mkdir /data/xplanung_light_upload
   chown -R xplanung_light /data/xplanung_light_upload
   # Verzeichnis für Ablage der statischen files
   mkdir /data/xplanung_light_static
   chown -R xplanung_light /data/xplanung_light_static
   # Leseberechtigung für nginx
   sudo chgrp -R www-data /data/xplanung_light_static
   sudo find /data/xplanung_light_static -type d -exec chmod g+rx {} +
   sudo find /data/xplanung_light_static -type f -exec chmod g+r {} +

Datenbank
+++++++++

Das Anlegen der Datenbank erfolgt mit **postgres**. Es macht Sinn den Eigentümer der DB vorher anzulegen.

root-Shell:

.. code-block:: shell

   sudo -u postgres psql -p 5432 -c "CREATE USER geodjango;"

Damit das Passwort nicht irgendwo in der history auftaucht öffnet man eine SQL-Shell und setzt es dort interaktiv.

Shell öffnen

.. code-block:: shell

   sudo -u postgres psql -p 5432

Passwort setzen und shell verlassen

.. code-block:: shell

   \password geodjango
   # ... eingeben - und notieren ;-)
   exit

Erstellen der der DB und Einrichten der GIS-Erweiterung

.. code-block:: shell

   su - postgres -c "createdb -p 5432 -E UTF8 xplanung_light -T template0"
   sudo -u postgres psql -p 5432 -d xplanung_light -c "CREATE EXTENSION postgis;"
   sudo -u postgres psql -p 5432 -c "ALTER DATABASE xplanung_light OWNER TO geodjango;"

Anpassen der Zugangsberechtigungen in der /etc/postgresql/17/main/pg_hba.conf

.. code-block:: ini

   # ...
   # TYPE  DATABASE        USER            ADDRESS                 METHOD

   # "local" is for Unix domain socket connections only
   # ...
   # IPv4 local connections:
   # ...
   host    xplanung_light  geodjango       127.0.0.1/32            scram-sha-256 
   # IPv6 local connections:
   # ...
   host    xplanung_light  geodjango       ::1/128                 scram-sha-256 
   # ...

Datenbank neustarten

.. code-block:: shell

   /etc/init.d/postgresql restart

Umzug der DB und logs in eigene Verzeichnisse

.. code-block:: shell

   # Stop der DB
   sudo systemctl stop postgresql
   # Anzeige des Clusters
   pg_lsclusters
   # Anlegen der Datenbank-/Logverzeichnisse und setzen der Berechtigungen
   sudo mkdir -p /data/xplanung_light_db/postgresql/17/main
   sudo mkdir -p /data/xplanung_light_log/postgresql

   sudo chown -R postgres:postgres /data/xplanung_light_db/postgresql
   sudo chown -R postgres:postgres /data/xplanung_light_log/postgresql

   sudo chmod 700 /data/xplanung_light_db/postgresql/17/main
   sudo chmod 700 /data/xplanung_light_log/postgresql
   # Übetragung der DB ins neue Verzeichnis
   sudo rsync -av /var/lib/postgresql/17/main/ /data/xplanung_light_db/postgresql/17/main/
   # Sicherheitskopie für DB-Verzeichnis
   sudo mv /var/lib/postgresql/17/main /var/lib/postgresql/17/main.bak

Umstellung des Datenbank- und Logverzeicnisses in der Konfigurationsdatei

.. code-block:: shell

   sudo nano /etc/postgresql/17/main/postgresql.conf
   # Folgendes eintragen bzw. anpassen
   #data_directory = '/data/xplanung_light_db/postgresql/17/main'
   #log_directory = '/data/xplanung_light_log/postgresql/'

Datenbank neustarten und Prüfausgaben

.. code-block:: shell

   sudo systemctl start postgresql
   sudo systemctl status postgresql
   sudo -u postgres psql -c "SHOW data_directory;"

Django App
++++++++++

Basisinstallation

.. code-block:: shell

   mkdir /data/xplanung_light/
   chown -R xplanung_light /data/xplanung_light
   su xplanung_light
   cd /data/
   git clone https://github.com/mrmap-community/xplanung_light.git
   cd xplanung_light
   python3 -m venv .venv
   source .venv/bin/activate
   python3 -m pip install --upgrade pip
   python3 -m pip install -r requirements.txt
   python3 -m pip install gunicorn
   cd /data/xplanung_light/.venv/lib64/python3.13/site-packages/mapscript
   cp /usr/lib/python3/dist-packages/mapscript/_mapscript.cpython-313-x86_64-linux-gnu.so _mapscript.so
   exit

Konfigurationsdateien erstellen / anpassen

Einstellung für das zu nutzende Profil der Anwendnung - im Fall des Produktionssystems **prod**.

/data/xplanung_light/komserv/.my_xplanung_light_env.json

.. code-block:: json

   {
      "ENV_NAME": "prod"
   }

/data/xplanung_light/komserv/settings/prod.py

Die initiale Datei wird aus dem Template erstellt

   .. code-block:: bash

      cp /data/xplanung_light/komserv/settings/prod.example.py /data/xplanung_light/komserv/settings/prod.py

Danach sind die Defaultwerte in der Datei anzupassen.

Wichtig:

   * Verzeichnis für die statischen Dateien

      .. code-block:: python

         STATIC_ROOT = '/data/xplanung_light_static'

   * Zugriffsberechtigungen

      .. code-block:: Python

         # Adressen unter denen die Anwendnung erreichbar sein darf
         ALLOWED_HOSTS = ['{server}',]
         # Adressen, von denen Formulare stammen dürfen
         CSRF_TRUSTED_ORIGINS = ['http://{server}',]

   * Upload Verzeichnis

      .. code-block:: Python

         MEDIA_ROOT = '/data/xplanung_light_upload'

   * Datenbankverbindung

      .. code-block:: python

         DATABASES = {
            'default': {
               'ENGINE': 'django.contrib.gis.db.backends.postgis',
               'NAME': 'xplanung_light',
               'OPTIONS': {'service': 'xplanung_light_db'},
            }
         }

   * Virenscanner aktivieren

      .. code-block:: python

         CLAMD_ENABLED = True
         CLAMD_SOCKET = '/var/run/clamav/clamd.ctl'

   * Logging einschalten

      .. code-block:: python

         LOGGING = {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
               'datei': {
                     'level': 'ERROR',
                     'class': 'logging.handlers.WatchedFileHandler',
                     'filename': '/data/xplanung_light_log/error.log',
               },
            },
            'loggers': {
               'django': {'handlers': ['datei'], 'level': 'ERROR', 'propagate': True},
            },
         }

   * TODO: Weitere Einstellungen

Umgebungsvariablen / Konfigurationen 

Die Umgebungsvariablen werden zur Sicherheit in einem speziellen Verzeichnis abgelegt. Dieses muss zunächst erstellt werden.

.. code-block:: shell

   mkdir /data/xplanung_light_config

Datei mit den Umgebungsvariablen: /data/xplanung_light_config/env

.. code-block:: ini

   XPLANUNG_LIGHT_SECRET_KEY={django_security_key}
   PGSERVICEFILE=/data/xplanung_light_config/pg_service.conf
   PGPASSFILE=/data/xplanung_light_config/.pgpass
   MAPSERVER_CONFIG_FILE=/data/xplanung_light_config/mapserver.conf

Berechtigungen setzen (root Leserecht reicht aus, da systemd sie als root liest)

.. code-block:: shell

   chmod 0600 /data/xplanung_light_config/env

**Der security_key wird später über den manage.py Wrapper erzeugt und in diese Datei eingetragen!**

Datei mit den Verbindungsinformationen zur Postgres-DB: /data/xplanung_light_config/pg_service.conf

.. code-block:: ini

   [xplanung_light_db]
   host=127.0.0.1
   port=5432
   dbname=xplanung_light
   user=geodjango
   passfile=/data/xplanung_light_config/.pgpass

Berechtigungen setzen

.. code-block:: shell

   chown xplanung_light /data/xplanung_light_config/pg_service.conf
   chmod 0640 /data/xplanung_light_config/pg_service.conf

Datei mit dem Passwortinformationen für die Postgres-DB: /data/xplanung_light_config/.pgpass

.. code-block:: ini

   127.0.0.1:5432:xplanung_light:geodjango:{db-passwort}

.. code-block:: shell

   chown xplanung_light:xplanung_light /data/xplanung_light_config/.pgpass
   chmod 0600 /data/xplanung_light_config/.pgpass

Datei für die Mapserver Konfiguration: /data/xplanung_light_config/mapserver.conf

.. code-block:: ini

   CONFIG
      ENV
         PGSERVICEFILE "/data/xplanung_light_config/pg_service.conf"
      END
   END

Systemd script als Wrapper für manage.py - /usr/local/bin/xplanung-light-manage

Das Script läuft unter dem Nutzer **xplanung_light** und wrapped das normale manage.py Kommando.


.. code-block:: bash

   #!/usr/bin/env bash
   # /usr/local/bin/xplanung-light-manage  (chmod 755)
   set -euo pipefail
   mode=--pipe; [ -t 0 ] && mode=--pty
   exec systemd-run "$mode" --quiet --wait --collect \
   -p User=xplanung_light -p Group=www-data \
   -p UMask=0027 \
   -p EnvironmentFile=/data/xplanung_light_config/env \
   -p WorkingDirectory=/data/xplanung_light \
   /data/xplanung_light/.venv/bin/python manage.py "$@"

Berechtigung für script setzen

.. code-block:: bash

   chmod 755 /usr/local/bin/xplanung-light-manage

nginx
+++++

Bei nginx liegen die Konfigurationsdateien unter /etc/nginx/sites-available/ und werden durch symbolische Links aktiviert.
Wir brauchen eine neue Konfiguration: /etc/nginx/sites-available/django

   .. code-block:: ini

      server {
         listen 80;
         location = /favicon.ico { access_log off; log_not_found off; }
         server_name {servername/-ip};
         location = /favicon.ico { access_log off; log_not_found off; }
         client_max_body_size 250M; #
         proxy_read_timeout 90s; # länger als gunicorn timeout!
         proxy_set_header X-Forwarded-Proto $scheme;
         location /static/ {
               alias /data/xplanung_light_static/;
               access_log off;
         expires 30d;
         }
         location /media/ { return 403; }
         location /admin { allow 10.0.0.0/8; deny all; proxy_pass http://gunicorn; }
         location / {
               include proxy_params;
               proxy_pass http://unix:/run/gunicorn.sock;
         }
      }

Dann deaktivieren wir die default Seite, aktivieren unsere Konfiguration und starten den Service neu (als root):

   .. code-block:: bash

      rm /etc/nginx/sites-enabled/default
      ln -s /etc/nginx/sites-available/django /etc/nginx/sites-enabled/django
      systemctl restart nginx

gunicorn
++++++++

Der Prozess wird über systemd gesteuert - wir legen also eine Konfigurationsdatei **/etc/systemd/system/gunicorn.service** mit folgendem Inhalt an:

   .. code-block:: ini

      [Unit]
      Description=gunicorn daemon
      Requires=gunicorn.socket
      After=network.target
      [Service]
      User=xplanung_light
      Group=www-data
      # Hier werden die Umgebungsvariablen gelesen - gleiche Stelle wir auch im manage.py Wrapper:
      EnvironmentFile=/data/xplanung_light_config/env
      WorkingDirectory=/data/xplanung_light/
      ExecStart=/data/xplanung_light/.venv/bin/gunicorn \
               --worker-class sync \
               --timeout 60 \
               --workers 3 \
               --bind unix:/run/gunicorn.sock \
               komserv.wsgi:application

      [Install]
      WantedBy=multi-user.target

Ausserdem brauchen wir eine Socket-Datei **/etc/systemd/system/gunicorn.socket** mit folgendem Inhalt:

   .. code-block:: ini

      [Unit]
      Description=gunicorn socket

      [Socket]
      ListenStream=/run/gunicorn.sock

      [Install]
      WantedBy=sockets.target

Danach müssen wir den Daemon installieren, starten und den socket aktivieren, damit er einen reboot übersteht.

   .. code-block:: shell

      systemctl daemon-reload
      sudo systemctl status gunicorn
      sudo systemctl start gunicorn
      sudo systemctl status gunicorn
      sudo systemctl enable gunicorn.socket gunicorn

Initialisierung der Anwendung
+++++++++++++++++++++++++++++

Security Key erzeugen:

   .. code-block:: shell

      xplanung-light-manage shell -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

**Der Key muss in /data/xplanung_light_config/env eingefügt werden (da steht momentan noch ein Platzhalter).**

Nach Ablage des Schlüssels muss der gunicorn neu gestartet werden (als root), sonst läuft der Dienst mit dem o.g. default-Wert weiter.

   .. code-block:: shell

      systemctl restart gunicorn

Die Anwendung kann jetzt über den Wrapper gesteuert werden. Zunächst testet man, ob alles für den Produktivbetrieb fertig ist:

   .. code-block:: shell

      xplanung-light-manage check --deploy

Danach kopiert man die statics in den dafür vorgesehenen Folder:

   .. code-block:: shell

      xplanung-light-manage collectstatic --noinput

Initialisierung der Datenbank:

   .. code-block:: shell

      xplanung-light-manage migrate

Anlegen des superuser-Accounts:

   .. code-block:: shell

      xplanung-light-manage createsuperuser

Virenscanner prüfen
+++++++++++++++++++

   .. code-block:: shell

      systemctl status clamav-daemon

**Per Hand einen Upload starten, um zu sehen ob der Virenscanner tatsächlich läuft.**

Verzeichnisstruktur
+++++++++++++++++++
Das Projekt ist jetzt in verschiedene Verzeichnisse aufgeteilt und die Zugangsdaten sind sicher über Umgebungsvariablen eingebunden.

Updates
+++++++

Das Einspielen von Updates lässt sich sehr einfach über git pull realisieren. Das muss aber mit dem user **xplanung_light**
gemacht werden.

   .. code-block:: shell

      su xplanung_light
      cd /data/xplanung_light/
      git pull

Im Anschluss müssen ausstehende Migrationen gemacht, die static-Files generiert und der gunicorn neu
gestartet werden (als **root**).

   .. code-block:: shell

      xplanung-light-manage migrate
      xplanung-light-manage collectstatic
      sudo systemctl restart gunicorn

**Weitere Infos**

* https://www.howtoforge.de/anleitung/so-installierst-du-das-django-framework-unter-debian-11/
* https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu#step-6-testing-gunicorn-s-ability-to-serve-the-project
* https://serverfault.com/questions/1166209/apache2-forward-gunicorn-socket-error
* https://medium.com/building-the-system/gunicorn-3-means-of-concurrency-efbb547674b7
* https://serverfault.com/questions/517596/static-file-permissions-with-nginx-gunicorn-and-django
* https://codingnomads.com/django-debug-gunicorn-service


