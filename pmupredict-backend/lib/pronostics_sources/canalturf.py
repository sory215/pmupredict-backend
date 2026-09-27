from __future__ import annotations

import re
from datetime import date

import requests

from .base import PronosticExterne
from .normalizer import numbers
from .registry import register


BASE_URL = "https://www.canalturf.com"

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


def extract_section(html: str, title: str) -> list[int]:
    pattern = (
        rf"<th[^>]*>\s*{re.escape(title)}\s*</th>"
        rf".*?</table>"
    )

    match = re.search(
        pattern,
        html,
        re.I | re.S,
    )

    if not match:
        return []

    return numbers(
        re.findall(
            r"<td[^>]*>\s*(\d+)\s*</td>",
            match.group(0),
            re.I,
        )
    )


def extract_race(html: str) -> tuple[int, int]:
    match = re.search(
        r"R[ée]union\s+(\d+)\s+Course\s+(\d+)",
        html,
        re.I,
    )
    if match:
        return int(match.group(1)), int(match.group(2))
    raise RuntimeError(
        "Impossible d'identifier la réunion et la course Canalturf"
    )
def extract_journalist(html: str) -> str:
    match = re.search(
        r"Par\s+([^<]+)",
        html,
        re.I,
    )

    if match:
        return re.sub(
            r"\s+",
            " ",
            match.group(1),
        ).strip()

    return "Nicolas Labourasse"


def build_url(jour: str, reunion: int, course: int) -> str:
    # Canalturf utilise actuellement une URL propre à chaque course.
    # Le numéro interne de course doit donc être résolu par la page
    # de programme avant utilisation de ce constructeur.
    raise RuntimeError(
        "URL Canalturf non résolue automatiquement pour "
        f"R{reunion}C{course} du {jour}"
    )


@register("canalturf_nicolas")
def collect_canalturf(
    url: str,
    jour: str | None = None,
) -> list[PronosticExterne]:
    jour = jour or date.today().isoformat()

    html = fetch(url)

    reunion, course = extract_race(html)

    base = extract_section(html, "BASE")
    chances = extract_section(
        html,
        "CHANCES REGULIERES",
    )
    outsiders = extract_section(
        html,
        "OUTSIDERS",
    )

    classement = []
    for groupe in (base, chances, outsiders):
        for numero in groupe:
            if numero not in classement:
                classement.append(numero)

    if not classement:
        raise RuntimeError(
            "Aucun pronostic Canalturf détecté"
        )

    pronostiqueur = extract_journalist(html)

    return [
        PronosticExterne(
            source="Canalturf",
            pronostiqueur=pronostiqueur,
            type_source="presse",
            date=jour,
            reunion=reunion,
            course=course,
            classement=classement,
            base=base,
            chances=chances,
            outsiders=outsiders,
            commentaire=(
                "Sélection Canalturf : "
                f"base={base}; "
                f"chances={chances}; "
                f"outsiders={outsiders}"
            ),
            url=url,
        )
    ]
