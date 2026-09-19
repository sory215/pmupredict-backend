"""Helpers Supabase partagés par les jobs PMUPredict."""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
from typing import Any


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def _request(
    table: str,
    columns: str = "*",
    *,
    start: int = 0,
    page_size: int = 1000,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    params = {
        "select": columns,
        "offset": str(start),
        "limit": str(page_size),
    }

    for name, value in (filters or {}).items():
        if name.endswith("__in"):
            params[name[:-4]] = "in.(" + ",".join(str(v) for v in value) + ")"
        elif name.endswith("__eq"):
            params[name[:-4]] = "eq." + str(value)
        else:
            params[name] = "eq." + str(value)

    query = urllib.parse.urlencode(params, safe="(),")

    url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_all(
    table: str,
    columns: str = "*",
    *,
    page_size: int = 1000,
    **filters: Any,
) -> list[dict]:
    """Récupère toutes les lignes Supabase par pages.

    PostgREST/Supabase peut limiter une réponse à 1000 lignes.
    On utilise donc toujours des pages <= 1000 et on continue
    tant qu'une page complète est retournée.
    """

    rows: list[dict] = []
    start = 0

    # Supabase/PostgREST peut plafonner la réponse à 1000 lignes.
    effective_page_size = min(int(page_size), 1000)

    while True:
        batch = _request(
            table,
            columns,
            start=start,
            page_size=effective_page_size,
            filters=filters,
        )

        rows.extend(batch)

        if len(batch) < effective_page_size:
            break

        start += effective_page_size

    return rows
