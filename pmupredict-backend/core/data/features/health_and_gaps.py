"""
Santé proxy et suivi des écarts.

Aucune donnée médicale réelle n'est utilisée.
Les indicateurs sont uniquement dérivés des historiques de courses.
"""

from __future__ import annotations

import pandas as pd


def calculer_repos(df: pd.DataFrame) -> pd.Series:
    if "jours_repos" in df.columns:
        return pd.to_numeric(
            df["jours_repos"],
            errors="coerce"
        ).fillna(0)

    return pd.Series(0.0, index=df.index)


def calculer_ecarts(df: pd.DataFrame) -> pd.Series:
    if "jours_repos" in df.columns:
        return pd.to_numeric(
            df["jours_repos"],
            errors="coerce"
        ).fillna(0)

    return pd.Series(0.0, index=df.index)
