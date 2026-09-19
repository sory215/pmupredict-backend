"""
Comparateur marché / modèle.

Objectif:
proba modèle vs cote marché -> estimation de Value.
"""

from __future__ import annotations

import pandas as pd


def probabilite_implicite(cote) -> float:
    try:
        cote = float(cote)
        if cote <= 0:
            return 0.0
        return 1.0 / cote
    except (TypeError, ValueError):
        return 0.0


def calculer_value(probabilite, cote) -> float:
    """
    Value théorique simple:
    probabilité modèle * cote - 1
    """
    try:
        return float(probabilite) * float(cote) - 1.0
    except (TypeError, ValueError):
        return 0.0
