from __future__ import annotations

import json
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from .base import PronosticExterne
from .normalizer import numbers
from .registry import register


BASE_URL = "https://www.turf-pronostics.com"
PROGRAMME_URL = f"{BASE_URL}/programme-du-jour/"
COMMUNITY_URL = (
    f"{BASE_URL}/community/les-pronostics-des-internautes/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138 Mobile Safari/537.36"
    )
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self.links.append(urljoin(BASE_URL, href))


def fetch(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def find_quinte_course() -> tuple[int, int, str]:
    html = fetch(PROGRAMME_URL)

    cards = re.findall(
        r'<div[^>]*class=["\'][^"\']*tppmu-course-card[^"\']*["\'][^>]*>'
        r'.*?'
        r'</div>\s*</div>\s*</div>',
        html,
        re.I | re.S,
    )

    for card in cards:
        if not re.search(
            r'data-tags=["\'][^"\']*\bquinte\b[^"\']*["\']',
            card,
            re.I,
        ):
            continue

        ref = re.search(
            r'tppmu-course-ref[^>]*>\s*R(\d+)C(\d+)',
            card,
            re.I,
        )

        if ref:
            hippodrome = re.search(
                r"tppmu-course-ref[^>]*>\s*R\d+C\d+\s*(?:&#8211;|&#x2013;|–|-)\s*([^<]+)",
                card,
                re.I,
            )
            nom_hippodrome = (
                re.sub(r"\s+", " ", hippodrome.group(1)).strip()
                if hippodrome
                else ""
            )
            return (
                int(ref.group(1)),
                int(ref.group(2)),
                nom_hippodrome,
            )

    raise RuntimeError(
        "Impossible d'identifier le Quinté du jour "
        "sur le programme Turf-Pronostics"
    )

def community_topic_urls() -> list[str]:
    html = fetch(COMMUNITY_URL)

    parser = LinkParser()
    parser.feed(html)

    result = []
    for url in parser.links:
        if (
            "/community/les-pronostics-des-internautes/"
            in url
            and url.rstrip("/") != COMMUNITY_URL.rstrip("/")
        ):
            if url not in result:
                result.append(url)

    return result


def jsonld_postings(html: str) -> list[dict]:
    matches = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        html,
        re.I | re.S,
    )

    result = []

    for raw in matches:
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue

        if (
            isinstance(data, dict)
            and data.get("@type") == "DiscussionForumPosting"
        ):
            result.append(data)

    return result


@register("turf_pronostics")
def collect_turf_pronostics(
    jour: str | None = None,
) -> list[PronosticExterne]:
    jour = jour or date.today().isoformat()

    reunion, course, hippodrome_nom = find_quinte_course()

    result = []
    seen = set()

    for url in community_topic_urls():
        try:
            html = fetch(url)
            postings = jsonld_postings(html)

            for posting in postings:
                published = str(posting.get("datePublished", ""))

                if not published.startswith(jour):
                    continue

                headline = str(posting.get("headline", ""))
                text = str(posting.get("text", ""))

                if not re.search(
                    r"quint[ée]|\bq\+?\b",
                    headline,
                    re.I,
                ):
                    continue

                author = posting.get("author", {})
                if isinstance(author, dict):
                    pronostiqueur = str(
                        author.get("name", "Inconnu")
                    )
                else:
                    pronostiqueur = "Inconnu"

                classement = numbers(text)

                if not classement:
                    continue

                posting_url = str(
                    posting.get("url") or url
                )

                key = (
                    posting_url,
                    pronostiqueur,
                    tuple(classement),
                )

                if key in seen:
                    continue

                seen.add(key)

                result.append(
                    PronosticExterne(
                        source="Turf-Pronostics",
                        pronostiqueur=pronostiqueur,
                        type_source="communaute",
                        date=jour,
                        reunion=reunion,
                        course=course,
                        hippodrome_nom=hippodrome_nom,
                        classement=classement,
                        commentaire=text,
                        url=str(
                            posting.get("url") or url
                        ),
                    )
                )

        except Exception:
            continue

    return result
