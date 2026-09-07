"""
PMUPredict — Probability Engine v1

Couche probabiliste indépendante du modèle principal.

Fonctions :
- softmax stable
- température
- entropie
- log-probabilité
- log loss
- Brier score
"""

from __future__ import annotations

import math
from typing import Iterable, List


def softmax(scores: Iterable[float], temperature: float = 1.0) -> List[float]:
    """
    Transforme une liste de scores en distribution de probabilités.

    temperature < 1  -> distribution plus concentrée
    temperature = 1  -> distribution standard
    temperature > 1  -> distribution plus plate
    """

    scores = [float(x) for x in scores]

    if not scores:
        return []

    if temperature <= 0:
        raise ValueError("temperature doit être > 0")

    scaled = [x / temperature for x in scores]

    # Softmax numériquement stable
    max_score = max(scaled)

    exp_scores = [
        math.exp(x - max_score)
        for x in scaled
    ]

    total = sum(exp_scores)

    if total <= 0:
        raise ValueError("Impossible de normaliser les scores")

    return [
        x / total
        for x in exp_scores
    ]


def entropy(probabilities: Iterable[float]) -> float:
    """
    Entropie de Shannon :

        H = -sum(p * log(p))

    Mesure l'incertitude de la distribution.
    """

    probabilities = [float(p) for p in probabilities]

    if not probabilities:
        return 0.0

    result = 0.0

    for p in probabilities:
        if p > 0:
            result -= p * math.log(p)

    return result


def normalized_entropy(probabilities: Iterable[float]) -> float:
    """
    Entropie normalisée entre 0 et 1.

    0 -> distribution extrêmement concentrée
    1 -> distribution parfaitement uniforme
    """

    probabilities = [float(p) for p in probabilities]

    if len(probabilities) <= 1:
        return 0.0

    h = entropy(probabilities)
    maximum = math.log(len(probabilities))

    if maximum == 0:
        return 0.0

    return h / maximum


def log_probability(probability: float, epsilon: float = 1e-15) -> float:
    """
    Log-probabilité protégée contre log(0).
    """

    p = max(float(probability), epsilon)

    return math.log(p)


def log_loss(probabilities: Iterable[float], actual_index: int) -> float:
    """
    Log loss multiclasses pour une course.

    actual_index = index du cheval réellement gagnant.
    """

    probabilities = [float(p) for p in probabilities]

    if not probabilities:
        raise ValueError("Distribution vide")

    if actual_index < 0 or actual_index >= len(probabilities):
        raise IndexError("actual_index hors limites")

    return -log_probability(probabilities[actual_index])


def brier_score(probabilities: Iterable[float], actual_index: int) -> float:
    """
    Brier score multiclasses.

    Plus le score est faible, meilleure est la prédiction.
    """

    probabilities = [float(p) for p in probabilities]

    if actual_index < 0 or actual_index >= len(probabilities):
        raise IndexError("actual_index hors limites")

    score = 0.0

    for i, p in enumerate(probabilities):
        target = 1.0 if i == actual_index else 0.0
        score += (p - target) ** 2

    return score


def confidence_from_entropy(probabilities: Iterable[float]) -> float:
    """
    Transforme l'entropie normalisée en indice de confiance.

    1.0 -> très concentré
    0.0 -> très incertain
    """

    return 1.0 - normalized_entropy(probabilities)


def probability_distribution(
    scores: Iterable[float],
    temperature: float = 1.0,
) -> dict:
    """
    Fonction centrale.

    Retourne :
    - probabilités
    - entropie
    - entropie normalisée
    - confiance
    - température
    """

    probabilities = softmax(scores, temperature)

    return {
        "probabilities": probabilities,
        "temperature": float(temperature),
        "entropy": entropy(probabilities),
        "entropy_normalized": normalized_entropy(probabilities),
        "confidence": confidence_from_entropy(probabilities),
    }


def score_to_logit(
    score: float,
    center: float = 50.0,
    scale: float = 10.0,
) -> float:
    """
    Convertit un score PMUPredict 0-100
    en valeur adaptée à une couche probabiliste.

    Le score original reste inchangé.

    center :
        point central de l'échelle.

    scale :
        contrôle l'amplitude du score probabiliste.
    """

    if scale <= 0:
        raise ValueError("scale doit être > 0")

    return (float(score) - center) / scale


def probability_distribution_from_scores(
    scores: Iterable[float],
    temperature: float = 1.0,
    scale: float = 10.0,
) -> dict:
    """
    Transforme les scores PMUPredict 0-100
    en distribution probabiliste.

    Pipeline :

        score PMUPredict
            ↓
        score_to_logit
            ↓
        softmax + température
            ↓
        probabilités
    """

    scores = [float(x) for x in scores]

    logits = [
        score_to_logit(
            score,
            center=50.0,
            scale=scale,
        )
        for score in scores
    ]

    result = probability_distribution(
        logits,
        temperature=temperature,
    )

    result["scale"] = float(scale)
    result["logits"] = logits

    return result


def calibrated_distribution(
    scores: Iterable[float],
    scale: float = 10.0,
    temperature: float = 1.0,
) -> dict:
    """
    Distribution probabiliste calibrée à partir
    des scores PMUPredict 0-100.
    """

    return probability_distribution_from_scores(
        scores,
        temperature=temperature,
        scale=scale,
    )


def evaluate_prediction(
    probabilities: Iterable[float],
    actual_index: int,
) -> dict:
    """
    Évalue une distribution probabiliste par rapport
    au cheval réellement gagnant.

    Retourne :
    - log_loss
    - brier_score
    - probabilité attribuée au gagnant
    """

    probabilities = [float(p) for p in probabilities]

    if not probabilities:
        raise ValueError("Distribution vide")

    if actual_index < 0 or actual_index >= len(probabilities):
        raise IndexError("actual_index hors limites")

    winner_probability = probabilities[actual_index]

    return {
        "log_loss": round(
            log_loss(probabilities, actual_index),
            6,
        ),
        "brier_score": round(
            brier_score(probabilities, actual_index),
            6,
        ),
        "winner_probability": round(
            winner_probability,
            6,
        ),
    }
