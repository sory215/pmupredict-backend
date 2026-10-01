import os
import sys

# Ajouter le dossier parent (pmupredict-backend/) au chemin d'import
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Importer l'app FastAPI depuis main.py
from main import app  # noqa

# Vercel attend une variable "app" ou "handler"
handler = app
