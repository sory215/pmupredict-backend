from __future__ import annotations

import logging
from typing import Any

from .base import ResultSource
from .open_pmu import OpenPMUSource

log = logging.getLogger("sources.manager")


class SourceManager:
    """
    Orchestre toutes les sources de données PMU.
    """

    def __init__(self, sources: list[ResultSource] | None = None):
        self.sources = sources or [
            OpenPMUSource(),
        ]

    def fetch_all(self, jour: str) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}

        for source in self.sources:
            try:
                if not source.available():
                    log.warning(
                        "Source %s indisponible",
                        source.name,
                    )
                    continue

                data = source.fetch(jour)

                if data:
                    results[source.name] = data

            except Exception as exc:
                log.warning(
                    "Source %s indisponible: %s",
                    source.name,
                    exc,
                )

        return results

    def merge_results(
        self,
        jour: str,
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        """
        Fusionne les résultats des différentes sources.

        Clé :
            (réunion, course)

        Valeur :
            arrivée normalisée.
        """

        merged: dict[tuple[int, int], list[dict[str, Any]]] = {}

        all_results = self.fetch_all(jour)

        for source_name, courses in all_results.items():
            for course in courses:
                key = (
                    int(course["reunion"]),
                    int(course["course"]),
                )

                arrivee = course.get("arrivee") or []

                if not arrivee:
                    continue

                if key not in merged:
                    merged[key] = arrivee
                else:
                    # Pour l'instant, on conserve la première
                    # source valide rencontrée.
                    log.debug(
                        "Résultat déjà présent pour R%d/C%d "
                        "(source=%s)",
                        key[0],
                        key[1],
                        source_name,
                    )

        return merged
