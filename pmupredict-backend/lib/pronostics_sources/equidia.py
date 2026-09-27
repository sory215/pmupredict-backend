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
        "(KHTML, like Gecko) "
        "Chrome/138 Mobile Safari/537.36"
    )
}


def fetch(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def extract_race(html: str) -> tuple[int, int]:
    # Priorité au contexte éditorial de l'article.
    # La page peut embarquer d'autres articles contenant d'autres R/C
    # dans ses données JSON internes.
    match = re.search(
        r"Prix\s+Grandlieu\s*\([^)]*R(\d+)C(\d+)",
        html,
        re.I | re.S,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    # Structure de la course directement présente dans la page.
    match = re.search(
        r'"num_reunion":\s*(\d+).*?"num_course_pmu":\s*(\d+)',
        html,
        re.I | re.S,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(
        r"/courses/\d{4}-\d{2}-\d{2}/R(\d+)/C(\d+)",
        html,
        re.I,
    )
    if match:
        return int(match.group(1)), int(match.group(2))

    raise RuntimeError(
        "Impossible d'identifier la réunion et la course Equidia"
    )


def extract_feux(html: str) -> tuple[list[int], list[int], list[int]]:
    def extract(pattern: str, label: str) -> list[int]:
        match = re.search(pattern, html, re.I | re.S)
        if not match:
            raise RuntimeError(
                f"{label} Equidia introuvable"
            )
        return numbers(match.group(1))

    vert = extract(
        r"Feu\s+vert\s*:\s*.*?(\d+)\s*-\s*[^<]+",
        "Feu vert",
    )
    orange = extract(
        r"Feu\s+orange\s*:\s*.*?(\d+)\s*-\s*[^<]+",
        "Feu orange",
    )
    rouge = extract(
        r"Feu\s+rouge\s*:\s*.*?(\d+)\s*-\s*[^<]+",
        "Feu rouge",
    )

    return vert, orange, rouge


@register("equidia")
def collect_equidia(
    url: str,
    jour: str | None = None,
) -> list[PronosticExterne]:
    jour = jour or date.today().isoformat()

    html = fetch(url)
    reunion, course = extract_race(html)
    vert, orange, rouge = extract_feux(html)

    classement = []
    for numero in vert + orange + rouge:
        if numero not in classement:
            classement.append(numero)

    return [
        PronosticExterne(
            source="Equidia",
            pronostiqueur="Manuela Jollivet",
            type_source="presse",
            date=jour,
            reunion=reunion,
            course=course,
            classement=classement,
            base=vert,
            chances=orange,
            outsiders=rouge,
            commentaire=(
                "Feu vert: "
                + "-".join(map(str, vert))
                + " | Feu orange: "
                + "-".join(map(str, orange))
                + " | Feu rouge: "
                + "-".join(map(str, rouge))
            ),
            url=url,
        )
    ]
