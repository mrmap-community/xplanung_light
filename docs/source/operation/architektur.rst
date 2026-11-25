Architekturdiagramme
====================

Diese Seite zeigt den Produktivbetrieb, so wie er im :doc:`produktivbetrieb`
ausgeliefert wird: PostGIS und Gunicorn unter systemd hinter nginx mit bei Bedarf mit 
ModSecurity. Alle Diagramme sind aus dem Stand des Repos abgeleitet — die
Tafel unten nennt zu jedem Element die Stelle im Code. Die Diagramme selbst
liegen im Quellcode vor und werden von ``sphinxcontrib-mermaid`` gebaut (siehe
``docs/requirements.txt``), bleiben damit reviewbar und ändern sich mit dem
Code, den sie beschreiben.

.. contents:: Auf dieser Seite
   :local:
   :depth: 2

Was wo im Repo steht
--------------------

Wer ein Element der Diagramme nachschlagen oder ändern will:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Was im Diagramm zu sehen ist
     - Stelle im Repo
   * - Gunicorn am Unix-Socket, drei Worker, systemd
     - ``docs/source/operation/produktivbetrieb.rst`` (Unit-Datei mit
       ``PGSERVICEFILE``, ``PGPASSFILE``, ``MAPSERVER_CONFIG_FILE``)
   * - MapServer läuft **im** Django-Prozess, kein separates ``mapserv``-CGI
     - ``xplanung_light/views/views.py`` (``msLoadMapFromString``,
       ``OWSDispatch``), ``xplanung_light/apps.py`` (MapScript in ``ready()``)
   * - Mapfiles zur Laufzeit aus Vorlagen, je Worker X s gecacht
     - ``xplanung_light/helper/mapfile.py`` (mappyfile, Vorlagen in
       ``xplanung_light/mapserver/mapfile_templates/``),
       ``XPLANUNG_LIGHT_CONFIG['mapfile_cache_duration_seconds']`` in
       ``komserv/settings/base.py``
   * - MapServer verbindet sich selbst mit der DB - ohne Passwort im Mapfile
     - ``xplanung_light/helper/mapfile.py`` (libpq-Dienst über
       ``XPLANUNG_LIGHT_CONFIG['postgis_pg_service']``, PW aus
       ``PGPASSFILE``)
   * - Cache je Worker (LocMemCache), kein geteilten Cache eingerichtet
     - ``CACHES`` kommt in ``komserv/settings/`` nirgends vor
   * - Statische Dateien nur über nginx, ``/media/`` nie über die Platte
     - ``django.conf.urls.static.static()`` liefert bei ``DEBUG=False`` eine
       leere Liste; Anhänge werden immer über die Rights-Views in
       ``xplanung_light/views/views.py`` ausgeliefert
   * - Virenscan über clamd-Socket, ohne erreichbaren Daemon geht nichts
     - ``komserv/settings/base.py`` (``CLAMD_SOCKET``,
       ``CLAMD_FAIL_BY_DEFAULT``)
   * - Ausgänge: SMTP-Relay, BKG-Geokodierung, Import der Gebietskörperschaften
     - ``komserv/settings/base.py`` (``EMAIL_BACKEND``,
       ``BKG_GEOCODER_CONFIG``, ``REQUESTS_PROXIES``),
       ``xplanung_light/management/commands/importorganisations.py``
   * - Sicherung: DB und Mediendateien in einem Durchlauf, ein Zeitstempel
     - :doc:`sicherung`

Hauptarchitektur
----------------

Vom Frontend bis zur DB - und was auf dem Rechner dazugehört. Zwei Dinge sind es
wert, vor dem Diagramm genannt zu werden, weil sie in keinem generischen
Django-Bild stehen: MapServer läuft als Bibliothek **im** Django-Prozess (es
gibt keinen eigenen Kartendienst über CGI), und jeder Worker hat seinen eigenen Cache,
weil nirgends ein geteiltes ``CACHES`` genutzt wird.

.. mermaid::
  :config: {"layout": "elk", "theme": "redux-color"}

  flowchart TB
    subgraph CL["Wer ruft auf"]
      direction LR
      BU["Bürgerinnen und Bürger<br/>ohne Anmeldung"]
      FV["Fachverwaltung<br/>angemeldet"]
      TOEB["TÖB-Stellen<br/>Stellungnahmen"]
      GIS["Fachportal und GDI-Viewer<br/>WMS, WFS, CORS"]
    end
  
    FW["Firewall<br/>von aussen nur 443"]
  
    subgraph DMZ["Zugriffsschicht — nginx, Debian 13"]
      NGX["nginx<br/>TLS 1.3, HTTP/2, ACME<br/>HSTS, X-Forwarded-Proto"]
      MOD["ModSecurity 3 mit OWASP CRS 4<br/>Paranoia 1, erst DetectionOnly<br/>Audit-Log ohne Requestrumpf"]
      STA["statische Dateien<br/>alias /data/xplanung_light/static_collected"]
      BLK["/media/ bewusst 403<br/>Anhänge nur über die Rights-Views"]
    end
  
    subgraph AP["Anwendungsschicht — systemd, Benutzer xplanung_light"]
      Sock["gunicorn.socket<br/>/run/gunicorn.sock, 0660, Gruppe www-data"]
      MST["gunicorn.service<br/>Worker-Klasse sync, Timeout 60 s<br/>kein Thread-Betrieb, Begründung beim Kartenanfrage-Pfad"]
      subgraph WRK["Gunicorn-Worker, drei Stück, baugleich"]
        DJ["Django mit GeoDjango<br/>prod.py, ENV_NAME prod<br/>SECRET_KEY aus der Umgebung"]
        OGC["OGC-Proxy-Views<br/>ows, map, GetFeatureInfo"]
        GEN["MapfileGenerator<br/>mappyfile aus mapfile_templates"]
        MAP["libmapserver 8.4 im Prozess<br/>python3-mapscript"]
        CCH["LocMemCache, je Worker eigene<br/>Mapfilefassung 20 s"]
        CLA["Upload-Prüfung<br/>Inhalt und Virenscan"]
        EML["E-Mail-Versand<br/>Rollen, Beiträge, TÖB"]
      end
      CLAMD["clamd als Daemon<br/>/var/run/clamav/clamd.ctl"]
    end
  
    subgraph DBS["Datenschicht — nur lokal erreichbar"]
      PG["PostgreSQL mit PostGIS<br/>Socket und 127.0.0.1, scram-sha-256<br/>Raumindex GiST"]
      MED["MEDIA_ROOT, absolut, ausserhalb des Projektbaums<br/>0750, nur App-Benutzer"]
      CFG["Konfiguration ausserhalb des Git<br/>pg_service.conf, .pgpass, prod.py,<br/>.my_xplanung_light_env.json"]
    end
  
    subgraph OUT["Ausgänge"]
      SMTP["SMTP-Relay"]
      BKG["BKG-Geokodierung"]
      RLP["geoportal.rlp.de<br/>Import der Gebietskörperschaften"]
    end
  
    subgraph OPS["Sicherung und Beobachtung"]
      TIM["systemd-Timer<br/>pg_dump und Mediendateien, ein Zeitstempel"]
      OFF["Ausser-Haus-Ablage"]
      LOG["journalctl -u gunicorn, nginx-Fehlerprotokoll,<br/>modsec_audit.log"]
    end
  
    BU --> FW
    FV --> FW
    TOEB --> FW
    GIS --> FW
    FW --> NGX
    NGX --> MOD
    MOD -->|"Anwendung, OGC"| Sock
    MOD -->|"/static/"| STA
    MOD -.->|"/media/"| BLK
    Sock --> MST --> WRK
    DJ --- OGC
    OGC --> GEN --> MAP
    DJ --- CCH
    DJ --- CLA
    DJ --> EML
    MAP -->|"eigene libpq-Sitzung<br/>bleibt prozessweit offen"| PG
    DJ -->|"Django-Verbindung<br/>über PGSERVICEFILE und PGPASSFILE"| PG
    DJ -->|"Anhänge schreiben"| MED
    CLA -->|"Socket"| CLAMD
    EML --> SMTP
    DJ --> BKG
    DJ --> RLP
    CFG -.->|"beim Start eingelesen"| DJ
    PG --> TIM
    MED --> TIM
    TIM --> OFF
    MST --> LOG
    MOD --> LOG
  
    classDef kritisch stroke:#c0392b,stroke-width:2px;
    classDef daten stroke:#1f6f8b,stroke-width:2px;
    class MOD kritisch;
    class MAP kritisch;
    class PG daten;
    class MED daten;

Beispiel Request-Pfad einer Kartenanfrage (WMS ``GetMap``)
----------------------------------------------------------

Karten werden nicht durch separaten MapServer-Dienst erstellt: Der View baut das Mapfile aus
der Vorlage, gibt es dem in den Worker geladenen libmapserver, und libmapserver
öffnet eine **eigene** libpq-Sitzung zur DB — getrennt von der
Django-Verbindung. Der Bildpuffer, über den MapServer antwortet
(``msIO_installStdoutToBuffer``, ``views.py``), ist prozessweiter Zustand:
legten zwei Threads in einem Worker gleichzeitig eine Kartenanfrage ab, könnten
sie sich gegenseitig die Bildbytes aus dem Puffer lesen. Darum läuft Gunicorn mit
``sync``-Workern — nie ``--threads``, nie ``--preload`` (MapScript wird in
``AppConfig.ready()`` initialisiert, ein Preload zöge das vor den Fork). 
In einer Alternativarchitektur könnte man das so abändern, dass die Konfigurationsdateien
für den Mapserver bei gewissen Events oder zeitgesteuert geschrieben werden und der
Mapserver dann einfach eigenständige CGI Anwendung läuft. Da ist sehr viel skalierfähiger.

.. mermaid::

  sequenceDiagram
    autonumber
    participant V as GDI-Viewer
    participant N as nginx
    participant M as ModSecurity
    participant G as Gunicorn-Worker
    participant L as libmapserver im Worker
    participant D as PostGIS
    V->>N: GetMap mit BBOX, CRS 4326, Filter
    N->>M: Kopfzeilen und Argumentliste
    Note over M: OGC-Argumente sind ein klassisches Fehlalarmfeld<br/>BBOX, WKT, ogc-Filter — Ausschluss pro Pfad
    M->>G: proxy_pass an /run/gunicorn.sock
    G->>G: Mapfile-Fassung aus dem Worker-Cache, 20 s
    G->>L: msLoadMapFromString, dann OWSDispatch
    Note over L: stdout wird prozessweit umgebogen<br/>msIO_installStdoutToBuffer
    L->>D: eigene libpq-Sitzung, nicht die von Django
    D-->>L: Geometrien als EWKB
    L-->>G: PNG aus dem Puffer
    G-->>V: Bild, Access-Control-Allow-Origin wie eingestellt

Request-Pfad eines Plans-Imports
--------------------------------

Der vom Volumen größte Request-Body ist ein Planarchiv (XPlan-ZIP-Archiv). Es läuft erst über
nginx und ModSecurity bevor es an die Django-App weitergeleitet wird. Hier hakt es wahrscheinlich am
 häufigsten: ``client_max_body_size`` unter der Archivgröße bedeutet 413, ein ``SecRequestBodyLimit`` unter der Uploadgröße
bedeutet 403, beides **vor** jeder eigenen App-internen Validierung.

.. mermaid::

  sequenceDiagram
    autonumber
    participant F as Fachverwaltung
    participant N as nginx
    participant M as ModSecurity
    participant G as Gunicorn-Worker
    participant C as clamd
    participant D as PostGIS
    F->>N: POST bplan/import-archiv, ZIP mit GML
    Note over N: client_max_body_size muss die Archivgröße<br/>aushalten, sonst 413 vor jeder Anwendung
    N->>M: Request wird komplett zwischengespeichert
    Note over M: SecRequestBodyLimit unter der Uploadgröße<br/>bedeutet 403, SecTmpDir schreibt auf Platte
    M->>G: weitergereicht
    G->>G: Formular, Inhaltstest, Dateinamensvalidatoren
    G->>C: SCAN über /var/run/clamav/clamd.ctl
    C-->>G: sauber, infiziert oder nicht erreichbar
    Note over G: CLAMD_FAIL_BY_DEFAULT True<br/>ohne erreichbaren Daemon geht nichts hoch
    G->>D: Plan, Geometrien, Historie in einer Transaktion
    G->>G: Mapfile-Cache dieses Arbeiters fällt nach 20 s raus
    G-->>F: Ergebnisseite

Prozess-, Socket- und Dateisicht
--------------------------------

Für die Shell auf dem Zielrechner: Was über systemd läuft, was wo auf der Platte
liegen sollte und mit welchen Rechten. Die MapServer-Konfiguration unter ``/tmp``
ist orange markiert — die Env-Datei deklariert ``MAPSERVER_CONFIG_FILE`` auf
einen Pfad, den die Anwendung beim Start selbst schreibt; wer das
ändert, muss beide Stellen im Blick haben.

.. mermaid::
  :config: {"layout": "elk", "theme": "redux-color"}

  flowchart LR
    subgraph SYS["systemd"]
      U1["gunicorn.socket<br/>Accept=/run/gunicorn.sock"]
      U2["gunicorn.service<br/>Environment mit SECRET_KEY,<br/>PGSERVICEFILE, PGPASSFILE"]
      U3["xplanung-sicherung.timer<br/>xplanung-sicherung.service"]
      U4["clamd.service"]
    end
    subgraph FS["Dateisystem"]
      P1["/data/xplanung_light<br/>Projektbaum, Deployment"]
      P2["/data/xplanung_light/config<br/>0750: pg_service.conf, .pgpass, prod.py"]
      P3["MEDIA_ROOT absolut<br/>0750, ausserhalb von 1"]
      P4["/data/xplanung_light/static_collected<br/>von nginx gelesen"]
      P5["/tmp/mapserver-xxx.conf<br/>bei jedem Start neu, bleibt liegen"]
    end
    U2 -->|"bindet"| U1
    U2 -->|"liest beim Start"| P2
    U2 -->|"schreibt Anhänge"| P3
    U2 -->|"lieferte früher selbst"| P4
    U2 -->|"MAPSERVER_CONFIG_FILE"| P5
    U3 -->|"sichert"| P3
    U2 --- U4
    classDef wartung stroke:#b8860b,stroke-width:2px;
    class P5 wartung;
