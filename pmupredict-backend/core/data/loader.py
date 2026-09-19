"""
Loader centralisé PMUPredict.

Responsabilités :
- récupérer les données Supabase avec pagination ;
- transformer les lignes SQL en objets du domaine ;
- conserver les données brutes nécessaires au moteur ML ;
- éviter toute fuite temporelle dans l'historique.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .db import fetch_all
from .schemas import (
    Horse,
    Jockey,
    Trainer,
    Race,
    Partant,
    horse_from_row,
    jockey_from_row,
    trainer_from_row,
    race_from_row,
    partant_from_row,
)


# ---------------------------------------------------------------------------
# Chargement brut Supabase
# ---------------------------------------------------------------------------

def load_courses(page_size: int = 1000) -> list[dict[str, Any]]:
    """Charge toutes les courses."""

    return fetch_all(
        "courses",
        "id,reunion_id,numero,libelle,discipline,heure_depart,"
        "statut,distance_m,allocation",
        page_size=page_size,
    )


def load_partants(
    course_ids: list[str] | None = None,
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    """Charge les partants, éventuellement limités à certaines courses."""

    columns = (
        "id,course_id,numero,cheval_nom,cote_matin,cote_actuelle,"
        "poids_kg,musique,jockey,est_deferre"
    )

    if course_ids:
        return fetch_all(
            "partants",
            columns,
            page_size=page_size,
            course_id__in=course_ids,
        )

    return fetch_all("partants", columns, page_size=page_size)


def load_arrivees(page_size: int = 1000) -> list[dict[str, Any]]:
    """Charge les arrivées historiques."""

    return fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        page_size=page_size,
    )


def load_reunions(page_size: int = 1000) -> list[dict[str, Any]]:
    """Charge les réunions."""

    return fetch_all(
        "reunions",
        "id,numero,date",
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Conversion en objets métier
# ---------------------------------------------------------------------------

def course_to_race(row: dict[str, Any]) -> Race:
    """Transforme une ligne courses en Race."""

    return race_from_row(row)


def partant_to_domain(row: dict[str, Any]) -> Partant:
    """Transforme une ligne partants en Partant."""

    return partant_from_row(row)


def horse_from_partant(row: dict[str, Any]) -> Horse:
    """Extrait le cheval depuis une ligne partants."""

    return horse_from_row(row)


def jockey_from_partant(row: dict[str, Any]) -> Jockey | None:
    """Extrait le jockey depuis une ligne partants."""

    return jockey_from_row(row)


def trainer_from_partant(row: dict[str, Any]) -> Trainer | None:
    """Extrait l'entraîneur lorsqu'il est disponible."""

    return trainer_from_row(row)


# ---------------------------------------------------------------------------
# Chargement d'une course complète
# ---------------------------------------------------------------------------

def load_course_complete(course_id: str) -> dict[str, Any]:
    """
    Charge une course et ses partants.

    Retour :
        {
            "race": Race,
            "partants": list[Partant],
            "raw_race": dict,
            "raw_partants": list[dict]
        }
    """

    courses = fetch_all(
        "courses",
        "id,reunion_id,numero,libelle,discipline,heure_depart,"
        "statut,distance_m,allocation",
        page_size=1000,
        id__eq=course_id,
    )

    if not courses:
        raise ValueError(f"Course introuvable : {course_id}")

    race_row = courses[0]

    partant_rows = load_partants([course_id])

    return {
        "race": course_to_race(race_row),
        "partants": [
            partant_to_domain(row)
            for row in partant_rows
        ],
        "raw_race": race_row,
        "raw_partants": partant_rows,
    }


# ---------------------------------------------------------------------------
# Historique pour le moteur ML
# ---------------------------------------------------------------------------

def load_training_dataset() -> pd.DataFrame:
    """
    Construit le DataFrame historique utilisé par l'entraînement.

    Important :
    on ne calcule aucune feature ici.
    Le feature engineering reste dans core/data/features/.
    """

    partants = load_partants()
    arrivees = load_arrivees()
    courses = load_courses()

    if not partants or not arrivees or not courses:
        return pd.DataFrame()

    ps = pd.DataFrame(partants)
    ar = pd.DataFrame(arrivees)
    co = pd.DataFrame(courses)

    if ps.empty or ar.empty or co.empty:
        return pd.DataFrame()

    # Arrivée associée au partant.
    df = ps.merge(
        ar,
        left_on="id",
        right_on="partant_id",
        how="inner",
        suffixes=("", "_arr"),
    )

    # Informations course.
    df = df.merge(
        co,
        left_on="course_id",
        right_on="id",
        how="left",
        suffixes=("", "_course"),
    )

    if "position" in df.columns:
        df["position"] = pd.to_numeric(
            df["position"],
            errors="coerce",
        )

        df = df[df["position"].notna()].copy()

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Données du jour
# ---------------------------------------------------------------------------

def load_today_courses(jour: str) -> list[dict[str, Any]]:
    """Retourne les courses correspondant à une date donnée."""

    courses = load_courses()

    if not courses:
        return []

    result = []

    for course in courses:
        heure = str(course.get("heure_depart") or "")

        if heure.startswith(jour):
            result.append(course)

    return result


def load_today_partants(jour: str) -> pd.DataFrame:
    """Retourne les partants des courses du jour."""

    courses = load_today_courses(jour)

    if not courses:
        return pd.DataFrame()

    ids = [
        str(course["id"])
        for course in courses
        if course.get("id") is not None
    ]

    if not ids:
        return pd.DataFrame()

    partants = load_partants(ids)

    if not partants:
        return pd.DataFrame()

    return pd.DataFrame(partants)


# ---------------------------------------------------------------------------
# Contrôles simples
# ---------------------------------------------------------------------------

def validate_training_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Retourne un résumé de sécurité du dataset."""

    if df.empty:
        return {
            "ok": False,
            "nb_lignes": 0,
            "nb_courses": 0,
            "colonnes": [],
        }

    return {
        "ok": True,
        "nb_lignes": int(len(df)),
        "nb_courses": int(
            df["course_id"].nunique()
            if "course_id" in df.columns
            else 0
        ),
        "colonnes": list(df.columns),
        "positions_valides": bool(
            "position" in df.columns
            and df["position"].notna().all()
        ),
    }
