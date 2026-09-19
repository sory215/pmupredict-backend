from __future__ import annotations

import requests

from .base import PronosticExterne
from .normalizer import numbers


def collect_json_source(
    src: dict,
    jour: str,
) -> list[PronosticExterne]:

    url = src.get("url")
    if not url:
        return []

    headers = {
        "User-Agent": src.get(
            "user_agent",
            "pmupredict/1.0"
        )
    }

    response = requests.get(
        url,
        params={"date": jour},
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        return []

    courses = data.get("courses", [])

    if not isinstance(courses, list):
        return []

    result = []

    for c in courses:
        if not isinstance(c, dict):
            continue

        classement = numbers(
            c.get("pronostic", c.get("classement", []))
        )

        base = numbers(c.get("base"))
        chances = numbers(c.get("chances"))
        outsiders = numbers(c.get("outsiders"))

        result.append(
            PronosticExterne(
                source=str(src.get("nom", "Source")),
                pronostiqueur=str(
                    c.get(
                        "pronostiqueur",
                        src.get("nom", "Source")
                    )
                ),
                type_source=str(
                    src.get("type", "presse")
                ),
                date=jour,
                reunion=int(c.get("reunion", 0)),
                course=int(c.get("course", 0)),
                classement=classement,
                base=base,
                chances=chances,
                outsiders=outsiders,
                commentaire=str(
                    c.get("commentaire", "")
                ),
                url=url,
            )
        )

    return result
