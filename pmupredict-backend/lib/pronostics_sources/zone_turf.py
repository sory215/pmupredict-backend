from __future__ import annotations

import re
from datetime import date

import requests

from .base import PronosticExterne
from .normalizer import numbers
from .registry import register

BASE_URL = "https://www.zone-turf.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
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


def extract_race(html: str) -> tuple[int, int]:
    match = re.search(
        r"<strong>\s*R(\d+)\s*C(\d+)\s+[^<]+</strong>",
        html,
        re.I,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    raise RuntimeError(
        "Impossible d'identifier la réunion et la course Zone-Turf"
    )
def extract_selection(html: str) -> list[int]:
    tables = re.findall(
        r'<table class="fl">.*?</table>',
        html,
        re.I | re.S,
    )

    if not tables:
        raise RuntimeError(
            "Table de sélection Zone-Turf introuvable"
        )

    table = tables[0]

    numbers_found = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>\s*(?:<strong>)?\s*(\d+)",
        table,
        re.I | re.S,
    )

    result = numbers(numbers_found[:8])

    if not result:
        raise RuntimeError(
            "Aucune sélection Zone-Turf détectée"
        )

    return result


@register("zone_turf")
def collect_zone_turf(
    url: str,
    jour: str | None = None,
) -> list[PronosticExterne]:
    jour = jour or date.today().isoformat()

    html = fetch(url)

    reunion, course = extract_race(html)
    classement = extract_selection(html)

    return [
        PronosticExterne(
            source="Zone-Turf",
            pronostiqueur="Zone-Turf",
            type_source="presse",
            date=jour,
            reunion=reunion,
            course=course,
            classement=classement,
            commentaire=(
                "Sélection Zone-Turf : "
                + "-".join(map(str, classement))
            ),
            url=url,
        )
    ]
