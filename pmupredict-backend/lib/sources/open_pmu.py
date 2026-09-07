from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

import requests

from .base import ResultSource

log = logging.getLogger("sources.open_pmu")

RESULTS_API_URL = os.getenv(
    "RESULTS_API_URL",
    "https://open-pmu-api.vercel.app/api/arrivees",
)

UA = {
    "User-Agent": os.getenv(
        "HTTP_USER_AGENT",
        "pmupredict/1.0 (+https://pmupredict.app)",
    )
}


class OpenPMUSource(ResultSource):
    name = "open_pmu"

    def __init__(self, url: str | None = None):
        self.url = url or RESULTS_API_URL

    def fetch(self, jour: str) -> list[dict[str, Any]]:
        """
        Récupère les arrivées historiques depuis Open PMU API.

        jour attendu : YYYY-MM-DD
        """

        date_api = datetime.strptime(jour, "%Y-%m-%d").strftime("%d/%m/%Y")

        response = requests.get(
            self.url,
            params={"date": date_api},
            headers=UA,
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return []

        message = data.get("message", [])

        if isinstance(message, dict):
            message = list(message.values())

        if not isinstance(message, list):
            return []

        courses: list[dict[str, Any]] = []

        for item in message:
            if not isinstance(item, dict):
                continue

            rc = str(item.get("r/c", "")).upper().replace(" ", "")
            match = re.match(r"R(\d+)/C(\d+)", rc)

            if not match:
                continue

            reunion = int(match.group(1))
            course = int(match.group(2))

            arrivee = item.get("arrivee") or []

            if not isinstance(arrivee, (list, tuple)):
                continue

            positions = []

            for position, numero in enumerate(arrivee, 1):
                try:
                    numero = int(numero)
                except (TypeError, ValueError):
                    continue

                positions.append(
                    {
                        "position": position,
                        "numero": numero,
                    }
                )

            courses.append(
                {
                    "source": self.name,
                    "date": jour,
                    "reunion": reunion,
                    "course": course,
                    "arrivee": positions,
                    "raw": item,
                }
            )

        log.info(
            "Open PMU: %s course(s) récupérée(s) pour %s",
            len(courses),
            jour,
        )

        return courses
