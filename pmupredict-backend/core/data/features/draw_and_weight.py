"""
Features liées au numéro/à la corde et au poids.

Les coefficients doivent être validés historiquement avant
d'être appliqués comme bonus/malus de prédiction.
"""

from __future__ import annotations

import pandas as pd


def calculer_avantage_corde(df: pd.DataFrame) -> pd.Series:
    """Version neutre initiale : aucun bonus arbitraire."""
    return pd.Series(0.0, index=df.index)


def calculer_impact_poids(df: pd.DataFrame) -> pd.Series:
    """Version neutre initiale : conserve le poids brut."""
    if "poids_kg" in df.columns:
        return pd.to_numeric(
            df["poids_kg"],
            errors="coerce"
        ).fillna(0)

    return pd.Series(0.0, index=df.index)
