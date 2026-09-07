"""Helpers Supabase partagés par les jobs PMUPredict."""
from __future__ import annotations
import os
from typing import Any
from supabase import Client, create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def fetch_all(table: str, columns: str = "*", *, page_size: int = 1000, **filters: Any) -> list[dict]:
    """Récupère toutes les lignes par pages pour éviter la limite implicite de 1000 lignes."""
    page_size = min(max(1, page_size), 1000)

    rows: list[dict] = []
    start = 0
    while True:
        q = supabase.table(table).select(columns)
        for name, value in filters.items():
            if name.endswith("__in"):
                q = q.in_(name[:-4], value)
            elif name.endswith("__eq"):
                q = q.eq(name[:-4], value)
            else:
                q = q.eq(name, value)
        batch = q.range(start, start + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows
