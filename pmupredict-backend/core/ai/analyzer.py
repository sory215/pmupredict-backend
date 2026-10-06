"""Analyse indépendante des partants PMUPredict."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class AIAnalysis:
    course_id: str
    partant_id: str
    numero: int | None
    cheval: str
    score: float
    confiance: float
    probabilite: float
    facteurs: list[str]
    value: float | None = None


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _music_positions(musique: Any) -> list[int]:
    if not isinstance(musique, str):
        return []

    positions: list[int] = []

    for token in musique.replace("(", " ").replace(")", " ").split():
        digits = ""
        for char in token:
            if char.isdigit():
                digits += char
            elif digits:
                break

        if digits:
            positions.append(int(digits))

    return positions


def _history_for_horse(
    historique: pd.DataFrame,
    cheval_nom: str,
    course_id: str,
) -> pd.DataFrame:
    if historique.empty or "cheval_nom" not in historique.columns:
        return pd.DataFrame()

    df = historique[
        historique["cheval_nom"].astype(str) == str(cheval_nom)
    ].copy()

    if "course_id" in df.columns:
        df = df[df["course_id"].astype(str) != str(course_id)]

    return df


def _positions_history(
    historique: pd.DataFrame,
    arrivees: list[dict[str, Any]],
) -> list[float]:
    if historique.empty or not arrivees:
        return []

    arrivals = pd.DataFrame(arrivees)

    if arrivals.empty or "partant_id" not in arrivals.columns:
        return []

    if "id" not in historique.columns:
        return []

    merged = historique.merge(
        arrivals[["partant_id", "position"]],
        left_on="id",
        right_on="partant_id",
        how="inner",
    )

    if "position" not in merged.columns:
        return []

    return [
        value
        for value in pd.to_numeric(
            merged["position"],
            errors="coerce",
        ).dropna().tolist()
        if value > 0
    ]


def _score_partant(
    partant: dict[str, Any],
    historique: pd.DataFrame,
    arrivees: list[dict[str, Any]],
    course_id: str,
) -> tuple[float, list[str]]:
    score = 0.0
    facteurs: list[str] = []

    cheval = str(partant.get("cheval_nom") or "")
    history = _history_for_horse(historique, cheval, course_id)
    positions = _positions_history(history, arrivees)

    if positions:
        top3 = sum(position <= 3 for position in positions)
        taux_top3 = top3 / len(positions)

        score += min(30.0, taux_top3 * 30.0)

        if taux_top3 >= 0.50:
            facteurs.append("régularité historique")
        elif taux_top3 >= 0.33:
            facteurs.append("forme correcte")

    musique = _music_positions(partant.get("musique"))

    if musique:
        recent = musique[:5]
        recent_top3 = sum(position in (1, 2, 3) for position in recent)

        score += recent_top3 * 4.0

        if recent_top3 >= 2:
            facteurs.append("musique récente favorable")

    cote_matin = _num(partant.get("cote_matin"))
    cote_actuelle = _num(partant.get("cote_actuelle"))

    if cote_actuelle > 0:
        if cote_matin > 0 and cote_actuelle < cote_matin:
            variation = (cote_matin - cote_actuelle) / cote_matin
            score += min(15.0, variation * 30.0)
            facteurs.append("cote en amélioration")

        if cote_actuelle <= 5:
            score += 8.0
            facteurs.append("cote actuelle basse")

    poids = _num(partant.get("poids_kg"))

    if poids > 0:
        if poids <= 60:
            score += 3.0
            facteurs.append("poids favorable")

    if partant.get("est_deferre") is True:
        score += 3.0
        facteurs.append("déferrage")

    if positions:
        moyenne = sum(positions) / len(positions)
        if moyenne <= 5:
            score += 10.0
            facteurs.append("moyenne des classements favorable")

    return round(score, 6), facteurs


def analyser_course(
    course: dict[str, Any],
    historique: pd.DataFrame | None = None,
    arrivees: list[dict[str, Any]] | None = None,
) -> list[AIAnalysis]:
    """Analyse tous les partants d'une course indépendamment du moteur ML."""

    historique = (
        historique
        if historique is not None
        else pd.DataFrame()
    )
    arrivees = arrivees or []

    partants = course.get("partants", [])
    course_data = course.get("course") or {}
    course_id = str(course_data.get("id") or "")

    analyses: list[AIAnalysis] = []

    for partant in partants:
        score, facteurs = _score_partant(
            partant,
            historique,
            arrivees,
            course_id,
        )

        analyses.append(
            AIAnalysis(
                course_id=course_id,
                partant_id=str(partant.get("id") or ""),
                numero=(
                    int(partant["numero"])
                    if partant.get("numero") is not None
                    else None
                ),
                cheval=str(partant.get("cheval_nom") or ""),
                score=score,
                confiance=0.0,
                probabilite=0.0,
                facteurs=facteurs,
            )
        )

    if analyses:
        scores = pd.Series([a.score for a in analyses], dtype=float)

        if float(scores.sum()) > 0:
            probabilites = scores / scores.sum()
        else:
            probabilites = pd.Series(
                [1.0 / len(analyses)] * len(analyses)
            )

        for analysis, probability in zip(
            analyses,
            probabilites.tolist(),
        ):
            analysis.probabilite = round(
                float(probability),
                6,
            )
            analysis.confiance = round(
                min(1.0, max(0.0, float(probability) * len(analyses))),
                6,
            )

    return sorted(
        analyses,
        key=lambda item: item.score,
        reverse=True,
    )
