from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("sources.equidia")

EQUIDIA_URL = os.getenv(
    "EQUIDIA_PRONOSTICS_URL",
    "https://www.equidia.fr/pronostics",
)

UA = {
    "User-Agent": os.getenv(
        "HTTP_USER_AGENT",
        "pmupredict/1.0 (+https://pmupredict.app)",
    )
}

RC_PATTERN = re.compile(r"R(\d+)C(\d+)")


def _parse_numbers(text: str) -> list[int]:
    """Extrait une liste de numéros de partants depuis un texte du type '9 - 3 - 4'."""
    return [int(n) for n in re.findall(r"\d+", text)]


def _parse_ticket(ticket) -> dict[str, Any] | None:
    """Parse un bloc .ticket-prono en dict {reunion, course, hippodrome, pronostic}."""
    full_text = ticket.get_text(" | ", strip=True)

    match = RC_PATTERN.search(full_text)
    if not match:
        return None
    reunion = int(match.group(1))
    course = int(match.group(2))

    header_parts = full_text.split(" | ")
    hippodrome = None
    for i, part in enumerate(header_parts):
        if RC_PATTERN.fullmatch(part.strip()):
            if i > 0:
                hippodrome = header_parts[i - 1].strip()
            break
    if not hippodrome:
        return None

    def _section(label: str) -> list[int]:
        idx = full_text.find(f"{label} :")
        if idx == -1:
            idx = full_text.find(f"{label}:")
            if idx == -1:
                return []
        end_markers = [
            " | Bases", " | Outsiders", " | Belles chances",
            " | Délaissés", " | Arrivée définitive", " | Voir la page course",
        ]
        start = idx + len(label) + 2
        rest = full_text[start:]
        end = len(rest)
        for marker in end_markers:
            pos = rest.find(marker)
            if pos != -1 and pos < end:
                end = pos
        return _parse_numbers(rest[:end])

    bases = _section("Bases")
    belles_chances = _section("Belles chances")
    outsiders = _section("Outsiders")

    classement = bases + belles_chances + outsiders
    if not classement:
        return None

    commentaire_el = ticket.find(class_="quinte-prono--analysis") or ticket.find("p")
    commentaire = commentaire_el.get_text(" ", strip=True) if commentaire_el else ""

    return {
        "hippodrome_nom": hippodrome,
        "reunion": reunion,
        "course": course,
        "pronostic": classement,
        "commentaire": commentaire[:500],
    }


def fetch_equidia_pronostics(url: str | None = None) -> dict[str, Any]:
    """
    Récupère les pronostics de la rédaction Equidia pour le jour courant.
    """
    target_url = url or EQUIDIA_URL
    response = requests.get(target_url, headers=UA, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tickets = soup.find_all(class_="ticket-prono")

    courses: list[dict[str, Any]] = []
    for ticket in tickets:
        try:
            parsed = _parse_ticket(ticket)
        except Exception as exc:
            log.warning("Erreur parsing ticket Equidia: %s", exc)
            continue
        if parsed:
            courses.append(parsed)

    log.info("Equidia: %s pronostic(s) récupéré(s)", len(courses))
    return {"courses": courses}


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_equidia_pronostics(), ensure_ascii=False, indent=2))
