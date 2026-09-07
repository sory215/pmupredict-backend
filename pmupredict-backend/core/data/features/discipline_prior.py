"""
Priors expérimentaux par discipline.

IMPORTANT:
ces coefficients sont des hypothèses configurables et ne constituent
pas des vérités statistiques. Ils devront être validés par backtest.
"""

from __future__ import annotations

DISCIPLINE_PRIOR = {
    "attelé": {
        "favoris": 0.45,
        "outsiders": 0.35,
        "tocard": 0.20,
    },
    "plat": {
        "favoris": 0.40,
        "outsiders": 0.40,
        "tocard": 0.20,
    },
    "haie": {
        "favoris": 0.30,
        "outsiders": 0.30,
        "tocard": 0.40,
    },
}


def get_discipline_prior(discipline: str) -> dict:
    key = str(discipline or "").strip().lower()
    return DISCIPLINE_PRIOR.get(
        key,
        {"favoris": 1 / 3, "outsiders": 1 / 3, "tocard": 1 / 3},
    )
