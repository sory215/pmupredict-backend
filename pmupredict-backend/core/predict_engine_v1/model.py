from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Prediction:
    win_probability: float
    place_probability: float
    top3_probability: float


class PredictionModel:
    """
    Interface du modèle de prédiction.

    Le modèle réel sera branché après constitution du dataset
    historique et validation temporelle.
    """

    def predict(self, features: Sequence[float]) -> Prediction:
        raise NotImplementedError(
            "Le modèle doit être entraîné avant de produire des prédictions."
        )
