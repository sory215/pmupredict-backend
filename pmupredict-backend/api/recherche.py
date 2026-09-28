from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from supabase import create_client
from lib.pdf_extraction import extract_pdf_pages


supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_ANON_KEY"],
)


class handler(BaseHTTPRequestHandler):

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        pdf_path = params.get("pdf_path", [""])[0].strip()
        if pdf_path:
            try:
                pages = extract_pdf_pages(pdf_path)
                return self._send_json(
                    200,
                    {
                        "pdf": {
                            "path": pdf_path,
                            "pages": pages,
                            "page_count": len(pages),
                        }
                    },
                )
            except FileNotFoundError as exc:
                return self._send_json(
                    404,
                    {"error": str(exc)},
                )
            except Exception as exc:
                return self._send_json(
                    500,
                    {"error": str(exc)},
                )

        course_id = params.get("course_id", [""])[0].strip()

        if not course_id:
            return self._send_json(
                400,
                {"error": "course_id ou pdf_path obligatoire"},
            )

        try:
            course = (
                supabase
                .table("courses")
                .select(
                    "id,numero,libelle,discipline,"
                    "heure_depart,statut"
                )
                .eq("id", course_id)
                .limit(1)
                .execute()
                .data
            )

            if not course:
                return self._send_json(
                    404,
                    {"error": "course introuvable"},
                )

            ia = (
                supabase
                .table("pronostics_fusion")
                .select(
                    "score_ia,score_presse,score_communaute,"
                    "score_final,rang_final,probabilite_estimee,"
                    "cote_estimee,"
                    "partants(numero,cheval_nom,jockey,cote_actuelle)"
                )
                .eq("course_id", course_id)
                .order("rang_final")
                .execute()
                .data
            )

            externes = (
                supabase
                .table("pronostics_externes")
                .select(
                    "partant_id,rang_propose,commentaire,source,"
                    "pronostiqueurs(id,nom,type,site_source),"
                    "partants(numero,cheval_nom,jockey,cote_actuelle)"
                )
                .eq("course_id", course_id)
                .order("rang_propose")
                .execute()
                .data
            )

            tipsters = {}

            for row in externes or []:
                tip = row.get("pronostiqueurs") or {}
                partant = row.get("partants") or {}

                key = (
                    tip.get("id")
                    or tip.get("nom")
                    or "source-inconnue"
                )

                if key not in tipsters:
                    tipsters[key] = {
                        "nom": tip.get("nom"),
                        "type": tip.get("type"),
                        "site_source": tip.get("site_source"),
                        "source": row.get("source"),
                        "pronostics": [],
                        "commentaires": [],
                    }

                tipsters[key]["pronostics"].append({
                    "numero": partant.get("numero"),
                    "cheval_nom": partant.get("cheval_nom"),
                    "rang": row.get("rang_propose"),
                    "jockey": partant.get("jockey"),
                    "cote": partant.get("cote_actuelle"),
                })

                commentaire = row.get("commentaire")
                if commentaire:
                    tipsters[key]["commentaires"].append(
                        commentaire
                    )

            return self._send_json(
                200,
                {
                    "course": course[0],
                    "prediction_ia": ia or [],
                    "tipsters": list(tipsters.values()),
                },
            )

        except Exception as exc:
            return self._send_json(
                500,
                {"error": str(exc)},
            )
