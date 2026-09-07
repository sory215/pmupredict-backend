"""
GET /api/tipsters

Endpoint public : classement des pronostiqueurs communautaires par
fiabilité (`points`, alimenté par la boucle de feedback de fusion.py).

Query params optionnels :
  ?limit=20   (défaut 50)
  ?type=communaute|presse  (défaut communaute)
"""

import os
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

CACHE_HEADER = "public, s-maxage=300, stale-while-revalidate=600"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        limit = min(int(params.get("limit", ["50"])[0]), 100)
        type_filtre = params.get("type", ["communaute"])[0]

        try:
            res = (
                supabase.table("pronostiqueurs")
                .select("nom, type, points, nb_pronostics, site_source")
                .eq("type", type_filtre)
                .order("points", desc=True)
                .limit(limit)
                .execute()
            )
            self._send_json(200, {"type": type_filtre, "tipsters": res.data}, cache=True)
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status: int, payload: dict, cache: bool = False):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control", CACHE_HEADER)
        self.end_headers()
        self.wfile.write(body)
