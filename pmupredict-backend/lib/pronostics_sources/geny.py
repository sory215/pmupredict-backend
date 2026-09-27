from __future__ import annotations

import re
from datetime import date

import requests

from .base import PronosticExterne
from .normalizer import numbers
from .registry import register


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 "
        "Chrome/138 Mobile Safari/537.36"
    )
}


def fetch(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def extract_race(url: str, html: str) -> tuple[int, int]:
    match = re.search(
        r"/R(\d+)/C(\d+)/",
        url,
        re.I,
    )

    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(
        r"\bR(\d+)C(\d+)\b",
        html,
        re.I,
    )

    if match:
        return int(match.group(1)), int(match.group(2))

    raise RuntimeError(
        "Impossible d'identifier la réunion et la course Geny"
    )


def extract_expert(
    html: str,
    expert: str,
) -> list[int]:

    positions = list(
        re.finditer(
            re.escape(expert),
            html,
            re.I,
        )
    )

    for position in positions:
        bloc = html[
            max(0, position.start() - 500):
            position.start() + 7000
        ]

        # On cherche les 8 numéros affichés juste après
        # le nom de l'expert dans sa carte de pronostic.
        match = re.search(
            re.escape(expert)
            + r".{0,2500}?"
            + r'class="[^"]*text-sm[^"]*font-semibold[^"]*"'
            + r'>(\d+)</div>',
            bloc,
            re.I | re.S,
        )

        if not match:
            continue

        tail = bloc[match.start():]

        values = re.findall(
            r'class="[^"]*text-sm[^"]*font-semibold[^"]*"'
            r'>\s*(\d{1,2})\s*</div>',
            tail,
            re.I | re.S,
        )

        result = numbers(values[:8])

        if len(result) >= 3:
            return result[:8]

    raise RuntimeError(
        f"Aucune sélection détectée pour {expert}"
    )


@register("geny")
def collect_geny(
    url: str,
    experts: list[str] | None = None,
    jour: str | None = None,
) -> list[PronosticExterne]:

    jour = jour or date.today().isoformat()

    experts = experts or [
        "Sébastien Longubardo",
        "Hubert Debruyne",
    ]

    html = fetch(url)

    reunion, course = extract_race(url, html)

    results = []

    for expert in experts:
        classement = extract_expert(
            html,
            expert,
        )

        results.append(
            PronosticExterne(
                source="Geny",
                pronostiqueur=expert,
                type_source="presse",
                date=jour,
                reunion=reunion,
                course=course,
                classement=classement,
                commentaire=(
                    f"Sélection {expert} / Geny : "
                    + "-".join(map(str, classement))
                ),
                url=url,
            )
        )

    return results
