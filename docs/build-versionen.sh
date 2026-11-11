#!/usr/bin/env bash
#
# Baut die Dokumentation in einer Fassung je Git-Referenz: master und jeder
# Versionstag v1.0.0 bekommen ein eigenes Verzeichniss im Bauordner und
# verlinken sich gegenseitig (Umschalter rechts unten, Vorlage
# source/_templates/versions.html).
#
# Die Adressen ohne Fassungsverzeichniss — http.../xplanung_light/index.html,
# wie in publiccode.yml, in den Templates und in den Handreichungen steht —
# bleiben erhalten: für jede Seite der aktuellen Fassung liegt dort eine
# Weiterleitung auf die Fassung.
#
# Läuft sphinx-multiversion nicht mit (Paket fehlt, keine Git-Kopie, oder es
# gibt noch keinen Versionstag), bleibt der Bau wie bisher: eine Fassung in den
# Bauordner, keine Weiterleitungen, kein Umschalter. Der Workflow kann also vor
# dem Bauen eingerichtet werden und muss nicht.
#
# Benutzung (virtualenv auf dem Weg):
#     PATH="$PWD/.venv/bin:$PATH" docs/build-versionen.sh
#
# Umgebungsvariablen:
#     SPHINX_MULTIVERSION  das Bauprogramm (Standard: sphinx-multiversion)
#     SPHINXBUILD          der einfache Bau für den Ausnahmefall (Standard: sphinx-build)
#     PYTHON               Python für die kleine Zählerei (Standard: python3)
#     AKTUELLE_FASSUNG     Referenz, deren Seiten die alten Adressen übernehmen
#                          (Standard: master)
#
# Zusätzliche Aufrufparameter gehen an sphinx-multiversion, z. B. zum Probieren
# mit einem eigenen Zweig:
#     docs/build-versionen.sh -D smv_branch_whitelist='^(master|mein-zweig)$'

set -euo pipefail

ZUSATZ=("$@")

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUELLE="$WURZEL/source"
BAU="$WURZEL/build/html"
AKTUELLE_FASSUNG="${AKTUELLE_FASSUNG:-master}"
PYTHON="${PYTHON:-python3}"
METADATEN="$(mktemp)"
FEHLERDATEI="$(mktemp)"
trap 'rm -f "$METADATEN" "$FEHLERDATEI"' EXIT

# Genau der Bau, den "make html" heute macht — der Ausweichpfad.
einzelbau() {
  echo "build-versionen: $1 — baut nur die aktuelle Fassung (wie 'make html')." >&2
  rm -rf "$BAU"
  rm -f "$METADATEN" "$FEHLERDATEI"
  exec "${SPHINXBUILD:-sphinx-build}" -b html "$QUELLE" "$BAU"
}

command -v "${SPHINX_MULTIVERSION:-sphinx-multiversion}" >/dev/null 2>&1 \
  || einzelbau "sphinx-multiversion fehlt"
git -C "$WURZEL" rev-parse --git-dir >/dev/null 2>&1 \
  || einzelbau "keine Git-Kopie"

# Was gebaut würde. Gezählt wird vorab, weil der Rest des Skripts
# Weiterleitungen nur braucht, wenn wirklich mehrere Fassungen entstehen.
# Scheitert das Auslesen, ist das ein eigener Fall und wird nicht als "es gibt
# noch keinen Tag" ausgegeben: die übliche Ursache ist ein zu neues Sphinx, für
# das sphinx-multiversion 0.2.4 nicht mehr taugt (docs/requirements.txt).
if ! "${SPHINX_MULTIVERSION:-sphinx-multiversion}" "${ZUSATZ[@]}" --dump-metadata \
       "$QUELLE" "$BAU" >"$METADATEN" 2>"$FEHLERDATEI"; then
  URSACHE="$(grep -v '^[[:space:]]' "$FEHLERDATEI" | tail -1 | cut -c1-160)"
  einzelbau "sphinx-multiversion arbeitet nicht mit dem installierten Sphinx zusammen${URSACHE:+: $URSACHE} — für die Fassungen gilt sphinx<8, siehe docs/requirements.txt"
fi
FASSUNGEN="$("$PYTHON" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' \
               "$METADATEN" 2>/dev/null || echo 0)"
if [ "${FASSUNGEN:-0}" -lt 2 ]; then
  einzelbau "nur eine Referenz ($FASSUNGEN) — es gibt noch keinen Versionstag, siehe RELEASING.md"
fi

# Die Zahl je Fassung besorgt die Erweiterung selbst: sie liest version und
# release im conf.py der jeweiligen Referenz und setzt sie vor dem Bau wieder.
# Darum hier kein -D version=... — ein solcher Zuschrieb würde genau diese
# abgelesenen Werte überschreiben und alle Fassungen mit derselben Zahl laufen
# lassen.
rm -rf "$BAU"
"${SPHINX_MULTIVERSION:-sphinx-multiversion}" "${ZUSATZ[@]}" "$QUELLE" "$BAU"

# ---------------------------------------------------------------------------
# Adressen ohne Fassungsverzeichniss: eine Weiterleitung je Seite der aktuellen
# Fassung. Absichtlich kein inhaltlich doppeltes Abbild — doppelte Inhalte an
# zwei Adressen sind im Netz die übliche Quelle für Verwirrung in Suchmaschinen.
# ---------------------------------------------------------------------------
AKTUELLE_BAU="$BAU/$AKTUELLE_FASSUNG"
if [ ! -d "$AKTUELLE_BAU" ]; then
  echo "build-versionen: $AKTUELLE_FASSUNG wurde nicht gebaut — es gibt nur die Verzeichnisse der Fassungen." >&2
  exit 0
fi

echo "build-versionen: Weiterleitungen für die alten Adressen aus $AKTUELLE_FASSUNG"
while IFS= read -r seite; do
  relativ="${seite#"$AKTUELLE_BAU"/}"
  ziel_ordner="$BAU/$(dirname "$relativ")"
  mkdir -p "$ziel_ordner"
  verweis="$(realpath --relative-to="$ziel_ordner" "$seite")"
  cat > "$BAU/$relativ" <<WEB
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Weiterleitung — XPlanung-light</title>
  <link rel="canonical" href="$verweis">
  <meta http-equiv="refresh" content="0; url=$verweis">
  <meta name="robots" content="noindex">
</head>
<body>
  <p>Diese Seite steht jetzt in der Fassung <code>$AKTUELLE_FASSUNG</code>:
     <a href="$verweis">$relativ</a>.</p>
</body>
</html>
WEB
done < <(find "$AKTUELLE_BAU" -type f -name '*.html')

echo "build-versionen: fertig — $(find "$BAU" -name index.html | wc -l) startseiten, Fassungen:"
find "$BAU" -mindepth 2 -maxdepth 2 -name index.html | sed "s|$BAU/||; s|/index.html||" >&2
