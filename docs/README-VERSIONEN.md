# Doku in mehreren Fassungen (master und die veröffentlichten Versionen)

## Was dabei herauskommt

| Adresse | Inhalt |
|---|---|
| `.../xplanung_light/master/<seite>.html` | Doku der aktuellen Entwicklung |
| `.../xplanung_light/v1.0.0/<seite>.html` | Doku des Stands, auf dem der Tag `v1.0.0` sitzt |
| `.../xplanung_light/<seite>.html` | Adressen, wie sie in `publiccode.yml`, in den Templates und in den Handreichungen stehen — eine Weiterleitung auf `master/<seite>.html` |

In jedem gebauten Blatt sitzt rechts unten ein Umschalter („Fassung: …“) mit den
anderen Fassungen; der Weg führt zur selben Seite, wenn es sie in der anderen
Fassung gibt, sonst zu deren Startseite.

Gebaut wird, was `docs/source/conf.py` festlegt: der Zweig `master` und die Tags
`v<haupt>.<unter>.<punkt>`. Fremde Repos (Forks) bleiben draußen.

## Lokal bauen

```bash
python3 -m venv /tmp/venv-docs
/tmp/venv-docs/bin/pip install -r docs/requirements.txt
PATH="/tmp/venv-docs/bin:$PATH" docs/build-versionen.sh
```

Ergebnis liegt in `docs/build/html`. Ohne das Paket, ohne Git-Kopie oder solange
es noch keinen Versionstag gibt, weicht das Skript auf den einfachen Bau aus
(dasselbe, was `make html` tut): eine Fassung in den Bauordner, keine
Weiterleitungen, kein Umschalter. Probieren mit einem eigenen Zweig:

```bash
docs/build-versionen.sh -D 'smv_branch_whitelist=^(master|mein-zweig)$'
```

## Was der Workflow (`deploy.yml`) dafür braucht

Der Workflow baut heute mit `make html` und lädt `docs/build/html` hoch. Vier
Änderungen; der Hochladepfad bleibt, wie er ist, und der Schritt, der den
Coverage-Bericht nach `docs/build/html/coverage` legt, passt unverändert dahinter.

```yaml
      - name: Auschecken — mit Tags und voller Historie
        uses: actions/checkout@v4
        with:
          # fetch-depth: 1 (der Standard) holt weder die Tags noch genug
          # Historie — ohne diese zwei Zeilen gibt es keine Fassungen.
          fetch-depth: 0
          fetch-tags: true

      - name: Zweig master als lokale Referenz anlegen
        # sphinx-multiversion sieht nur lokale Referenzen; der Auscheckschritt
        # von actions/checkout lässt bei diesem Auslöser oft keinen lokalen
        # Zweig master zurück, dann fehlt die Fassung des Hauptzweigs.
        run: git branch -f master HEAD

      - name: Sphinx-Abhängigkeiten installieren
        run: pip install -r docs/requirements.txt

      - name: Sphinx-Dokumentation bauen
        run: docs/build-versionen.sh
```

Reihenfolge beim Mergen ist gleichgültig: bleibt der Workflow beim alten
`make html`, baut alles wie bisher; ist nur die pip-Zeile neu, läuft der einfache
Bau mit der Erweiterung, ohne dass sie etwas ändert — es fehlt ja der zweite
Baupfad. Ist das Skript drin, die pip-Zeile aber nicht, meldet das Skript den
Grund und baut die aktuelle Fassung:

```
build-versionen: sphinx-multiversion arbeitet nicht mit dem installierten Sphinx zusammen:
TypeError: Config.read() takes 2 positional arguments but 3 were given — für die
Fassungen gilt sphinx<8, siehe docs/requirements.txt — baut nur die aktuelle Fassung.
```

## Welche Pakete — und läuft das auf den unterstützten Systemen gleich?

Die Test-Workflow (`django-tests.yml`) baut keine Doku; von dort läuft nichts in
den Dokubauf. Der Doku-Bau (`deploy.yml`) installierte die Pakete bisher
ungebunden, und das ist je Python-Fassung etwas anderes (gemessen am 12.11.2026
mit trockenen pip-Durchläufen, pip 26.3):

| installiert | Python 3.9 (Debian 11) | 3.11 (Debian 12) | 3.12 (Runner) | 3.13 (Debian 13) |
|---|---|---|---|---|
| `pip install sphinx sphinx_rtd_theme myst_parser` (heute) | Sphinx 7.4.7 | Sphinx 9.0.4 | Sphinx 9.1.1 | Sphinx 9.2.0 |
| `pip install -r docs/requirements.txt` (dieser Zweig) | Sphinx 7.4.7, Theme 3.0.2 | dito | dito | dito |

Dasselbe Bild in den Anwendungs-Anforderungen, und die waren sich bisher uneins:
`requirements.txt` (Debian 11/12) band `sphinx==7.4.7` und
`sphinx-rtd-theme==3.0.2`, `requirements_deb13.txt` ließ beide ungebunden — auf
Debian 13 also Sphinx 9.2. Ein lokaler Dokubau hätte damit auf Debian 12 die
Fassungen nebeneinander erzeugt und auf Debian 13 stillschweigend nur eine.
Dieser Zweig bindet in `requirements_deb13.txt` dasselbe Paar wie in
`requirements.txt`; mit den Bindungen aus `docs/requirements.txt` bauen Debian
11, 12, 13 und der Runner nachweislich mit derselben Fassung (Sphinx 7.4.7,
docutils 0.21.2, Theme 3.0.2, multiversion 0.2.4 auf Python 3.9, 3.11, 3.12, 3.13).

Empfohlen bleibt für die Doku ein eigenes venv — die Anwendungs-Umgebung braucht
die Baupakete nicht, und `django-docs` (in beiden Anforderungslisten, aber im
Projekt nirgends eingebunden) ändert daran nichts.

### Warum dieses Paket — und nicht ein anderes

Geprüft am 12.11.2026:

- **Upstream** (`sphinx-contrib/multiversion`, früher `Holzhaus/sphinx-multiversion`):
  das Repo ist aktiv, aber es gibt nichts Neueres als 0.2.4 auf PyPI, und der
  unveröffentlichte main-Stand (0.2.5) ruft weiterhin `Config.read(confdir,
  confoverrides)` auf — mit Sphinx 8 und 9 also unbrauchbar.
- **`sphinx-multiversion-scylla` 0.3.9** (Fork, PyPI 10/2026): gemessen laufend mit
  Sphinx 7.4.7 wie mit 9.2.0; Modul- und Programmname sind dieselben, der Tausch
  wäre eine Zeile in `docs/requirements.txt` und die Sphinx-Bindung könnte wieder
  raus. Was dagegen spricht, ist entscheidbar und nicht technisch: die 0.3.x liegen
  auf keinem öffentlichen Repo, der Quelltext steckt nur als Quellpaket auf PyPI
  (1070 Zeilen Python in vier Modulen; die Korrektur selbst ist klein).
- **Ein eigenes Bauprogramm** (je Referenz ein Arbeitszweig, dann `sphinx-build`):
  rund hundert eigene Zeilen, dafür kein Fremdcode — und ein CI-Job, der den
  Dokubau baut, sonst merkt niemand, wenn er kaputtgeht.
- **Beim Veröffentlichen ins Archiv legen** statt je Referenz neu zu bauen: ohne
  Fremdpaket und ohne Sphinx-Bindung, die bestehenden Adressen bleiben ohne jede
  Weiterleitung gültig. Dafür wird das nachträgliche Ändern einer alten Fassung ein
  bewusster Schritt statt eines laufenden Baus, und alte Fassungen sehen aus wie am
  Tag ihrer Veröffentlichung (was auch ein Vorteil ist).

Dieser Stand nimmt die Sphinx-Bindung unter 8 in Kauf — und dass
Debian-13-Installationen von 9.2 auf 7.4.7 zurückziehen, weil nichts im App-Betrieb
Sphinx braucht.

## Die zwei Eigenheiten, die man kennen sollte

**`conf.py` und die Vorlagen kommen aus dem Auscheckvorgang, die Seiten aus der
jeweiligen Referenz.** sphinx-multiversion übergibt jedem Baulauf das
Konfigurationsverzeichnis des Repos, aus dem heraus gebaut wird (`-c`), als
Quellverzeichnis aber die Referenz. Folge: auch eine alte Fassung sieht aus wie
heute (gleiches Theme, dieselben Vorlagen) und behält doch ihren eigenen Text.
Die Versionszahl im Seitentitel ist davon ausgenommen — die liest die Erweiterung
aus dem `conf.py` der Referenz und setzt sie vor dem Bau wieder ein, jede Fassung
zeigt also ihre eigene Zahl.

**`sphinx` bleibt unter 8, solange die Fassungen nebeneinander gebaut werden** —
die Begründung steht in `docs/requirements.txt`. Der einfache Bau ist davon nicht
betroffen.

## Neue Fassung veröffentlichen

Schritt für Schritt in `RELEASING.md`. Für die Doku ist nur der Tag maßgeblich:
`git tag -a v1.0.0 origin/master && git push origin v1.0.0`, danach läuft der
Dokubauf von selbst, weil er an den erfolgreichen Lauf der Test-Workflow gekoppelt
ist. Der Umschalter zeigt `v1.0.0` dann ohne den Zusatz „(Entwicklung)“, weil
`smv_released_pattern` auf Tags dieser Form passt.
