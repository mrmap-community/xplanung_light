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

**Gunicorn (WSGI/ASGI)**

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

**DB-Zugang der Kartenebenen: der Dienst erscheint direkt im Mapfile**

Die Kartenebenen verbinden sich unabhängig von Django selbst zur Bank: MapServer öffnet
pro Anfrage (und danach prozessweit cached) eine eigene libpq-Verbindung. Steht der
Bankzugang allein in ``settings.DATABASES``, werden Rechner, DB, Benutzer, Passwort und
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

Konkrete Anleitung Debian 13 (netinstall)
-----------------------------------------

Wir gehen davon aus, dass wir auf der Maschine root-Rechte haben.

Verwendete Komponeten
+++++++++++++++++++++

* nginx
* postgresql
* gunicorn
* python-venv

Für den Betrieb nutzen wir verschiedene Komponeten aus den Standardpaketen von Debian. Die 
werden einfach über apt installiert.

.. code-block:: shell

   apt install nginx git rsync binutils libproj-dev gdal-bin spatialite-bin \ 
   libsqlite3-mod-spatialite python3-mapscript git \
   python3.13-venv python3-dev libpq-dev build-essential libmagic-dev gunicorn \
   postgresql-17 postgresql-17-postgis-3 postgresql-server-dev-17 python3-psycopg2

Nutzer
++++++

Für die Datenbank gibt es unter Debian schon den postgres als Zentraladmin. Hier benötigen wir nur eine Rolle.
Der App-Server gunicorn läuft unter dem neu anzulegenden Nutzer **xplanung_light** und nginx standardmäßig unter 
**www-data**.

.. code-block:: shell

   udo useradd -M -s /bin/bash xplanung_light

Verzeichnisse
+++++++++++++

.. code-block:: shell

   mkdir -p /data/xplanung_light_db
   mkdir /data/xplanung_light_log

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
   # ... eingeben
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
   chown -R xplanung_light xplanung_light
   su xplanung_light
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

Konfigurationsdateteien erstellen / anpassen

/data/xplanung_light/komserv/.my_xplanung_light_env.json

.. code-block:: json

   {
      "ENV_NAME": "prod"
   }

/data/xplanung_light/komserv/settings/prod.py

.. code-block:: python

   #

Umgebungsvariablen / Konfigurationen 

.. code-block:: shell
  
  #

Systemd script als Wrapper für manage.py - /usr/local/bin/xplanung-light-manage

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



Verzeichnisstruktur
+++++++++++++++++++
Wir teilen das Projekt in verschiedenen Verzeichnisse mit speziellen Berechtigungen auf.



**Weitere Infos**

* https://www.howtoforge.de/anleitung/so-installierst-du-das-django-framework-unter-debian-11/
* https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu#step-6-testing-gunicorn-s-ability-to-serve-the-project
* https://serverfault.com/questions/1166209/apache2-forward-gunicorn-socket-error
* https://medium.com/building-the-system/gunicorn-3-means-of-concurrency-efbb547674b7
* https://serverfault.com/questions/517596/static-file-permissions-with-nginx-gunicorn-and-django
* https://codingnomads.com/django-debug-gunicorn-service


