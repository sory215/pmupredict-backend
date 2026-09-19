"""
Schémas de données PMUPredict.

Les champs disponibles actuellement dans Supabase sont pris en charge.
Les champs optionnels permettent d'intégrer progressivement les nouvelles
features sans casser le moteur existant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Horse:
    """Cheval et informations générales."""

    nom: str
    age: int | None = None
    sexe: str | None = None
    poids_kg: float | None = None
    gains: float | None = None

    # Historique / indicateurs calculés
    musique: str | None = None
    jours_repos: float | None = None
    sante_proxy: float | None = None

    # Équipement
    est_deferre: bool | None = None
    ferrure: str | None = None
    oeilleres: str | None = None


@dataclass
class Jockey:
    """Jockey et statistiques disponibles ou calculées."""

    nom: str
    nb_chevaux: int | None = None
    nb_courses: int | None = None

    # C/E = chevaux / entraîneurs
    ce: float | None = None

    taux_victoire: float | None = None
    taux_top3: float | None = None
    forme: float | None = None


@dataclass
class Trainer:
    """Entraîneur et statistiques disponibles ou calculées."""

    nom: str
    nb_chevaux: int | None = None
    nb_courses: int | None = None

    # C/J = chevaux / jockeys
    cj: float | None = None

    taux_victoire: float | None = None
    taux_top3: float | None = None
    forme: float | None = None


@dataclass
class Race:
    """Course PMU."""

    id: str
    discipline: str | None = None
    distance_m: float | None = None
    numero: int | None = None
    libelle: str | None = None
    allocation: float | None = None
    heure_depart: datetime | None = None
    statut: str | None = None

    # Informations futures / enrichissement
    corde: int | None = None
    sol: str | None = None
    meteo: str | None = None

    # Identification réunion
    reunion_id: str | None = None
    date: date | None = None

    # Quinté+
    est_quinte_plus: bool = False


@dataclass
class Partant:
    """Association cheval + jockey + entraîneur dans une course."""

    id: str
    course_id: str
    cheval: Horse

    numero: int | None = None
    jockey: Jockey | None = None
    entraineur: Trainer | None = None

    poids_kg: float | None = None

    # Marché
    cote_matin: float | None = None
    cote_actuelle: float | None = None

    # Équipement
    est_deferre: bool | None = None
    ferrure: str | None = None
    oeilleres: str | None = None

    # Historique
    position_precedente: int | None = None
    position_precedente_2: int | None = None
    jours_repos: float | None = None

    # Variables calculées
    forme: float | None = None
    reussite: float | None = None
    appetence: float | None = None

    # Features supplémentaires
    score_musique: float | None = None
    taux_top3_musique: float | None = None
    taux_incident_musique: float | None = None
    ecart_cote: float | None = None
    cote_rang: float | None = None
    nb_partants: int | None = None


@dataclass
class Prediction:
    """Résultat brut du moteur de prédiction."""

    course_id: str
    partant_id: str

    score: float
    confiance: float

    modele: str | None = None
    version: str | None = None

    rang: int | None = None
    probabilite: float | None = None


@dataclass
class MarketValue:
    """Comparaison entre probabilité modèle et marché."""

    cote: float | None = None
    probabilite_modele: float | None = None
    probabilite_marche: float | None = None

    value: float | None = None
    gain_attendu: float | None = None
    rapport_attendu: float | None = None


@dataclass
class RacePrediction:
    """Vue complète d'une prédiction pour une course."""

    race: Race
    partant: Partant
    prediction: Prediction

    market: MarketValue | None = None

    rang_final: int | None = None
    score_final: float | None = None


@dataclass
class GuidePronostic:
    """Structure d'un guide PMUPredict FullMode."""

    version: str
    titre: str
    date_generation: datetime

    sections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers de conversion
# ---------------------------------------------------------------------------

def horse_from_row(row: dict[str, Any]) -> Horse:
    """Construit un Horse depuis une ligne Supabase."""

    return Horse(
        nom=str(row.get("cheval_nom") or "inconnu"),
        age=_float_or_int(row.get("age")),
        sexe=row.get("sexe"),
        poids_kg=_to_float(row.get("poids_kg")),
        gains=_to_float(row.get("gains")),
        musique=row.get("musique"),
        jours_repos=_to_float(row.get("jours_repos")),
        sante_proxy=_to_float(row.get("sante_proxy")),
        est_deferre=_to_bool(row.get("est_deferre")),
        ferrure=row.get("ferrure"),
        oeilleres=row.get("oeilleres"),
    )


def jockey_from_row(row: dict[str, Any]) -> Jockey | None:
    """Construit un Jockey si une identité est disponible."""

    nom = row.get("jockey")
    if not nom:
        return None

    return Jockey(
        nom=str(nom),
        nb_chevaux=_int_or_none(row.get("jockey_nb_chevaux")),
        nb_courses=_int_or_none(row.get("jockey_nb_courses")),
        ce=_to_float(row.get("jockey_ce")),
        taux_victoire=_to_float(row.get("jockey_taux_victoire")),
        taux_top3=_to_float(row.get("jockey_taux_top3")),
        forme=_to_float(row.get("jockey_forme")),
    )


def trainer_from_row(row: dict[str, Any]) -> Trainer | None:
    """Construit un Trainer si une identité est disponible."""

    nom = row.get("entraineur") or row.get("trainer")
    if not nom:
        return None

    return Trainer(
        nom=str(nom),
        nb_chevaux=_int_or_none(row.get("entraineur_nb_chevaux")),
        nb_courses=_int_or_none(row.get("entraineur_nb_courses")),
        cj=_to_float(row.get("entraineur_cj")),
        taux_victoire=_to_float(row.get("entraineur_taux_victoire")),
        taux_top3=_to_float(row.get("entraineur_taux_top3")),
        forme=_to_float(row.get("entraineur_forme")),
    )


def race_from_row(row: dict[str, Any]) -> Race:
    """Construit une Race depuis une ligne Supabase."""

    return Race(
        id=str(row.get("id") or ""),
        discipline=row.get("discipline"),
        distance_m=_to_float(row.get("distance_m")),
        numero=_int_or_none(row.get("numero")),
        libelle=row.get("libelle"),
        allocation=_to_float(row.get("allocation")),
        heure_depart=_to_datetime(row.get("heure_depart")),
        statut=row.get("statut"),
        corde=_int_or_none(row.get("corde")),
        sol=row.get("sol"),
        meteo=row.get("meteo"),
        reunion_id=_string_or_none(row.get("reunion_id")),
        date=_to_date(row.get("date")),
        est_quinte_plus=bool(row.get("est_quinte_plus", False)),
    )


def partant_from_row(row: dict[str, Any]) -> Partant:
    """Construit un Partant depuis une ligne Supabase."""

    horse = horse_from_row(row)

    return Partant(
        id=str(row.get("id") or ""),
        course_id=str(row.get("course_id") or ""),
        cheval=horse,
        numero=_int_or_none(row.get("numero")),
        jockey=jockey_from_row(row),
        entraineur=trainer_from_row(row),
        poids_kg=_to_float(row.get("poids_kg")),
        cote_matin=_to_float(row.get("cote_matin")),
        cote_actuelle=_to_float(row.get("cote_actuelle")),
        est_deferre=_to_bool(row.get("est_deferre")),
        ferrure=row.get("ferrure"),
        oeilleres=row.get("oeilleres"),
        position_precedente=_int_or_none(row.get("prev_rang_1")),
        position_precedente_2=_int_or_none(row.get("prev_rang_2")),
        jours_repos=_to_float(row.get("jours_repos")),
        forme=_to_float(row.get("forme")),
        reussite=_to_float(row.get("reussite")),
        appetence=_to_float(row.get("appetence")),
        score_musique=_to_float(row.get("score_musique")),
        taux_top3_musique=_to_float(row.get("taux_top3_musique")),
        taux_incident_musique=_to_float(row.get("taux_incident_musique")),
        ecart_cote=_to_float(row.get("ecart_cote")),
        cote_rang=_to_float(row.get("cote_rang")),
        nb_partants=_int_or_none(row.get("nb_partants")),
    )


# ---------------------------------------------------------------------------
# Conversion / normalisation
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        value = float(value)
        return value if value == value else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_int(value: Any) -> int | None:
    return _int_or_none(value)


def _string_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "1", "oui", "yes", "y", "deferre", "déferré"}:
            return True

        if normalized in {"false", "0", "non", "no", "n"}:
            return False

    return None


def _to_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
