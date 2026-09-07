"""
GET /api/recommendations

Endpoint authentifié : le frontend doit envoyer le JWT Supabase de
l'utilisateur connecté dans le header Authorization.
  Authorization: Bearer <jwt_utilisateur>

Logique :
  1. Vérifie le JWT et récupère l'utilisateur (auth.uid())
  2. Charge son profil (préférences : disciplines, hippodromes favoris)
  3. Filtre les courses du jour selon ces préférences
  4. Trie par score_final (déjà calculé par le module de fusion)
  5. Renvoie les meilleurs choix avec une justification textuelle simple
"""

import os
import json
from datetime import date
from http.server import BaseHTTPRequestHandler

from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        jwt = self._extraire_jwt()
        if not jwt:
            self._send_json(401, {"error": "authentification requise"})
            return

        # Client Supabase "au nom de l'utilisateur" : le JWT porte son
        # identité, donc les policies RLS s'appliquent normalement
        # (l'utilisateur ne peut lire que son propre profil).
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        supabase.postgrest.auth(jwt)

        try:
            user = supabase.auth.get_user(jwt)
            if not user or not user.user:
                self._send_json(401, {"error": "jwt invalide"})
                return
            user_id = user.user.id

            recommandations = self._construire_recommandations(supabase, user_id)
            self._send_json(200, {"recommandations": recommandations})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _construire_recommandations(self, supabase: Client, user_id: str):
        profil = supabase.table("profils").select("preferences").eq("id", user_id).limit(1).execute()
        preferences = (profil.data[0]["preferences"] if profil.data else {}) or {}
        disciplines = preferences.get("disciplines", [])
        hippodromes_favoris = preferences.get("hippodromes_favoris", [])

        jour = date.today().isoformat()

        query = (
            supabase.table("courses")
            .select(
                "id, numero, libelle, discipline, heure_depart, "
                "reunions(date, hippodromes(nom, code)), "
                "pronostics_fusion(score_final, rang_final, partants(numero, cheval_nom))"
            )
        )
        if disciplines:
            query = query.in_("discipline", disciplines)

        courses = query.execute().data

        resultats = []
        for c in courses:
            reunion = c.get("reunions") or {}
            if reunion.get("date") != jour:
                continue

            hippodrome = reunion.get("hippodromes") or {}
            if hippodromes_favoris and hippodrome.get("code") not in hippodromes_favoris:
                continue

            fusion = sorted(
                c.get("pronostics_fusion") or [], key=lambda r: r.get("rang_final") or 999
            )
            if not fusion:
                continue

            favori = fusion[0]
            partant = favori.get("partants") or {}

            resultats.append({
                "course_id": c["id"],
                "hippodrome": hippodrome.get("nom"),
                "libelle": c.get("libelle"),
                "heure_depart": c.get("heure_depart"),
                "favori_recommande": partant.get("cheval_nom"),
                "score_final": favori.get("score_final"),
                "justification": self._justification(hippodrome, c),
            })

        resultats.sort(key=lambda r: r["score_final"] or 0, reverse=True)
        return resultats[:10]

    def _justification(self, hippodrome: dict, course: dict) -> str:
        elements = []
        if hippodrome.get("nom"):
            elements.append(f"un de vos hippodromes suivis ({hippodrome['nom']})")
        if course.get("discipline"):
            elements.append(f"discipline préférée ({course['discipline']})")
        return "Recommandé car : " + ", ".join(elements) if elements else "Score de fusion élevé aujourd'hui"

    def _extraire_jwt(self):
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[len("Bearer "):]
        return None

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
