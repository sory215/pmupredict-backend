"""
Coefficients de forme, réussite et appétence.

Version initiale:
les fonctions historiques existantes restent dans legacy_features.py.
Ce module servira de couche dédiée aux nouvelles features.
"""

from __future__ import annotations

import pandas as pd


def normaliser_0_10(value, minimum=0.0, maximum=1.0):
    """Normalise une valeur vers une échelle 0-10."""
    if maximum <= minimum:
        return 0.0

    value = float(value)
    result = (value - minimum) / (maximum - minimum)
    return max(0.0, min(10.0, result * 10.0))


def calculer_forme(df: pd.DataFrame) -> pd.Series:
    """
    Point d'entrée pour la future feature de forme.
    Version initiale basée sur les performances récentes disponibles.
    """
    if "score_musique" in df.columns:
        return df["score_musique"].fillna(0).astype(float).clip(0, 10)

    return pd.Series(0.0, index=df.index)


def calculer_reussite(df: pd.DataFrame) -> pd.Series:
    """Point d'entrée pour la future feature de réussite."""
    if "taux_top3_musique" in df.columns:
        return (
            df["taux_top3_musique"]
            .fillna(0)
            .astype(float)
            .clip(0, 1)
            * 10
        )

    return pd.Series(0.0, index=df.index)


def calculer_appetence(df: pd.DataFrame) -> pd.Series:
    """Point d'entrée pour la future feature d'appétence."""
    return pd.Series(0.0, index=df.index)
