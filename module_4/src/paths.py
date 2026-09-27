"""Keep the project's folder names in one place."""
from pathlib import Path

# __file__ is this Python file. Its parent is the src folder.
SOURCE_FOLDER = Path(__file__).resolve().parent
PROJECT_FOLDER = SOURCE_FOLDER.parent

# Fresh collections go here so the original submitted JSON files stay safe.
# Both scrape.py and clean.py use this same folder by default.
DATA_FOLDER = PROJECT_FOLDER / "runtime" / "collection"
