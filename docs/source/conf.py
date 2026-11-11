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

templates_path = ['_templates']
exclude_patterns = []

language = 'de'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
