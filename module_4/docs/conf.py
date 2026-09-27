"""Sphinx configuration; importing the app needs neither a DB nor model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
project = 'Grad Cafe - Module 4'
author = 'Carlos David Arredondo Vazquez'
copyright = '2026, ' + author
release = '1.0'
extensions = ['sphinx.ext.autodoc']
exclude_patterns = ['_build']
html_theme = 'alabaster'
html_title = 'Grad Cafe: Testing and Documentation'
html_theme_options = {'description': 'Module 4 | Pytest, PostgreSQL and Sphinx', 'fixed_sidebar': True}
autodoc_member_order = 'bysource'
