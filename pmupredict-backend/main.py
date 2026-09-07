import os
import re
import sys
from datetime import datetime
import zoneinfo
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Ajout du sous-dossier lib au chemin Python pour importer tes scripts
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from lib.db import supabase

app = FastAPI(
    title="PMUPredict API",
    description="Backend API pour les prédictions PMU",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PMUPredict Backend",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    missing_vars = [
        var for var in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
        if not os.getenv(var)
    ]
    if missing_vars:
        return {
            "status": "degraded",
            "warning": f"Variables d'environnement manquantes : {', '.join(missing_vars)}"
        }
    return {"status": "healthy", "database": "configured"}


# Nouvel endpoint pour déclencher les prédictions
@app.get("/api/predict")
def run_prediction():
    try:
        from core.predict import run_prediction as predict_run

        result = predict_run()

        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur de prédiction : {str(e)}"
        )


def parse_date_jour():
    tz = zoneinfo.ZoneInfo("Africa/Abidjan")
    return datetime.now(tz).date().isoformat()


def resoudre_course(question: str, jour: str):
    q = question.lower()

    reunions = supabase.table("reunions").select(
        "id,numero,date,hippodromes(nom,code)"
    ).eq("date", jour).execute().data or []

    if not reunions:
        return None, "Aucune réunion programmée pour cette date."

    reunion_ids = [r["id"] for r in reunions]
    courses = supabase.table("courses").select(
        "id,reunion_id,numero,libelle,heure_depart,statut"
    ).in_("reunion_id", reunion_ids).execute().data or []

    reunion_by_id = {r["id"]: r for r in reunions}

    # Format "R1 C2" / "r1c2" / "reunion 1 course 2"
    m = re.search(r"r(?:éunion)?\s*(\d+)\D+c(?:ourse)?\s*(\d+)", q)
    if m:
        num_r, num_c = int(m.group(1)), int(m.group(2))
        for c in courses:
            reunion = reunion_by_id.get(c["reunion_id"])
            if reunion and reunion["numero"] == num_r and c["numero"] == num_c:
                return c, None
        return None, f"Aucune course trouvée pour R{num_r}C{num_c} aujourd'hui."

    # Format heure "14h" / "14h30" / "14:00"
    m = re.search(r"(\d{1,2})\s*h\s*(\d{2})?|(\d{1,2}):(\d{2})", q)
    if m:
        heure = m.group(1) or m.group(3)
        minute = m.group(2) or m.group(4) or "00"
        cible = f"{int(heure):02d}:{minute}"
        for c in courses:
            if c.get("heure_depart") and c["heure_depart"].startswith(cible):
                return c, None
        return None, f"Aucune course trouvée à {cible} aujourd'hui."

    # Recherche par nom de course ou d'hippodrome
    for c in courses:
        if c["libelle"] and c["libelle"].lower() in q:
            return c, None
    for r in reunions:
        hippo_nom = (r.get("hippodromes") or {}).get("nom", "").lower()
        if hippo_nom and hippo_nom in q:
            r_courses = [c for c in courses if c["reunion_id"] == r["id"]]
            if r_courses:
                return r_courses[0], None

    return None, "Je n'ai pas identifié de course précise dans la question. Essaie par exemple 'R1 C2', 'la course de 14h', ou le nom de l'hippodrome."


@app.get("/api/chat")
def chat_endpoint(q: str, date_str: str = None):
    try:
        jour = date_str or parse_date_jour()
        course, erreur = resoudre_course(q, jour)

        if erreur:
            return {"reponse": erreur, "course": None, "pronostics": []}

        pronostics = supabase.table("pronostics_fusion").select(
            "score_ia,score_presse,score_communaute,score_final,rang_final,"
            "probabilite_estimee,cote_estimee,partants(numero,cheval_nom,jockey)"
        ).eq("course_id", course["id"]).order("rang_final").execute().data or []

        if not pronostics:
            arrivees = supabase.table("arrivees").select(
                "position,partant_id"
            ).eq("course_id", course["id"]).order("position").execute().data or []

            if not arrivees:
                return {
                    "reponse": f"Aucun pronostic ni résultat disponible pour {course['libelle']} pour le moment.",
                    "course": course,
                    "pronostics": [],
                }

            partant_ids = [a["partant_id"] for a in arrivees]
            partants_data = supabase.table("partants").select(
                "id,numero,cheval_nom,jockey"
            ).in_("id", partant_ids).execute().data or []
            partant_by_id = {p["id"]: p for p in partants_data}

            gagnant = partant_by_id.get(arrivees[0]["partant_id"], {})
            reponse = (
                f"{course['libelle']} est déjà terminée. Le vainqueur a été "
                f"{gagnant.get('cheval_nom', '?')}, monté par {gagnant.get('jockey', '?')}."
            )

            return {
                "reponse": reponse,
                "course": course,
                "resultats": [
                    {**partant_by_id.get(a["partant_id"], {}), "position": a["position"]}
                    for a in arrivees
                ],
            }

        favori = pronostics[0]
        favori_nom = (favori.get("partants") or {}).get("cheval_nom", "?")

        ecarts = [
            abs((p.get("score_ia") or 0) - (p.get("score_communaute") or 0))
            for p in pronostics
        ]
        ecart_max = max(ecarts) if ecarts else 0
        tendance = (
            "Les sources sont globalement d'accord sur ce favori."
            if ecart_max < 0.15
            else "Il y a un désaccord notable entre l'IA et le public sur au moins un cheval — surveille les value bets."
        )

        reponse = (
            f"Pour {course['libelle']}, le favori du modèle est {favori_nom} "
            f"(score fusion {favori.get('score_final', 0):.0%}). {tendance}"
        )

        return {
            "reponse": reponse,
            "course": course,
            "pronostics": [
                {**(p.get("partants") or {}), **{k: p.get(k) for k in (
                    "score_ia", "score_presse", "score_communaute",
                    "score_final", "rang_final", "probabilite_estimee", "cote_estimee"
                )}}
                for p in pronostics
            ],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur assistant : {str(e)}")
