"""Service d'accès à la couche IA indépendante de PMUPredict."""

from __future__ import annotations

from core.ai.analyzer import AIAnalysis, analyser_course
from core.ai.data import load_course_ai_data


def analyser_course_id(course_id: str) -> list[AIAnalysis]:
    """Charge les données enrichies d'une course et lance l'analyse IA."""
    data = load_course_ai_data(course_id)

    return analyser_course(
        {
            "course": data["course"],
            "partants": data["partants"],
        },
        historique=data["historique"],
        arrivees=data["arrivees"],
    )
