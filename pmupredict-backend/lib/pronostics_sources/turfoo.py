from __future__ import annotations

import re
from datetime import date

import requests

from .base import PronosticExterne
from .normalizer import numbers
from .registry import register


BASE_URL = "https://www.turfoo.fr"

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


def extract_race(html: str, url: str = "") -> tuple[int, int, str]:
    match = re.search(
        r"reunion(\d+)-([^/]+)/course(\d+)-",
        html,
        re.I,
    )

    if match:
        return (
            int(match.group(1)),
            int(match.group(3)),
            match.group(2).replace("-", " ").strip().upper(),
        )

    match = re.search(
        r"reunion(\d+)-([^/]+)/course(\d+)-",
        url,
        re.I,
    )

    if match:
        return (
            int(match.group(1)),
            int(match.group(3)),
            match.group(2).replace("-", " ").strip().upper(),
        )

    raise RuntimeError(
        "Impossible d'identifier la réunion, la course et l'hippodrome Turfoo"
    )


def extract_selection(html: str) -> list[int]:
    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html,
        re.I | re.S,
    )

    selection: list[tuple[int, int]] = []

    for row in rows:
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row,
            re.I | re.S,
        )

        if len(cells) < 3:
            continue

        clean = [
            re.sub(r"<[^>]+>", " ", cell)
            for cell in cells
        ]
        clean = [
            re.sub(r"\s+", " ", cell).strip()
            for cell in clean
        ]

        rank_match = re.fullmatch(r"\d{1,2}", clean[0])
        numero_match = re.fullmatch(r"\d{1,2}", clean[1])

        if not rank_match or not numero_match:
            continue

        rank = int(rank_match.group(0))
        numero = int(numero_match.group(0))

        if 1 <= rank <= 8 and numero > 0:
            selection.append((rank, numero))

    selection.sort(key=lambda item: item[0])

    result = numbers(
        [numero for _, numero in selection[:8]]
    )

    if not result:
        raise RuntimeError(
            "Aucune sélection Turfoo détectée"
        )

    return result


@register("turfoo")
def collect_turfoo(
    url: str,
    jour: str | None = None,
) -> list[PronosticExterne]:

    jour = jour or date.today().isoformat()

    html = fetch(url)

    reunion, course, hippodrome_nom = extract_race(html, url)

    classement = extract_selection(html)

    return [
        PronosticExterne(
            source="Turfoo",
            pronostiqueur="Turfoo",
            type_source="presse",
            date=jour,
            reunion=reunion,
            course=course,
            classement=classement,
            commentaire=(
                "Sélection Turfoo : "
                + "-".join(map(str, classement))
            ),
            url=url,
        )
    ]
