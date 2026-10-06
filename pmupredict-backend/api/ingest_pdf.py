"""
Endpoint d'ingestion manuelle de programme PDF (upload depuis le chat).

Contrairement au pipeline automatique (api/cron/ingest.py, qui tape l'API
officielle), celui-ci sert de filet de sécurité : un utilisateur peut uploader
un PDF de programme (France Galop, LONAB, LONACI, ou autre) quand la source
automatique ne couvre pas un hippodrome ou une réunion.

Pipeline :
  1. Extraction du texte brut du PDF (pdfplumber, 2 colonnes comme pour les résultats)
  2. Structuration du texte en JSON via l'IA (les formats variant trop entre
     sources pour un regex rigide comme parse_results_v2.py)
  3. Validation du JSON renvoyé (garde-fou contre une hallucination du modèle)
  4. Upsert dans reunions / courses / partants (clés naturelles pour éviter les doublons)
  5. Log dans historique_ingestion_runs, cohérent avec le pipeline automatique
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from lib.db import supabase

# TODO: remplacer par l'import réel de ton client LLM utilisé dans main.py
# (ex. `from lib.llm import call_llm` ou l'équivalent déjà en place pour /api/chat)
from lib.llm import call_llm  # noqa: à adapter

app = FastAPI()

SOURCE_MANUAL_UPLOAD = "manual_pdf_upload"


# ---------- Schéma de validation ----------

class PartantExtrait(BaseModel):
    numero: int
    cheval_nom: str
    jockey: Optional[str] = None
    entraineur: Optional[str] = None
    cote_matin: Optional[float] = None


class CourseExtraite(BaseModel):
    numero: int
    libelle: Optional[str] = None
    discipline: Optional[str] = None
    distance_m: Optional[int] = None
    heure_depart: Optional[str] = None  # ISO 8601 si présent dans le PDF
    partants: list[PartantExtrait]


class ProgrammeExtrait(BaseModel):
    hippodrome_nom: str
    date: str  # YYYY-MM-DD
    reunion_numero: int
    courses: list[CourseExtraite]


# ---------- Extraction PDF ----------

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extrait le texte en respectant la mise en page à 2 colonnes, comme pdf_extract_columns.py."""
    text_parts = []
    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            width, height = page.width, page.height
            left = page.crop((0, 0, width / 2, height)).extract_text() or ""
            right = page.crop((width / 2, 0, width, height)).extract_text() or ""
            text_parts.append(left)
            text_parts.append(right)
    return "\n".join(text_parts)


# ---------- Structuration via IA ----------

EXTRACTION_PROMPT = """Tu reçois le texte brut d'un PDF de programme de courses hippiques.
Extrais UNIQUEMENT les informations suivantes, au format JSON strict, sans texte autour :

{{
  "hippodrome_nom": "...",
  "date": "YYYY-MM-DD",
  "reunion_numero": 1,
  "courses": [
    {{
      "numero": 1,
      "libelle": "...",
      "discipline": "trot" | "plat" | "obstacle",
      "distance_m": 2100,
      "heure_depart": "2026-09-06T14:30:00" | null,
      "partants": [
        {{"numero": 1, "cheval_nom": "...", "jockey": "...", "entraineur": "...", "cote_matin": 3.5}}
      ]
    }}
  ]
}}

Si une information est absente du texte, mets null plutôt que d'inventer une valeur.

TEXTE DU PDF :
{pdf_text}
"""


def structure_programme(pdf_text: str) -> ProgrammeExtrait:
    # Tronque si trop long pour éviter de dépasser le contexte du modèle
    truncated = pdf_text[:15000]
    raw_response = call_llm(EXTRACTION_PROMPT.format(pdf_text=truncated))

    # Le modèle peut entourer le JSON de ```json ... ``` malgré la consigne
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_response.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise HTTPException(422, f"L'IA n'a pas renvoyé un JSON valide : {e}")

    try:
        return ProgrammeExtrait(**data)
    except ValidationError as e:
        raise HTTPException(422, f"Structure JSON incorrecte : {e}")


# ---------- Insertion Supabase ----------

def upsert_programme(programme: ProgrammeExtrait) -> dict:
    # Hippodrome : cherche par nom, ne crée pas à la volée (évite les doublons
    # de type "Vincennes" vs "vincennes" ; à ajuster si tu préfères l'auto-création)
    hippo_res = (
        supabase.table("hippodromes")
        .select("id")
        .ilike("nom", programme.hippodrome_nom)
        .limit(1)
        .execute()
    )
    if not hippo_res.data:
        raise HTTPException(
            404,
            f"Hippodrome '{programme.hippodrome_nom}' introuvable — "
            "vérifie l'orthographe ou crée-le d'abord dans la table hippodromes.",
        )
    hippodrome_id = hippo_res.data[0]["id"]

    # Réunion : upsert sur (date, numero, hippodrome_id)
    reunion_res = (
        supabase.table("reunions")
        .upsert(
            {
                "date": programme.date,
                "numero": programme.reunion_numero,
                "hippodrome_id": hippodrome_id,
            },
            on_conflict="date,numero,hippodrome_id",
        )
        .execute()
    )
    reunion_id = reunion_res.data[0]["id"]

    courses_written = 0
    partants_written = 0

    for course in programme.courses:
        course_res = (
            supabase.table("courses")
            .upsert(
                {
                    "reunion_id": reunion_id,
                    "numero": course.numero,
                    "libelle": course.libelle,
                    "discipline": course.discipline,
                    "distance_m": course.distance_m,
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
            supabase.table("partants").upsert(
                {
                    "course_id": course_id,
                    "numero": partant.numero,
                    "cheval_nom": partant.cheval_nom,
                    "jockey": partant.jockey,
                    "entraineur": partant.entraineur,
                    "cote_matin": partant.cote_matin,
                },
                on_conflict="course_id,numero",
            ).execute()
            partants_written += 1

    return {
        "reunion_id": reunion_id,
        "courses_written": courses_written,
        "partants_written": partants_written,
    }


def log_ingestion_run(status: str, result: dict, error: Optional[str] = None):
    supabase.table("historique_ingestion_runs").insert(
        {
            "source": SOURCE_MANUAL_UPLOAD,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "documents_seen": 1,
            "documents_ok": 1 if status == "success" else 0,
            "documents_failed": 0 if status == "success" else 1,
            "courses_written": result.get("courses_written", 0),
            "partants_written": result.get("partants_written", 0),
            "errors": {"message": error} if error else None,
        }
    ).execute()


# ---------- Route ----------

@app.post("/api/ingest-pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Seuls les fichiers PDF sont acceptés pour l'instant.")

    file_bytes = await file.read()

    try:
        pdf_text = extract_pdf_text(file_bytes)
        if not pdf_text.strip():
            raise HTTPException(422, "Aucun texte extrait du PDF (scan image sans OCR ?).")

        programme = structure_programme(pdf_text)
        result = upsert_programme(programme)
        log_ingestion_run("success", result)

        return {
            "message": (
                f"Programme importé : {programme.hippodrome_nom} du {programme.date} — "
                f"{result['courses_written']} course(s), {result['partants_written']} partant(s)."
            ),
            **result,
        }

    except HTTPException as e:
        log_ingestion_run("failed", {}, error=str(e.detail))
        raise
    except Exception as e:
        log_ingestion_run("failed", {}, error=str(e))
        raise HTTPException(500, f"Erreur inattendue lors de l'import : {e}")
