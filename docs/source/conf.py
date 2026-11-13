# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'XPlanung-light'
copyright = '2026, GDI-RP'
author = 'GDI-RP'

# -- Version -----------------------------------------------------------------
# Gelesen aus xplanung_light/__init__.py, damit Doku und App dieselbe Zahl zeigen
# und niemand sie hier nachtragen muss. Als Textauswertung und nicht als Import:
# der Doc-Bau zieht dadurch keine App-Abhaengigkeiten (Settings, Datenbank) nach.
import re
from pathlib import Path

_VERSION_DATEI = Path(__file__).resolve().parents[2] / 'xplanung_light' / '__init__.py'
_GELESEN = re.search(r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                     _VERSION_DATEI.read_text(encoding='utf-8'), re.MULTILINE)
if not _GELESEN:
    raise RuntimeError('%s enthaelt kein __version__' % _VERSION_DATEI)

_VERSION = _GELESEN.group(1)
# version steht im Kopf des Themes, release in den Metadaten und im HTML-Titel:
# dort die Haupt- und Unterart, hier die volle Zahl.
version = '.'.join(_VERSION.split('.')[:2])
release = _VERSION

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx_rtd_theme',
]

# -- Fassungen nebeneinander -------------------------------------------------
# sphinx-multiversion baut aus master und aus den Versionstags (v1.0.0) je eine
# eigene Fassung, die sich gegenseitig verlinken. Das Paket gehört nur in den
# Doku-Bau der Workflows, nicht in die Anwendungsumgebung. Darum die Abfrage:
# fehlt das Paket, bleibt es beim bekannten Einzelbau. Ohne diese Absicherung
# würde schon der Merge dieses Zweigs den Doku-Bau unlaufen, solange der
# Workflow das Paket noch nicht installiert.
try:
    import sphinx_multiversion  # noqa: F401
except ImportError:
    pass
else:
    extensions.append('sphinx_multiversion')
    # Gebaut werden master und die Versionstags, Fremdrepos bleiben aussen vor.
    smv_branch_whitelist = r'^master$'
    smv_tag_whitelist = r'^v\d+\.\d+\.\d+$'
    smv_remote_whitelist = None
    # Was eine veröffentlichte Fassung ist (für den Umschalter: "Entwicklung"
    # oder nicht). sphinx-multiversion prüft das gegen den vollen Referenznamen,
    # also refs/tags/... — die in den Beispielen der Erweiterung genannte Form
    # ^tags/... greift deshalb nicht.
    smv_released_pattern = r'^(refs/)?tags/v\d+\.\d+\.\d+$'
    # Jede Fassung in ein eigenes Verzeichnis; die alten Adressen ohne
    # Verzeichnis übernimmt docs/build-versionen.sh als Weiterleitung.
    smv_outputdir_format = '{ref.name}'

templates_path = ['_templates']
exclude_patterns = []

language = 'de'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
