import re
from datetime import date


def identify_race_from_pdf_text(text: str) -> dict:
    """Identify date, race number and basic race metadata from PMU PDF text."""
    if not text or not text.strip():
        raise ValueError("Texte PDF vide")

    normalized = re.sub(r"\s+", " ", text).strip()

    date_match = re.search(
        r"\b(?:DU|LE)\s+"
        r"(?:LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)\s+"
        r"(\d{1,2})\s+"
        r"(JANVIER|FÉVRIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOÛT|AOUT|SEPTEMBRE|OCTOBRE|NOVEMBRE|DÉCEMBRE|DECEMBRE)\s+"
        r"(\d{4})",
        normalized,
        re.IGNORECASE,
    )

    month_names = {
        "JANVIER": 1,
        "FÉVRIER": 2,
        "FEVRIER": 2,
        "MARS": 3,
        "AVRIL": 4,
        "MAI": 5,
        "JUIN": 6,
        "JUILLET": 7,
        "AOÛT": 8,
        "AOUT": 8,
        "SEPTEMBRE": 9,
        "OCTOBRE": 10,
        "NOVEMBRE": 11,
        "DÉCEMBRE": 12,
        "DECEMBRE": 12,
    }

    detected_date = None
    if date_match:
        day = int(date_match.group(1))
        month = month_names[date_match.group(2).upper()]
        year = int(date_match.group(3))
        detected_date = date(year, month, day).isoformat()

    course_match = re.search(
        r"\b(\d{1,2})\s*(?:[ÈE]RE|[ÈE]RE)\s+COURSE\b",
        normalized,
        re.IGNORECASE,
    )

    course_number = int(course_match.group(1)) if course_match else None

    race_match = re.search(
        r"\b(?:QUINT[ÉE]|QUARTE|4\+1|TIERCE)\b",
        normalized,
        re.IGNORECASE,
    )

    race_type = race_match.group(0).upper() if race_match else None

    return {
        "date": detected_date,
        "course_numero": course_number,
        "type_epreuve": race_type,
    }


def extract_race_identity(text: str) -> tuple[str | None, int | None]:
    """Return the date and course number needed to resolve a Supabase course_id."""
    result = identify_race_from_pdf_text(text)
    return result["date"], result["course_numero"]


def resolve_course_id(supabase, race_date: str, course_numero: int):
    """Resolve a Supabase course ID from the PDF race identity."""
    if not race_date or not course_numero:
        return None

    reunions = (
        supabase.table("reunions")
        .select("id,numero,hippodrome_id")
        .eq("date", race_date)
        .execute()
        .data
    )

    for reunion in reunions or []:
        courses = (
            supabase.table("courses")
            .select("id,numero,reunion_id")
            .eq("reunion_id", reunion["id"])
            .eq("numero", course_numero)
            .limit(1)
            .execute()
            .data
        )

        if courses:
            return courses[0]["id"]

    return None
