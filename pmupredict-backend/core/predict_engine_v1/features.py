from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RunnerFeatures:
    """Variables disponibles avant le départ d'une course."""

    horse_id: Optional[str] = None
    race_id: Optional[str] = None

    # Forme récente
    recent_wins: float = 0.0
    recent_places: float = 0.0
    recent_runs: float = 0.0
    recent_avg_finish: float = 0.0

    # Niveau / performance
    official_rating: float = 0.0
    class_rating: float = 0.0

    # Conditions
    distance: float = 0.0
    weight: float = 0.0
    draw: float = 0.0
    going_rating: float = 0.0

    # Connexions
    jockey_win_rate: float = 0.0
    trainer_win_rate: float = 0.0

    # Marché
    market_odds: float = 0.0
    market_probability: float = 0.0


FEATURE_NAMES = (
    "recent_wins",
    "recent_places",
    "recent_runs",
    "recent_avg_finish",
    "official_rating",
    "class_rating",
    "distance",
    "weight",
    "draw",
    "going_rating",
    "jockey_win_rate",
    "trainer_win_rate",
    "market_odds",
    "market_probability",
)
