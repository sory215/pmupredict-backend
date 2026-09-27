from __future__ import annotations

import os
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

from supabase import create_client, Client

from lib.pronostics_sources.registry import SOURCES


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
)

CACHE_HEADER = "public, s-maxage=300, stale-while-revalidate=600"


class handler(BaseHTTPRequestHandler):

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", CACHE_HEADER)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        try:
            limit = min(int(params.get("limit", ["50"])[0]), 100)
        except ValueError:
            limit = 50

        type_filtre = params.get("type", [""])[0].strip().lower()

        sources = []

        for source in SOURCES.values():
            if not source.actif:
                continue

            if type_filtre and source.type_source != type_filtre:
                continue

            sources.append({
                "id": source.key,
                "nom": source.nom,
                "type": source.type_source,
                "points": 0,
                "nb_pronostics": 0,
                "site_source": "",
                "description": source.description,
                "priorite": source.priorite,
                "independant": source.independant,
            })

        sources = sources[:limit]

        try:
            result = (
                supabase
                .table("pronostiqueurs")
                .select("id,nom,type,points,nb_pronostics,site_source")
                .execute()
            )

            stats = {
                (row.get("nom"), row.get("type")): row
                for row in (result.data or [])
            }

            for source in sources:
                row = stats.get((source["nom"], source["type"]))

                if not row:
                    continue

                source["points"] = row.get("points") or 0
                source["site_source"] = row.get("site_source") or ""

                try:
                    count_result = (
                        supabase
                        .table("pronostics_externes")
                        .select("partant_id", count="exact")
                        .eq("pronostiqueur_id", row["id"])
                        .execute()
                    )
                    source["nb_pronostics"] = count_result.count or 0
                except Exception:
                    source["nb_pronostics"] = row.get("nb_pronostics") or 0

        except Exception:
            pass

        self._send_json(
            200,
            {
                "type": type_filtre or "all",
                "tipsters": sources,
            },
        )
