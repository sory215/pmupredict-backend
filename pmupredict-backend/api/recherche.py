from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from supabase import create_client
from lib.pdf_extraction import extract_pdf_pages
from lib.pdf_race_parser import identify_race_from_pdf_text, resolve_course_id


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


    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0") or "0")

        if content_length <= 0:
            return self._send_json(
                400,
                {"error": "PDF vide ou absent"},
            )

        if "application/pdf" not in content_type:
            return self._send_json(
                415,
                {"error": "Content-Type application/pdf obligatoire"},
            )

        try:
            pdf_bytes = self.rfile.read(content_length)

            if not pdf_bytes.startswith(b"%PDF"):
                return self._send_json(
                    400,
                    {"error": "Le fichier envoyé n'est pas un PDF valide"},
                )

            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False,
            ) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = Path(tmp.name)

            try:
                pages = extract_pdf_pages(tmp_path)
                pdf_text = "\n\n".join(
                    page.get("text", "")
                    for page in pages
                ).strip()

                identity = identify_race_from_pdf_text(pdf_text)
                race_date = identity.get("date")
                course_numero = identity.get("course_numero")

                course_id = resolve_course_id(
                    supabase,
                    race_date,
                    course_numero,
                )

                pdf_data = {
                    "filename": self.headers.get(
                        "X-PDF-Filename",
                        "document.pdf",
                    ),
                    "page_count": len(pages),
                    "identity": identity,
                    "course_id": course_id,
                    "pages": pages,
                }

                if not course_id:
                    return self._send_json(
                        404,
                        {
                            "error": "course introuvable dans Supabase",
                            "pdf": pdf_data,
                        },
                    )

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
                        "pdf": pdf_data,
                        "course": course[0],
                        "prediction_ia": ia or [],
                        "tipsters": list(tipsters.values()),
                    },
                )

            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as exc:
            return self._send_json(
                500,
                {"error": str(exc)},
            )

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        pdf_path = params.get("pdf_path", [""])[0].strip()
        pdf_data = None

        if pdf_path:
            try:
                pages = extract_pdf_pages(pdf_path)
                pdf_text = "\n\n".join(
                    page.get("text", "")
                    for page in pages
                ).strip()

                identity = identify_race_from_pdf_text(pdf_text)
                race_date = identity.get("date")
                course_numero = identity.get("course_numero")

                course_id = resolve_course_id(
                    supabase,
                    race_date,
                    course_numero,
                )

                pdf_data = {
                    "path": pdf_path,
                    "pages": pages,
                    "page_count": len(pages),
                    "identity": identity,
                    "course_id": course_id,
                }

                if not course_id:
                    return self._send_json(
                        404,
                        {
                            "error": "course introuvable dans Supabase",
                            "pdf": pdf_data,
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
        else:
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
                    "pdf": pdf_data,
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
