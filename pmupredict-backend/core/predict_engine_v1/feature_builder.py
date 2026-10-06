from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .features import FEATURE_NAMES, RunnerFeatures


def _number(value: Any, default: float = 0.0) -> float:
    """Convertit proprement une valeur en nombre."""
    if value is None or value == "":
        return default

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    return result


def build_runner_features(
    runner: Mapping[str, Any],
    race: Mapping[str, Any] | None = None,
) -> RunnerFeatures:
    """
    Construit les features disponibles avant le départ.

    Aucun résultat futur ne doit être injecté ici.
    """

    race = race or {}

    return RunnerFeatures(
        horse_id=runner.get("horse_id") or runner.get("horseId"),
        race_id=runner.get("race_id") or runner.get("raceId"),

        recent_wins=_number(
            runner.get("recent_wins", runner.get("recentWins"))
        ),
        recent_places=_number(
            runner.get("recent_places", runner.get("recentPlaces"))
        ),
        recent_runs=_number(
            runner.get("recent_runs", runner.get("recentRuns"))
        ),
        recent_avg_finish=_number(
            runner.get("recent_avg_finish", runner.get("recentAvgFinish"))
        ),

        official_rating=_number(
            runner.get("official_rating", runner.get("officialRating"))
        ),
        class_rating=_number(
            runner.get("class_rating", runner.get("classRating"))
        ),

        distance=_number(
            runner.get("distance", race.get("distance"))
        ),
        weight=_number(
            runner.get("weight")
        ),
        draw=_number(
            runner.get("draw", runner.get("stall"))
        ),
        going_rating=_number(
            runner.get("going_rating", runner.get("goingRating"))
        ),

        jockey_win_rate=_number(
            runner.get("jockey_win_rate", runner.get("jockeyWinRate"))
        ),
        trainer_win_rate=_number(
            runner.get("trainer_win_rate", runner.get("trainerWinRate"))
        ),

        market_odds=_number(
            runner.get("market_odds", runner.get("odds"))
        ),
        market_probability=_number(
            runner.get("market_probability")
        ),
    )


def features_to_vector(features: RunnerFeatures) -> list[float]:
    """Convertit les features en vecteur dans un ordre stable."""
    values = asdict(features)
    return [float(values[name]) for name in FEATURE_NAMES]
