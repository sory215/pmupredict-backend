"""
Analyse de l'équipement du cheval.

Ce module sera enrichi avec:
- oeillères classiques
- oeillères australiennes
- ferrure
- impact historique de chaque combinaison
"""

from __future__ import annotations

import pandas as pd


EQUIPMENT_IMPACT = {
    "oeilleres_australiennes": 1.05,
    "oeilleres_classiques": 0.98,
    "ferrure_plaque_ant": 1.00,
    "ferrure_plaque_post": 1.02,
    "ferrure_plaque_4": 1.05,
    "ferrure_deferre_ant": 0.95,
    "ferrure_deferre_post": 0.97,
    "ferrure_deferre_4": 0.90,
    "ferrure_mixte": 1.00,
}


def encoder_equipement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare les variables d'équipement.

    Pour l'instant, cette fonction ne modifie pas les données
    si les colonnes correspondantes ne sont pas présentes.
    """
    result = df.copy()

    if "est_deferre" not in result.columns:
        result["est_deferre"] = False

    return result
