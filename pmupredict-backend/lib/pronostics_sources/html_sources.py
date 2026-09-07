from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import PronosticExterne
from .normalizer import numbers

log = logging.getLogger("pronostics.html_sources")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


def fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def soup_from_url(url: str) -> BeautifulSoup:
    html = fetch_html(url)
    return BeautifulSoup(html, "html.parser")


def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_numbers(text: str) -> list[int]:
    if not text:
        return []

    found = re.findall(r"\b\d{1,2}\b", text)
    return numbers(found)


def make_pronostic(
    source: str,
    url: str,
    jour: str,
    reunion: int,
    course: int,
    classement: list[int],
    base: list[int] | None = None,
    chances: list[int] | None = None,
    outsiders: list[int] | None = None,
    commentaire: str = "",
    pronostiqueur: str | None = None,
) -> PronosticExterne:

    return PronosticExterne(
        source=source,
        pronostiqueur=pronostiqueur or source,
        type_source="presse",
        date=jour,
        reunion=reunion,
        course=course,
        classement=classement,
        base=base or [],
        chances=chances or [],
        outsiders=outsiders or [],
        commentaire=commentaire,
        url=url,
    )


def extract_reunion_course(text: str) -> tuple[int, int]:
    """
    Cherche des formes du type :
    R1C5
    R1 - C5
    Réunion 1 Course 5
    """

    patterns = [
        r"\bR\s*(\d+)\s*C\s*(\d+)\b",
        r"\bR\s*(\d+)\s*[-:/]\s*C\s*(\d+)\b",
        r"\bRéunion\s*(\d+).*?\bCourse\s*(\d+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1)), int(match.group(2))

    return 0, 0


def find_course_links(
    html: str,
    base_url: str,
    pattern: str,
) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    result = []

    for link in soup.select("a[href]"):
        href = link.get("href", "")

        if re.search(pattern, href, re.I):
            absolute = urljoin(base_url, href)

            if absolute not in result:
                result.append(absolute)

    return result
