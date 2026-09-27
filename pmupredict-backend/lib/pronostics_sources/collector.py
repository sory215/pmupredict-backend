from __future__ import annotations

import os
import json
import logging

from .authorized import collect_json_source
from .base import PronosticExterne
from .registry import get

# Import des collecteurs spécialisés.
# Ces imports déclenchent leurs décorateurs @register(...).
from . import turf_pronostics
from . import canalturf
from . import zone_turf
from . import turfoo
from . import rue_des_joueurs
from . import equidia
from . import geny

log = logging.getLogger("pronostics.collector")


def load_sources() -> list[dict]:
    raw = os.getenv("PRONOSTICS_SOURCES_JSON", "").strip()

    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "PRONOSTICS_SOURCES_JSON doit être un JSON valide"
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            "PRONOSTICS_SOURCES_JSON doit contenir une liste"
        )

    return [
        src
        for src in data
        if isinstance(src, dict) and src.get("url")
    ]


def load_registered_sources() -> list[dict]:
    raw = os.getenv("PRONOSTICS_HTML_SOURCES_JSON", "").strip()

    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "PRONOSTICS_HTML_SOURCES_JSON doit être un JSON valide"
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            "PRONOSTICS_HTML_SOURCES_JSON doit contenir une liste"
        )

    return [
        src
        for src in data
        if isinstance(src, dict) and src.get("name")
    ]


def collect_registered_source(
    src: dict,
    jour: str,
) -> list[PronosticExterne]:
    name = str(src["name"])
    collector = get(name)

    if collector is None:
        raise RuntimeError(
            f"Collecteur enregistré introuvable : {name}"
        )

    if name == "turf_pronostics":
        return collector(jour=jour)

    url = src.get("url")
    if not url:
        raise RuntimeError(
            f"URL obligatoire pour le collecteur : {name}"
        )

    if name == "geny":
        experts = src.get("experts")
        return collector(
            url=url,
            experts=experts,
            jour=jour,
        )

    return collector(
        url=url,
        jour=jour,
    )


def collect_external_pronostics(
    jour: str,
) -> list[PronosticExterne]:
    result: list[PronosticExterne] = []

    # ---------------------------------------------------------
    # Ancien système JSON : conservé
    # ---------------------------------------------------------
    for src in load_sources():
        try:
            items = collect_json_source(src, jour)

            log.info(
                "Source JSON %s : %d pronostics récupérés",
                src.get("nom", "Source"),
                len(items),
            )

            result.extend(items)

        except Exception as exc:
            log.exception(
                "Erreur source JSON %s : %s",
                src.get("nom", "Source"),
                exc,
            )

    # ---------------------------------------------------------
    # Nouveau système de collecteurs spécialisés
    # ---------------------------------------------------------
    for src in load_registered_sources():
        try:
            items = collect_registered_source(src, jour)

            log.info(
                "Source spécialisée %s : %d pronostics récupérés",
                src.get("name", "Source"),
                len(items),
            )

            result.extend(items)

        except Exception as exc:
            log.exception(
                "Erreur source spécialisée %s : %s",
                src.get("name", "Source"),
                exc,
            )

    return result
