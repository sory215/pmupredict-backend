"""Historique métier PMUPredict.

Couche de transposition du contrat historique Predictify :
- forme du cheval ;
- performances sur un hippodrome ;
- historique exploitable par les futures routes API.

Cette couche utilise uniquement les données PMUPredict/Supabase
existantes et ne réutilise aucun endpoint ou secret Predictify.
"""

from __future__ import annotations

from typing import Any

from .db import fetch_all


def load_horse_history(
    horse_name: str,
    *,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retourne les courses terminées connues pour un cheval.

    Le modèle PMUPredict ne possède pas encore d'identifiant cheval
    permanent : l'identité historique est donc actuellement basée
    sur ``partants.cheval_nom``.

    Les résultats sont raccordés par ``arrivees.partant_id``.
    """

    if not horse_name:
        return []

    partants = fetch_all(
        "partants",
        (
            "id,course_id,numero,cheval_nom,jockey,entraineur,"
            "musique,poids_kg,cote_matin,cote_actuelle,est_deferre"
        ),
        cheval_nom__eq=horse_name,
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    if not partants:
        return []

    partant_ids = [p["id"] for p in partants if p.get("id")]
    course_ids = list({
        p["course_id"]
        for p in partants
        if p.get("course_id")
    })

    arrivees = fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        partant_id__in=partant_ids,
    )

    courses = fetch_all(
        "courses",
        (
            "id,reunion_id,numero,libelle,discipline,"
            "heure_depart,statut,distance_m,allocation"
        ),
        id__in=course_ids,
    )

    arrivals_by_partant = {
        a["partant_id"]: a
        for a in arrivees
        if a.get("partant_id")
    }

    courses_by_id = {
        c["id"]: c
        for c in courses
        if c.get("id")
    }

    history: list[dict[str, Any]] = []

    for partant in partants:
        result = arrivals_by_partant.get(partant.get("id"))
        course = courses_by_id.get(partant.get("course_id"))

        # Une course sans arrivée connue ne constitue pas encore
        # une performance historique exploitable.
        if not result or not course:
            continue

        history.append(
            {
                "partant": partant,
                "course": course,
                "position": result.get("position"),
            }
        )

    history.sort(
        key=lambda item: str(
            item["course"].get("heure_depart") or ""
        ),
        reverse=True,
    )

    return history


def load_horse_course_stats(
    horse_name: str,
    hippodrome_id: str,
    *,
    exclude_course_id: str | None = None,
) -> dict[str, Any]:
    """Calcule les statistiques historiques d'un cheval sur un hippodrome.

    Transposition du contrat historique Predictify ``getHorseCourseStats``.
    L'identité du cheval repose actuellement sur ``partants.cheval_nom``.
    """

    history = load_horse_history(
        horse_name,
        exclude_course_id=exclude_course_id,
    )

    if not history or not hippodrome_id:
        return {
            "horse_name": horse_name,
            "hippodrome_id": hippodrome_id,
            "courses": 0,
            "victoires": 0,
            "places": 0,
            "performances": [],
        }

    course_ids = [
        item["course"]["id"]
        for item in history
        if item["course"].get("id")
    ]

    if not course_ids:
        return {
            "horse_name": horse_name,
            "hippodrome_id": hippodrome_id,
            "courses": 0,
            "victoires": 0,
            "places": 0,
            "performances": [],
        }

    courses = fetch_all(
        "courses",
        "id,reunion_id",
        id__in=course_ids,
    )

    reunion_ids = list({
        c["reunion_id"]
        for c in courses
        if c.get("reunion_id")
    })

    reunions = fetch_all(
        "reunions",
        "id,hippodrome_id",
        id__in=reunion_ids,
    )

    allowed_reunions = {
        r["id"]
        for r in reunions
        if r.get("id") and r.get("hippodrome_id") == hippodrome_id
    }

    allowed_courses = {
        c["id"]
        for c in courses
        if c.get("id") and c.get("reunion_id") in allowed_reunions
    }

    performances = [
        item
        for item in history
        if item["course"].get("id") in allowed_courses
    ]

    positions = [
        item["position"]
        for item in performances
        if isinstance(item.get("position"), int)
    ]

    return {
        "horse_name": horse_name,
        "hippodrome_id": hippodrome_id,
        "courses": len(performances),
        "victoires": sum(1 for p in positions if p == 1),
        "places": sum(1 for p in positions if p in (2, 3)),
        "performances": performances,
    }

def load_jockey_history(
    jockey_name: str,
    *,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retourne les courses terminées connues pour un jockey."""

    if not jockey_name:
        return []

    partants = fetch_all(
        "partants",
        (
            "id,course_id,numero,cheval_nom,jockey,entraineur,"
            "musique,poids_kg,cote_matin,cote_actuelle,est_deferre"
        ),
        jockey__eq=jockey_name,
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    if not partants:
        return []

    partant_ids = [p["id"] for p in partants if p.get("id")]
    course_ids = list({
        p["course_id"]
        for p in partants
        if p.get("course_id")
    })

    arrivees = fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        partant_id__in=partant_ids,
    )

    courses = fetch_all(
        "courses",
        (
            "id,reunion_id,numero,libelle,discipline,"
            "heure_depart,statut,distance_m,allocation"
        ),
        id__in=course_ids,
    )

    arrivals_by_partant = {
        a["partant_id"]: a
        for a in arrivees
        if a.get("partant_id")
    }

    courses_by_id = {
        c["id"]: c
        for c in courses
        if c.get("id")
    }

    history = []

    for partant in partants:
        result = arrivals_by_partant.get(partant.get("id"))
        course = courses_by_id.get(partant.get("course_id"))

        if not result or not course:
            continue

        history.append(
            {
                "partant": partant,
                "course": course,
                "position": result.get("position"),
            }
        )

    history.sort(
        key=lambda item: str(
            item["course"].get("heure_depart") or ""
        ),
        reverse=True,
    )

    return history

def load_jockey_stats(
    jockey_name: str,
    *,
    exclude_course_id: str | None = None,
) -> dict[str, Any]:
    """Calcule les statistiques historiques d'un jockey."""

    history = load_jockey_history(
        jockey_name,
        exclude_course_id=exclude_course_id,
    )

    positions = [
        item["position"]
        for item in history
        if isinstance(item.get("position"), int)
    ]

    nb_courses = len(positions)
    victoires = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p in (1, 2, 3))

    chevaux = {
        item["partant"].get("cheval_nom")
        for item in history
        if item["partant"].get("cheval_nom")
    }

    return {
        "jockey_name": jockey_name,
        "nb_courses": nb_courses,
        "nb_chevaux": len(chevaux),
        "victoires": victoires,
        "top3": top3,
        "taux_victoire": victoires / nb_courses if nb_courses else 0.0,
        "taux_top3": top3 / nb_courses if nb_courses else 0.0,
        "forme": (
            sum(
                max(0.0, 1.0 - (p - 1) / 10.0)
                for p in positions[:5]
            ) / min(len(positions), 5)
            if positions else 0.0
        ),
        "courses": history,
    }

def load_trainer_history(
    trainer_name: str,
    *,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retourne les courses terminées connues pour un entraîneur."""

    if not trainer_name:
        return []

    partants = fetch_all(
        "partants",
        (
            "id,course_id,numero,cheval_nom,jockey,entraineur,"
            "musique,poids_kg,cote_matin,cote_actuelle,est_deferre"
        ),
        entraineur__eq=trainer_name,
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    if not partants:
        return []

    partant_ids = [p["id"] for p in partants if p.get("id")]
    course_ids = list({
        p["course_id"]
        for p in partants
        if p.get("course_id")
    })

    arrivees = fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        partant_id__in=partant_ids,
    )

    courses = fetch_all(
        "courses",
        (
            "id,reunion_id,numero,libelle,discipline,"
            "heure_depart,statut,distance_m,allocation"
        ),
        id__in=course_ids,
    )

    arrivals_by_partant = {
        a["partant_id"]: a
        for a in arrivees
        if a.get("partant_id")
    }

    courses_by_id = {
        c["id"]: c
        for c in courses
        if c.get("id")
    }

    history = []

    for partant in partants:
        result = arrivals_by_partant.get(partant.get("id"))
        course = courses_by_id.get(partant.get("course_id"))

        if not result or not course:
            continue

        history.append(
            {
                "partant": partant,
                "course": course,
                "position": result.get("position"),
            }
        )

    history.sort(
        key=lambda item: str(
            item["course"].get("heure_depart") or ""
        ),
        reverse=True,
    )

    return history

def load_trainer_stats(
    trainer_name: str,
    *,
    exclude_course_id: str | None = None,
) -> dict[str, Any]:
    """Calcule les statistiques historiques d'un entraîneur."""

    history = load_trainer_history(
        trainer_name,
        exclude_course_id=exclude_course_id,
    )

    positions = [
        item["position"]
        for item in history
        if isinstance(item.get("position"), int)
    ]

    nb_courses = len(positions)
    victoires = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p in (1, 2, 3))

    chevaux = {
        item["partant"].get("cheval_nom")
        for item in history
        if item["partant"].get("cheval_nom")
    }

    return {
        "trainer_name": trainer_name,
        "nb_courses": nb_courses,
        "nb_chevaux": len(chevaux),
        "victoires": victoires,
        "top3": top3,
        "taux_victoire": victoires / nb_courses if nb_courses else 0.0,
        "taux_top3": top3 / nb_courses if nb_courses else 0.0,
        "forme": (
            sum(
                max(0.0, 1.0 - (p - 1) / 10.0)
                for p in positions[:5]
            ) / min(len(positions), 5)
            if positions else 0.0
        ),
        "courses": history,
    }

def load_jockey_standings(
    *,
    limit: int = 50,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Construit un classement des jockeys à partir des résultats connus."""

    partants = fetch_all(
        "partants",
        "id,course_id,cheval_nom,jockey",
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    partants = [
        p for p in partants
        if p.get("jockey")
    ]

    if not partants:
        return []

    partant_ids = [p["id"] for p in partants if p.get("id")]

    arrivees = fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        partant_id__in=partant_ids,
    )

    arrivals_by_partant = {
        a["partant_id"]: a
        for a in arrivees
        if a.get("partant_id")
    }

    stats: dict[str, dict[str, Any]] = {}

    for partant in partants:
        result = arrivals_by_partant.get(partant.get("id"))
        position = result.get("position") if result else None

        if not isinstance(position, int):
            continue

        name = partant["jockey"]

        if name not in stats:
            stats[name] = {
                "jockey_name": name,
                "nb_courses": 0,
                "nb_chevaux": set(),
                "victoires": 0,
                "top3": 0,
            }

        row = stats[name]
        row["nb_courses"] += 1

        if partant.get("cheval_nom"):
            row["nb_chevaux"].add(partant["cheval_nom"])

        if position == 1:
            row["victoires"] += 1

        if position in (1, 2, 3):
            row["top3"] += 1

    standings = []

    for row in stats.values():
        courses = row["nb_courses"]
        victoires = row["victoires"]
        top3 = row["top3"]

        standings.append({
            "jockey_name": row["jockey_name"],
            "nb_courses": courses,
            "nb_chevaux": len(row["nb_chevaux"]),
            "victoires": victoires,
            "top3": top3,
            "taux_victoire": victoires / courses if courses else 0.0,
            "taux_top3": top3 / courses if courses else 0.0,
        })

    standings.sort(
        key=lambda row: (
            row["victoires"],
            row["top3"],
            row["taux_top3"],
        ),
        reverse=True,
    )

    return standings[:max(1, int(limit))]

def load_trainer_standings(
    *,
    limit: int = 50,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Construit un classement des entraîneurs à partir des résultats connus."""

    partants = fetch_all(
        "partants",
        "id,course_id,cheval_nom,entraineur",
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    partants = [
        p for p in partants
        if p.get("entraineur")
    ]

    if not partants:
        return []

    partant_ids = [p["id"] for p in partants if p.get("id")]

    arrivees = fetch_all(
        "arrivees",
        "course_id,position,partant_id",
        partant_id__in=partant_ids,
    )

    arrivals_by_partant = {
        a["partant_id"]: a
        for a in arrivees
        if a.get("partant_id")
    }

    stats: dict[str, dict[str, Any]] = {}

    for partant in partants:
        result = arrivals_by_partant.get(partant.get("id"))
        position = result.get("position") if result else None

        if not isinstance(position, int):
            continue

        name = partant["entraineur"]

        if name not in stats:
            stats[name] = {
                "trainer_name": name,
                "nb_courses": 0,
                "nb_chevaux": set(),
                "victoires": 0,
                "top3": 0,
            }

        row = stats[name]
        row["nb_courses"] += 1

        if partant.get("cheval_nom"):
            row["nb_chevaux"].add(partant["cheval_nom"])

        if position == 1:
            row["victoires"] += 1

        if position in (1, 2, 3):
            row["top3"] += 1

    standings = []

    for row in stats.values():
        courses = row["nb_courses"]
        victoires = row["victoires"]
        top3 = row["top3"]

        standings.append({
            "trainer_name": row["trainer_name"],
            "nb_courses": courses,
            "nb_chevaux": len(row["nb_chevaux"]),
            "victoires": victoires,
            "top3": top3,
            "taux_victoire": victoires / courses if courses else 0.0,
            "taux_top3": top3 / courses if courses else 0.0,
        })

    standings.sort(
        key=lambda row: (
            row["victoires"],
            row["top3"],
            row["taux_top3"],
        ),
        reverse=True,
    )

    return standings[:max(1, int(limit))]

def load_trainer_horses(
    trainer_name: str,
    *,
    exclude_course_id: str | None = None,
) -> list[dict[str, Any]]:
    """Retourne les chevaux connus associés à un entraîneur."""

    if not trainer_name:
        return []

    partants = fetch_all(
        "partants",
        (
            "id,course_id,numero,cheval_nom,jockey,entraineur,"
            "musique,poids_kg,cote_matin,cote_actuelle,est_deferre"
        ),
        entraineur__eq=trainer_name,
    )

    if exclude_course_id:
        partants = [
            p for p in partants
            if p.get("course_id") != exclude_course_id
        ]

    horses: dict[str, dict[str, Any]] = {}

    for partant in partants:
        name = (partant.get("cheval_nom") or "").strip()

        if not name:
            continue

        horses[name] = {
            "horse_name": name,
            "jockey": partant.get("jockey"),
            "entraineur": partant.get("entraineur"),
            "course_id": partant.get("course_id"),
            "numero": partant.get("numero"),
            "musique": partant.get("musique"),
            "cote_actuelle": partant.get("cote_actuelle"),
        }

    return list(horses.values())
