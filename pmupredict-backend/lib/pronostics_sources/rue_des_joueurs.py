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
        "Impossible d'identifier la réunion et la course Rue des Joueurs"
    )


def extract_selection(html: str) -> list[int]:
    blocks = re.findall(
        r'<div class="rdj-jersey".*?</div>\s*</div>',
        html,
        re.I | re.S,
    )

    selection = []

    for block in blocks:
        num = re.search(
            r'class="rdj-num">\s*(\d+)',
            block,
            re.I,
        )

        name = re.search(
            r'<h3>\s*(.*?)\s*</h3>',
            block,
            re.I | re.S,
        )

        if not num or not name:
            continue

        numero = int(num.group(1))
        cheval = re.sub(
            r"\s+",
            " ",
            re.sub(r"<[^>]+>", " ", name.group(1)),
        ).strip()

        selection.append((numero, cheval))

    result = numbers(
        [numero for numero, _ in selection]
    )

    if not result:
        raise RuntimeError(
            "Aucune sélection Rue des Joueurs détectée"
        )

    return result


@register("rue_des_joueurs_sarah")
def collect_rue_des_joueurs(
    url: str,
    jour: str | None = None,
) -> list[PronosticExterne]:

    jour = jour or date.today().isoformat()

    html = fetch(url)

    reunion, course = extract_race(url, html)

    classement = extract_selection(html)

    return [
        PronosticExterne(
            source="Rue des Joueurs",
            pronostiqueur="Sarah",
            type_source="presse",
            date=jour,
            reunion=reunion,
            course=course,
            classement=classement,
            commentaire=(
                "Sélection Sarah / Rue des Joueurs : "
                + "-".join(map(str, classement))
            ),
            url=url,
        )
    ]
