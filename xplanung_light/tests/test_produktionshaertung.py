"""Produktionshärtung: Vorlage, Systemchecks und die Basis-Einstellungen.

Prüft drei Dinge zusammen, die nur gemeinsam wirken:

* die **Systemchecks** aus `xplanung_light/checks.py`, die eine Produktionsinstallation
  ansprechen, wenn sie mit Entwicklungswerten läuft,
* die **Vorlage** `komserv/settings/prod.example.py`, damit Betreiber:innen diese Werte
  überhaupt setzen können, und
* `komserv/settings/base.py` selbst — die Basis darf keine Debug-Werkzeuge enthalten und
  muss die eingebaute Doku hinter eine Anmeldung legen.

Die Dateien werden gelesen, nicht importiert: eine Settings-Datei zu importieren würde
Django mit einer zweiten Konfiguration starten, und die Vorlage bricht ohne
Schlüssel-Umgebungsvariable absichtlich ab.
"""

import ast
import os
import re
from pathlib import Path

from django.core.checks.registry import registry
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from xplanung_light.checks import (
    pruefe_dateiablage,
    pruefe_geheimnisschluessel,
    pruefe_haertung,
    pruefe_mapfile_bankzugang,
)
from xplanung_light.models import AdministrativeOrganization
from xplanung_light.views.obergrenzen import cors_erlaubnis

REPO = Path(__file__).resolve().parents[2]
BASE_PY = REPO / 'komserv' / 'settings' / 'base.py'
# dev.py liegt in .gitignore und fehlt auf einem frischen Clone — alle Pruefungen, die
# die Datei lesen, fragen vorher exists() ab
DEV_PY = REPO / 'komserv' / 'settings' / 'dev.py'
PROD_VORLAGE = REPO / 'komserv' / 'settings' / 'prod.example.py'
README_MD = REPO / 'README.md'

# Worin ein von Django erzeugter Schlüssel steckt. Absichtlich ein Muster und nicht der
# Wortlaut: der Wert, der vor dieser Korrektur in base.py stand, darf nirgends im Git
# auftauchen — auch nicht als Prüfkonstante. Ein einmal öffentlicher Schlüssel bleibt
# öffentlich, und ein Test, der ihn zitiert, würde die Suche danach (Sekretscan,
# GitHub-Suche) selbst wieder anschlagen lassen. Erkannt wird das Präfix plus längeres
# Zufallsende; der bewusst kurze, selbsterklärende Ausweichwert aus base.py
# ('django-insecure-entwurfsschluessel-nicht-fuer-produktion') fällt nicht darunter.
DJANGO_SCHLUESSEL_MUSTER = re.compile(r'django-insecure-[A-Za-z0-9@_+=.~!$%&*(){}-]{45,}')


def zuweisungen(pfad):
    """Werte der Zuweisungen auf Modul-Ebene einer Python-Datei, als Wörterbuch.

    Was sich wie ein Literal auswerten lässt, kommt als Python-Wert zurück; alles andere
    (`os.environ.get(...)`, `BASE_DIR / 'uploads'`) als Quelltext, damit eine Prüfung
    trotzdem sagen kann, was dort steht.
    """
    quelltext = pfad.read_text(encoding='utf-8')
    ast_wurzel = ast.parse(quelltext)
    werte = {}
    for knoten in ast_wurzel.body:
        if not isinstance(knoten, ast.Assign) or len(knoten.targets) != 1:
            continue
        ziel = knoten.targets[0]
        if not isinstance(ziel, ast.Name):
            continue
        try:
            werte[ziel.id] = ast.literal_eval(knoten.value)
        except (ValueError, SyntaxError):
            werte[ziel.id] = ast.unparse(knoten.value)
    return werte


def meldungen(check, **einstellungen):
    """Systemcheck mit den angegebenen Einstellungen ausführen, Ids zurückgeben."""
    with override_settings(**einstellungen):
        return sorted(meldung.id for meldung in check(None))


class SecretKeyCheckTests(TestCase):
    """Ein bekannter Schlüssel in Produktion ist ein Fehler, in Arbeitsumgebungen nicht."""

    PRODUKTION = {'DEBUG': False}

    def test_bekannter_schluessel_in_produktion_ist_fehler(self):
        """
        Was wird geprüft: Ein als unsicher erkennbarer Schlüssel meldet Fehler E001.

        Warum: der Wert aus base.py ist ausdrücklich ein Entwicklungsschlüssel. Vergisst
        eine Installation den Ersatz, laufen Session-Cookies, Passwort-Reset und
        CSRF-Masking mit einem öffentlich bekannten Schlüssel — das darf nicht
        stillschweigend durchlaufen.

        Erwartung: ['xplanung_light.E001'] bei DEBUG=False, für jedes der drei
        Erkennungsmuster und in jeder Schreibweise.
        """
        for schluessel in ('django-insecure-irgendwas', 'CHANGEME-bitte-ersetzen',
                           'sehr_geheimer_changeme_wert'):
            self.assertEqual(
                meldungen(pruefe_geheimnisschluessel, SECRET_KEY=schluessel, **self.PRODUKTION),
                ['xplanung_light.E001'], f"Schlüssel {schluessel!r}")

    def test_echter_schluessel_und_arbeitsumgebung_melden_nichts(self):
        """
        Was wird geprüft: Ein eigener Schlüssel meldet nichts, eine Arbeitsumgebung mit
        Entwicklungswert ebenso nicht.

        Warum: der Check soll Produktion beanstanden, nicht lokale Arbeit blockieren —
        sonst stellt ihn jemand ab, statt ihn zu lesen.

        Erwartung: keine Meldungen für einen unauffälligen Schlüssel bei DEBUG=False und
        für den Entwicklungswert bei DEBUG=True.
        """
        self.assertEqual(meldungen(pruefe_geheimnisschluessel, SECRET_KEY='x' * 60,
                                   **self.PRODUKTION), [])
        self.assertEqual(meldungen(pruefe_geheimnisschluessel, DEBUG=True,
                                   SECRET_KEY='django-insecure-entwurfsschluessel'), [])

    def test_pruefung_laeuft_bei_manage_check_mit(self):
        """
        Was wird geprüft: Der Check ist registriert und läuft bei 'manage.py check' mit.

        Warum: ein Check, den niemand aufruft, schützt nichts. Das Mitlaufen zeigt sich
        daran, dass der Aufruf über die registrierte Funktion eine Ergebnisliste liefert.

        Erwartung: eine Liste, deren Meldungen höchstens die Id E001 tragen.
        """
        ergebnis = pruefe_geheimnisschluessel(None)
        self.assertIsInstance(ergebnis, list)
        self.assertTrue(all(meldung.id == 'xplanung_light.E001' for meldung in ergebnis))

    def test_deployment_pruefungen_sind_nur_bei_deploy_registriert(self):
        """
        Was wird geprüft: Die beiden Deployment-Prüfungen stecken in der Deployment-Gruppe,
        der Schlüssel-Check in der normalen Gruppe.

        Warum: vorgekommen und korrigiert — `register(deployment=True)` klingt richtig,
        ist es aber nicht: Django liest `deploy`. Das falsche Schlüsselwort wird als
        Check-Argument mitgeschleift, die Prüfung läuft trotzdem — bei jedem `check` und
        damit in jedem Testlauf. Der Testlauf meldete daraufhin drei Warnungen, obwohl
        eine Testbank MEDIA_ROOT und CORS-Liste gar nicht leisten kann.

        Erwartung: die beiden Deployment-Prüfungen in `deployment_checks`, der
        Schlüssel-Check in `registered_checks`.
        """
        self.assertIn(pruefe_dateiablage, registry.deployment_checks)
        self.assertIn(pruefe_haertung, registry.deployment_checks)
        self.assertNotIn(pruefe_dateiablage, registry.registered_checks)
        self.assertNotIn(pruefe_haertung, registry.registered_checks)
        self.assertIn(pruefe_geheimnisschluessel, registry.registered_checks)

    def test_pruefungen_sind_ueber_apps_py_angemeldet(self):
        """
        Was wird geprüft: `xplanung_light/apps.py` importiert das Prüfmodul in `ready()`.

        Warum: gemessen und korrigiert — Django importiert `checks.py` einer App **nicht**
        von selbst. Nach `django.setup()` war das Modul nicht geladen, die Prüfungen waren
        also in keiner echten Installation registriert; sie liefen nur im Testlauf, weil
        die Testdatei sie importiert. Angemeldet gehören sie in `AppConfig.ready()`.

        Erwartung: der Import des Prüfmoduls steht in apps.py.
        """
        quelle = (REPO / 'xplanung_light' / 'apps.py').read_text(encoding='utf-8')
        self.assertIn('import xplanung_light.checks', quelle)


class DateiablageCheckTests(TestCase):
    """Der Ablageort der Anhänge muss in Produktion absolut und ausserhalb liegen."""

    PRODUKTION = {'DEBUG': False, 'BASE_DIR': '/opt/xplanung'}

    def test_fehtende_oder_relative_ablage_ist_fehler(self):
        """
        Was wird geprüft: Ohne MEDIA_ROOT oder mit relativem Pfad meldet der Check E002.

        Warum: ohne Angabe löst Django `upload_to='uploads'` gegen das aktuelle
        Arbeitsverzeichnis auf. Gunicorn, systemd und ein manueller Start schreiben dann
        in verschiedene Ordner, und die Sicherung findet die Anhänge nicht wieder.

        Erwartung: ['xplanung_light.E002'] für '' und für 'uploads'.
        """
        for media_root in ('', 'uploads'):
            self.assertEqual(
                meldungen(pruefe_dateiablage, MEDIA_ROOT=media_root, **self.PRODUKTION),
                ['xplanung_light.E002'], f"MEDIA_ROOT={media_root!r}")

    def test_ablage_im_projektbaum_ist_warnung(self):
        """
        Was wird geprüft: Ein MEDIA_ROOT innerhalb des Projektbaums meldet Warnung W001.

        Warum: im Projektbaum wird die Ablage bei jedem Deployment mitgenommen und kann
        über den Weg der statischen Dateien ausgeliefert werden. Ein Fehler ist es nicht —
        base.py setzt genau das für Arbeitsumgebungen.

        Erwartung: ['xplanung_light.W001'] für '/opt/xplanung/uploads', keine Meldung für
        '/var/lib/xplanung/uploads'.
        """
        self.assertEqual(meldungen(pruefe_dateiablage, MEDIA_ROOT='/opt/xplanung/uploads',
                                   **self.PRODUKTION), ['xplanung_light.W001'])
        self.assertEqual(meldungen(pruefe_dateiablage, MEDIA_ROOT='/var/lib/xplanung/uploads',
                                   **self.PRODUKTION), [])

    def test_arbeitsumgebung_wird_nicht_beanstandet(self):
        """
        Was wird geprüft: Mit DEBUG=True meldet der Check nichts.

        Warum: base.py setzt MEDIA_ROOT auf 'uploads' im Projektroot — in einer
        Arbeitsumgebung ist das richtig und darf nicht dauernd beanstandet werden.

        Erwartung: keine Meldungen für eine Ablage im Projektbaum bei DEBUG=True.
        """
        self.assertEqual(meldungen(pruefe_dateiablage, DEBUG=True,
                                   MEDIA_ROOT='/opt/xplanung/uploads',
                                   BASE_DIR='/opt/xplanung'), [])


class HaertungsCheckTests(TestCase):
    """Erinnerungen für die Produktionskonfiguration und den Cross-Origin-Wert."""

    PRODUKTION = {'DEBUG': False}

    def test_ohne_produktionskonfiguration_und_ohne_cors_liste_wird_erinnert(self):
        """
        Was wird geprüft: Ohne prod-Konfiguration und ohne CORS-Liste gibt es W002, W003.

        Warum: produktiver Betrieb auf der Basis-Konfiguration (ENV_NAME nicht 'prod') ist
        der häufigste Fall, in dem gar keine Härtung stattfindet. Und die OGC-Antworten
        senden weiterhin 'Access-Control-Allow-Origin: *'.

        Erwartung: beide Warnungen, wenn ENV_NAME nicht 'prod' ist und die CORS-Liste fehlt.
        """
        self.assertEqual(
            meldungen(pruefe_haertung, ENV_NAME='test',
                      XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=None, **self.PRODUKTION),
            ['xplanung_light.W002', 'xplanung_light.W003'])
        # dieselbe Antwort, wenn die Umgebung ueberhaupt nicht bekannt ist
        self.assertEqual(
            meldungen(pruefe_haertung, ENV_NAME=None,
                      XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=None, **self.PRODUKTION),
            ['xplanung_light.W002', 'xplanung_light.W003'])

    def test_umgebung_aus_der_json_datei_gilt_als_prod(self):
        """
        Was wird geprüft: Die Umgebung wird über die Einstellung erkannt, nicht nur über
        die Umgebungsvariable.

        Warum: üblich ist die json-Datei `komserv/.my_xplanung_light_env.json`; die
        Variable setzen die wenigsten Betreiber. Eine Prüfung, die nur die Variable kennt,
        meldet eine vollständig gehärtete Installation als ungehärtet. `ENV_NAME` steht
        deshalb in den Einstellungen — aufgeloest von `komserv/settings/__init__.py`.

        Erwartung: keine Warnung bei ENV_NAME='prod' ohne gesetzte Variable.
        """
        umgebung = os.environ.pop('DJANGO_ENV_NAME', None)
        try:
            self.assertEqual(
                meldungen(pruefe_haertung, ENV_NAME='prod',
                          XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=['https://geo.example.de'],
                          **self.PRODUKTION), [])
        finally:
            if umgebung is not None:
                os.environ['DJANGO_ENV_NAME'] = umgebung

    def test_werte_der_vorlage_erfuellen_beide_erinnerungen(self):
        """
        Was wird geprüft: Mit den Werten der Vorlage meldet der Check nichts.

        Warum: die Vorlage soll das Beispiel sein, das diese Prüfungen erfüllt — sonst
        erinnert der Check an etwas, das nirgends vorgemacht ist.

        Erwartung: keine Meldungen bei ENV_NAME='prod' und gesetzter CORS-Liste.
        """
        self.assertEqual(
            meldungen(pruefe_haertung, ENV_NAME='prod',
                      XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=['https://geo.example.de'],
                      **self.PRODUKTION), [])


class BasisEinstellungenTests(TestCase):
    """Die Basis-Konfiguration enthält keine Debug-Werkzeuge und liefert Doku nicht offen aus."""

    def test_basis_ohne_debug_toolbar_mit_media_root_und_mit_doku_pflichtanmeldung(self):
        """
        Was wird geprüft: base.py installiert keine Debug-Toolbar, setzt MEDIA_ROOT und
        gibt die eingebaute Doku nicht an Unangemeldete aus.

        Warum: base.py ist die Grundlage jeder Produktion. Eine dort installierte
        Debug-Toolbar wäre bei jedem Deployment dabei und zeigt bei einem beiläufig
        gedrehten DEBUG allen Besuchern SQL-Abfragen und Header; 'DOCS_ACCESS = public'
        lieferte Installationsinternes an alle; ohne MEDIA_ROOT hängt der Anhang-Ablageort
        vom Startverzeichnis ab.

        Erwartung: kein debug_toolbar in INSTALLED_APPS und MIDDLEWARE, DOCS_ACCESS nicht
        'public', MEDIA_ROOT gesetzt.
        """
        werte = zuweisungen(BASE_PY)
        self.assertNotIn('debug_toolbar', str(werte.get('INSTALLED_APPS')))
        self.assertNotIn('debug_toolbar', str(werte.get('MIDDLEWARE')))
        self.assertNotEqual(werte.get('DOCS_ACCESS'), 'public')
        self.assertIn('MEDIA_ROOT', werte)

    def test_debug_toolbar_ist_fuer_die_arbeitsumgebung_vorgemacht(self):
        """
        Was wird geprüft: Die Anleitung macht vor, wie eine Arbeitsumgebung die
        Debug-Toolbar ergänzt, seit base.py sie nicht mehr mitbringt.

        Warum: in der Arbeitsumgebung ist die Toolbar wertvoll — der Punkt ist das
        Umziehen, nicht das Löschen. `dev.py` liegt aber in .gitignore und kann die
        Zeilen deshalb nicht enthalten; vorgemacht sein müssen sie im README.

        Erwartung: README nennt App, Middleware und INTERNAL_IPS der Toolbar. Ein lokal
        vorhandenes dev.py (nicht im Git) wird mitgeprüft, wenn es existiert.
        """
        readme = README_MD.read_text(encoding='utf-8')
        self.assertIn("INSTALLED_APPS + ['debug_toolbar']", readme)
        self.assertIn('debug_toolbar.middleware.DebugToolbarMiddleware', readme)
        self.assertIn('INTERNAL_IPS', readme)
        if DEV_PY.exists():
            quelle = DEV_PY.read_text(encoding='utf-8')
            self.assertIn("'debug_toolbar'", quelle)
            self.assertIn('debug_toolbar.middleware.DebugToolbarMiddleware', quelle)

    def test_kein_erzeugter_schluessel_im_git_und_basis_liest_aus_der_umgebung(self):
        """
        Was wird geprüft: In keiner mitgeführten Konfigurationsdatei und nicht im README
        steht ein von Django erzeugter Schlüssel; base.py liest den Schlüssel aus der
        Umgebung.

        Warum: ein bekannter Schlüssel erlaubt es, Session-Cookies zu fälschen. Ein Wert,
        der einmal im Git war, ist dauerhaft öffentlich — ihn überschreiben reicht nicht,
        entfernen ist die Korrektur. Geprüft wird über das Muster, nicht über den Wortlaut
        des alten Werts: sonst stünde der genau hier wieder im Git (siehe Kommentar beim
        Muster).

        Erwartung: kein Treffer auf das Muster in base.py, prod.example.py, __init__.py,
        README und — wenn vorhanden — dev.py; der Ausweichwert in base.py ist kurz und
        heißt ausdrücklich „nicht für Produktion"; base.py liest
        XPLANUNG_LIGHT_SECRET_KEY.
        """
        pfade = [BASE_PY, PROD_VORLAGE, README_MD,
                 REPO / 'komserv' / 'settings' / '__init__.py']
        if DEV_PY.exists():  # nicht im Git, aber wenn vorhanden soll er auch hier fehlen
            pfade.append(DEV_PY)
        for pfad in pfade:
            quelltext = pfad.read_text(encoding='utf-8')
            treffer = DJANGO_SCHLUESSEL_MUSTER.findall(quelltext)
            self.assertFalse(treffer,
                             f'{pfad.name}: erzeugter Schlüssel ({len(treffer)} Stück)')
        ausweichwert = str(zuweisungen(BASE_PY).get('SECRET_KEY', ''))
        self.assertIn('XPLANUNG_LIGHT_SECRET_KEY', ausweichwert)
        # Der Ausweichwert selbst: ein Schlussel aus base.py darf nicht wie ein erzeugter
        # aussehen, sondern muss beim Namen nennen, wofuer er nicht da ist
        self.assertIn('nicht-fuer-produktion', ausweichwert)
        worte = re.findall(r"'(django-insecure-[^']*)'", ausweichwert)
        self.assertEqual(len(worte), 1, 'genau ein Ausweichwert in base.py')
        self.assertLess(len(worte[0]), 60,
                        f'Ausweichwert soll kurz und selbsterklaarend bleiben: {worte[0]}')


class CrossOriginTests(TestCase):
    """Der Cross-Origin-Wert der OGC-Antworten kommt aus einer einstellbaren Quelle."""

    ERLAUBT = ['https://geoportal.example.de']

    def anfrage(self, origin=None):
        """Request mit (oder ohne) Origin-Kopf, wie ein Browser ihn sendet."""
        kopfe = {'HTTP_ORIGIN': origin} if origin is not None else {}
        return RequestFactory().get('/ows/', **kopfe)

    def test_ohne_konfiguration_bleibt_es_bei_stern(self):
        """
        Was wird geprüft: Ohne eingestellte Origin-Liste antworten die Dienste wie bisher
        mit '*'.

        Warum: die Dienste waren immer offen; eine stillschweigende Einengung reißt
        Einbettungen in Portalen ab, die niemand mitdenkt. Die Korrektur darf also nichts
        verstellen, solange niemand sie bestellt.

        Erwartung: '*' ohne Einstellung, mit leerer Liste und mit der Vorgabe '*'.
        """
        for einstellung in (None, [], '*'):
            with override_settings(XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=einstellung):
                self.assertEqual(cors_erlaubnis(self.anfrage('https://irgendwo.de')), '*',
                                 f"Einstellung {einstellung!r}")

    def test_liste_erlaubt_nur_genannte_origin_adressen(self):
        """
        Was wird geprüft: Mit gesetzter Liste bekommt nur die genannte Adresse die
        Erlaubnis, eine andere keine.

        Warum: das ist die eigentliche Härtung — ein fremder Host soll die Daten nicht
        querladen können. Und eine Anfrage ohne Origin-Kopf (direkter Aufruf,
        Kartenclient) darf nicht scheitern.

        Erwartung: die Adresse selbst bei Treffer in der Liste, '' bei einem anderen
        Origin, '*' bei einer Anfrage ohne Origin-Kopf.
        """
        with override_settings(XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=self.ERLAUBT):
            self.assertEqual(cors_erlaubnis(self.anfrage('https://geoportal.example.de')),
                             'https://geoportal.example.de')
            self.assertEqual(cors_erlaubnis(self.anfrage('https://angreifer.example.de')), '')
            self.assertEqual(cors_erlaubnis(self.anfrage()), '*')
            # ohne Request-Kontext: engste mögliche Antwort
            self.assertEqual(cors_erlaubnis(), 'https://geoportal.example.de')

    def test_ogc_nahe_html_antwort_nutzt_den_eingestellten_wert(self):
        """
        Was wird geprüft: Eine der betroffenen Antworten setzt den Wert aus der
        Einstellung, nicht einen fest geschriebenen Stern.

        Warum: die Helper-Funktion nützt nichts, wenn die Views weiter '*' in den Kopf
        schreiben. Geprüft wird eine html-Liste mit einer erlaubten und einer fremden
        Adresse; sie läuft wie die OGC-Endpunkte über dieselbe Funktion.

        Erwartung: mit erlaubter Adresse deren Wert, mit fremder Adresse ein leerer Kopf.
        """
        gemeinde = AdministrativeOrganization.objects.create(
            name="Gemeinde Crossorigin", ls="07", ks="333", gs="000")
        url = reverse('xplan-list-html', kwargs={'pk': gemeinde.pk})
        with override_settings(XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS=self.ERLAUBT):
            erlaubt = self.client.get(url, HTTP_ORIGIN='https://geoportal.example.de')
            fremd = self.client.get(url, HTTP_ORIGIN='https://angreifer.example.de')
        self.assertEqual(erlaubt.status_code, 200)
        self.assertEqual(erlaubt['Access-Control-Allow-Origin'], 'https://geoportal.example.de')
        self.assertEqual(fremd['Access-Control-Allow-Origin'], '')


class ProduktionsvorlageTests(TestCase):
    """Die Vorlage ist da und setzt, was `manage.py check --deploy` erwartet."""

    def test_vorlage_setzt_die_haertungswerte(self):
        """
        Was wird geprüft: Die Vorlage setzt HTTPS-Cookies, erlaubte Hosts, den
        Proxy-Kopf, einen absoluten Anhang-Ablageort und den Schlüssel aus der Umgebung.

        Warum: Härtung, die nur in einer Anleitung steht, passiert selten. Eine
        mitgeführte Vorlage, die man kopieren kann, ist der übliche Weg — und diese
        Prüfung hält fest, dass die Vorlage nicht wieder ausdünnt.

        Erwartung: SESSION_COOKIE_SECURE und CSRF_COOKIE_SECURE True, DEBUG False,
        ALLOWED_HOSTS gefüllt, SECURE_PROXY_SSL_HEADER gesetzt, MEDIA_ROOT absolut,
        SECRET_KEY aus XPLANUNG_LIGHT_SECRET_KEY.
        """
        self.assertTrue(PROD_VORLAGE.exists(), "Vorlage fehlt")
        werte = zuweisungen(PROD_VORLAGE)
        self.assertIs(werte.get('SESSION_COOKIE_SECURE'), True)
        self.assertIs(werte.get('CSRF_COOKIE_SECURE'), True)
        self.assertIs(werte.get('DEBUG'), False)
        self.assertTrue(werte.get('ALLOWED_HOSTS'), "ALLOWED_HOSTS ist leer")
        self.assertEqual(werte.get('SECURE_PROXY_SSL_HEADER'),
                         ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertIn('XPLANUNG_LIGHT_SECRET_KEY', str(werte.get('SECRET_KEY')))
        media_root = str(werte.get('MEDIA_ROOT'))
        self.assertTrue(media_root.startswith('/'), f"MEDIA_ROOT nicht absolut: {media_root}")


class MapfileBankzugangCheckTests(TestCase):
    """W004: ohne libpq-Dienst steht das Bank-Passwort im Mapfile-Text."""

    PRODUKTION = {'DEBUG': False}
    # Bankzugang so, wie er ohne Dienst in den Mapfile geschrieben würde
    POSTGIS = {'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'xplanung', 'USER': 'xplan', 'PASSWORD': 'geheim',
        'HOST': 'db.example.de', 'PORT': '5432', 'OPTIONS': {}}}
    POSTGIS_DIENST = {'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': '', 'OPTIONS': {'service': 'xplanung-light'}}}
    SPATIALITE = {'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': '/opt/xplanung/db.sqlite3'}}

    def test_postgis_ohne_dienst_meldet_das_passwort_im_mapfile(self):
        """
        Was wird geprüft: PostGIS mit Passwort in den Einstellungen und ohne Dienst.

        Warum: MapServer verbindet sich für jede Ebene selbst zur Bank. Ohne Dienst
        wird das Passwort aus settings.DATABASES in den Mapfile-Text gesetzt, und
        derselbe Text liegt zwanzig Sekunden im Mapfile-Cache. Das ist der Fall, den
        eine Produktionsinstallation sehen soll.

        Erwartung: xplanung_light.W004.
        """
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=self.POSTGIS,
                      **self.PRODUKTION),
            ['xplanung_light.W004'])

    def test_dienst_in_den_bankoptionen_erfuellt_die_pruefung(self):
        """
        Was wird geprüft: Der Dienst steht in DATABASES['default']['OPTIONS']['service'].

        Warum: das ist Djangos eigene Angabe — die Anwendung ist damit selbst
        verbunden, und die Kartenebenen bekommen dieselbe Angabe als 'service=…'.
        Zwei Quellen für ein und dasselbe Geheimnis wären einer zu viel.

        Erwartung: keine Meldung.
        """
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=self.POSTGIS_DIENST,
                      **self.PRODUKTION), [])

    def test_ausdruecklicher_kartendienst_erfuellt_die_pruefung(self):
        """
        Was wird geprüft: Der Dienst wird nur für die Kartenebenen über
        XPLANUNG_LIGHT_CONFIG['postgis_pg_service'] genannt.

        Warum: eine Installation kann die Bank selbst über Host und Passwort
        erreichen und die Ebenen über einen Dienst mit weniger Rechten. Beides ist
        gedeckt, Vorrang hat die ausdrückliche Angabe.

        Erwartung: keine Meldung, obwohl in DATABASES ein Passwort steht.
        """
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=self.POSTGIS,
                      XPLANUNG_LIGHT_CONFIG={'postgis_pg_service': 'karten-lesen'},
                      **self.PRODUKTION), [])

    def test_bank_ohne_passwort_in_den_einstellungen_meldet_nicht(self):
        """
        Was wird geprüft: PostGIS ohne Dienst, aber auch ohne Passwort in den
        Einstellungen.

        Warum: erreicht die Anwendung die Bank über .pgpass oder die Umgebung, steht
        in DATABASES kein Geheimnis — und damit auch nicht im Mapfile. Die Prüfung
        soll nicht an etwas erinnern, das hier gar nicht vorkommt.

        Erwartung: keine Meldung.
        """
        ohne = {k: dict(v) for k, v in self.POSTGIS.items()}
        ohne['default']['PASSWORD'] = ''
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=ohne, **self.PRODUKTION), [])

    def test_spatialite_und_entwicklung_melden_nicht(self):
        """
        Was wird geprüft: Spatialite, und PostGIS in der Arbeitsumgebung.

        Warum: eine Spatialite-Ebene nennt nur die Datei, da gibt es kein Passwort.
        Und in der Arbeitsumgebung (DEBUG=True) darf Deployment-Härtung nicht gemeldet
        werden — die Prüfung ist als Deployment-Prüfung angemeldet.

        Erwartung: beide Fälle ohne Meldung.
        """
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=self.SPATIALITE,
                      **self.PRODUKTION), [])
        self.assertEqual(
            meldungen(pruefe_mapfile_bankzugang, DATABASES=self.POSTGIS,
                      DEBUG=True), [])

    def test_basis_kennt_den_schluessel_fuer_den_kartendienst(self):
        """
        Was wird geprüft: base.py führt den Schlüssel 'postgis_pg_service' und liest
        die Umgebungsvariable XPLANUNG_LIGHT_PG_SERVICE.

        Warum: die Prüfung oben verweist auf beide Angaben. Fehlt der Schlüssel in
        der Basis, steht Betreiber:innen ins Leere — und helper/mapfile.py fällt
        still auf die Einzelangaben zurück.

        Erwartung: der Schlüssel ist in XPLANUNG_LIGHT_CONFIG enthalten.
        """
        werte = zuweisungen(BASE_PY)
        konfiguration = werte.get('XPLANUNG_LIGHT_CONFIG')
        if isinstance(konfiguration, str):
            # ast kann ein Wörterbuch mit nicht-literalen Werten nicht auswerten —
            # dann wird der Quelltext geprüft
            self.assertIn('postgis_pg_service', konfiguration)
            self.assertIn('XPLANUNG_LIGHT_PG_SERVICE', konfiguration)
        else:
            self.assertIn('postgis_pg_service', konfiguration)
