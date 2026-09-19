from __future__ import annotations

import os
import json
import logging

from .authorized import collect_json_source
from .base import PronosticExterne

log = logging.getLogger("pronostics.collector")


def load_sources() -> list[dict]:
    raw = os.getenv("PRONOSTICS_SOURCES_JSON", "[]")

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


def collect_external_pronostics(
    jour: str,
) -> list[PronosticExterne]:

    result: list[PronosticExterne] = []

    for src in load_sources():
        try:
            items = collect_json_source(src, jour)

            log.info(
                "Source %s : %d pronostics récupérés",
                src.get("nom", "Source"),
                len(items),
            )

            result.extend(items)

        except Exception as exc:
            log.exception(
                "Erreur source %s : %s",
                src.get("nom", "Source"),
                exc,
            )

    return result
