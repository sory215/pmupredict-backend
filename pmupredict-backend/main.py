import os
import re
import sys
from datetime import datetime
import zoneinfo
from fastapi import FastAPI, HTTPException
from fastapi import File, UploadFile
from datetime import datetime, timezone
from lib.db import supabase as _pdf_supabase
from lib.parse_programme import ProgrammeExtrait, ProgrammePdfError, parse_programme_pdf
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


# ===== Ingestion PDF de programme (upload manuel depuis le chat) =====
_PDF_SOURCE_MANUAL_UPLOAD = "manual_pdf_upload"


def _pdf_upsert_programme(programme: ProgrammeExtrait) -> dict:
    hippo_res = (
        _pdf_supabase.table("hippodromes")
        .select("id")
        .ilike("nom", programme.hippodrome_nom)
        .limit(1)
        .execute()
    )
    if not hippo_res.data:
        raise HTTPException(
            404,
            f"Hippodrome '{programme.hippodrome_nom}' introuvable dans la table "
            "hippodromes — vérifie l'orthographe ou crée-le d'abord.",
        )
    hippodrome_id = hippo_res.data[0]["id"]

    reunion_res = (
        _pdf_supabase.table("reunions")
        .upsert(
            {"date": programme.date, "numero": programme.reunion_numero, "hippodrome_id": hippodrome_id},
            on_conflict="date,numero,hippodrome_id",
        )
        .execute()
    )
    reunion_id = reunion_res.data[0]["id"]

    courses_written = 0
    partants_written = 0

    for course in programme.courses:
        course_res = (
            _pdf_supabase.table("courses")
            .upsert(
                {
                    "reunion_id": reunion_id,
                    "numero": course.numero,
                    "libelle": course.libelle,
                    "discipline": course.discipline,
                    "distance_m": course.distance_m,
                    "allocation": course.allocation_euros,
                    "heure_depart": course.heure_depart,
                    "statut": "programmee",
                },
                on_conflict="reunion_id,numero",
            )
            .execute()
        )
        course_id = course_res.data[0]["id"]
        courses_written += 1

        for partant in course.partants:
            _pdf_supabase.table("partants").upsert(
                {
                    "course_id": course_id,
                    "numero": partant.numero,
                    "cheval_nom": partant.cheval_nom,
                    "jockey": partant.driver_jockey,
                    "driver": partant.driver_jockey,
                    "entraineur": partant.entraineur,
                    "proprietaire": partant.proprietaire,
                    "age": partant.age,
                    "cote_matin": partant.cote_matin,
                    "poids_kg": partant.poids_kg,
                },
                on_conflict="course_id,numero",
            ).execute()
            partants_written += 1

    return {"reunion_id": reunion_id, "courses_written": courses_written, "partants_written": partants_written}


def _pdf_log_ingestion_run(status: str, result: dict, error: str | None = None):
    _pdf_supabase.table("historique_ingestion_runs").insert(
        {
            "source": _PDF_SOURCE_MANUAL_UPLOAD,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "documents_seen": 1,
            "documents_ok": 1 if status == "success" else 0,
            "documents_failed": 0 if status == "success" else 1,
            "courses_written": result.get("courses_written", 0),
            "partants_written": result.get("partants_written", 0),
            "errors": {"message": error} if error else {},
        }
    ).execute()


@app.post("/api/ingest-pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Seuls les fichiers PDF sont acceptés pour l'instant.")

    file_bytes = await file.read()

    try:
        programme = parse_programme_pdf(file_bytes)
        result = _pdf_upsert_programme(programme)
        _pdf_log_ingestion_run("completed", result)

        return {
            "message": (
                f"Programme importé : {programme.hippodrome_nom} du {programme.date} — "
                f"{result['courses_written']} course(s), {result['partants_written']} partant(s)."
            ),
            **result,
        }

    except ProgrammePdfError as e:
        _pdf_log_ingestion_run("failed", {}, error=str(e))
        raise HTTPException(422, f"Format de PDF non reconnu : {e}")
    except HTTPException as e:
        _pdf_log_ingestion_run("failed", {}, error=str(e.detail))
        raise
    except Exception as e:
        _pdf_log_ingestion_run("failed", {}, error=str(e))
        raise HTTPException(500, f"Erreur inattendue lors de l'import : {e}")
