"""Chargement des données nécessaires à la couche IA indépendante."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.data.db import fetch_all


def load_course_ai_data(course_id: str) -> dict[str, Any]:
    """Charge une course et son historique utile à l'analyse IA.

    Cette fonction ne charge aucun modèle ML et n'écrit aucune prédiction.
    """

    courses = fetch_all(
        "courses",
        "id,reunion_id,numero,libelle,discipline,heure_depart,statut,"
        "distance_m,allocation,etat_terrain,valeur_penetrometre",
        id__eq=course_id,
        page_size=1000,
    )

    if not courses:
        raise ValueError(f"Course introuvable : {course_id}")

    course = courses[0]

    partants = fetch_all(
        "partants",
        "id,course_id,numero,cheval_nom,cote_matin,cote_actuelle,"
        "poids_kg,musique,jockey,entraineur,est_deferre,gains_participant",
        course_id__eq=course_id,
        page_size=1000,
    )

    if not partants:
        return {
            "course": course,
            "partants": [],
            "historique": pd.DataFrame(),
            "arrivees": [],
        }

    names = list(
        {
            p["cheval_nom"]
            for p in partants
            if p.get("cheval_nom")
        }
    )

    historique = fetch_all(
        "partants",
        "id,course_id,numero,cheval_nom,cote_matin,cote_actuelle,"
        "poids_kg,musique,jockey,entraineur,est_deferre,gains_participant",
        cheval_nom__in=names,
        page_size=1000,
    )

    course_ids = list(
        {
            str(p["course_id"])
            for p in historique
            if p.get("course_id")
        }
    )

    courses_historiques = (
        fetch_all(
            "courses",
            "id,reunion_id,discipline,heure_depart,statut,distance_m,allocation,"
            "etat_terrain,valeur_penetrometre",
            id__in=course_ids,
            page_size=1000,
        )
        if course_ids
        else []
    )

    arrivees = (
        fetch_all(
            "arrivees",
            "course_id,position,partant_id",
            course_id__in=course_ids,
            page_size=1000,
        )
        if course_ids
        else []
    )

    return {
        "course": course,
        "partants": partants,
        "historique": pd.DataFrame(historique),
        "courses_historiques": pd.DataFrame(courses_historiques),
        "arrivees": arrivees,
    }
