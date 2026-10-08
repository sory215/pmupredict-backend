"""
Parseur des programmes hippiques PDF.

Le PDF "Journal Hippique PMU'B" peut contenir une réunion complète.
Chaque table pdfplumber correspondant à une course est transformée en
CourseExtraite, sans modifier le pipeline d'upsert existant.
"""

import re
from dataclasses import dataclass, field
from io import BytesIO

import pdfplumber


MOIS_FR = {
    "JANVIER": 1,
    "FEVRIER": 2,
    "FÉVRIER": 2,
    "MARS": 3,
    "AVRIL": 4,
    "MAI": 5,
    "JUIN": 6,
    "JUILLET": 7,
    "AOUT": 8,
    "AOÛT": 8,
    "SEPTEMBRE": 9,
    "OCTOBRE": 10,
    "NOVEMBRE": 11,
    "DECEMBRE": 12,
    "DÉCEMBRE": 12,
}

DISCIPLINE_MAP = {
    "ATTELE": "trot",
    "ATTELÉ": "trot",
    "MONTE": "trot_monte",
    "MONTÉ": "trot_monte",
    "PLAT": "plat",
    "HAIES": "obstacle",
    "STEEPLE": "obstacle",
    "CROSS": "obstacle",
}


class ProgrammePdfError(Exception):
    pass


@dataclass
class PartantExtrait:
    numero: int
    cheval_nom: str
    driver_jockey: str | None = None
    entraineur: str | None = None
    proprietaire: str | None = None
    sexe: str | None = None
    age: int | None = None
    cote_matin: float | None = None
    distance_m: int | None = None
    poids_kg: float | None = None


@dataclass
class CourseExtraite:
    numero: int
    libelle: str
    discipline: str
    distance_m: int | None
    allocation_euros: int | None
    heure_depart: str | None
    partants: list[PartantExtrait] = field(default_factory=list)


@dataclass
class ProgrammeExtrait:
    hippodrome_nom: str
    date: str
    reunion_numero: int
    courses: list[CourseExtraite]


def _parse_date_fr(jour: str, mois: str, annee: str) -> str:
    mois_num = MOIS_FR.get(mois.upper())
    if not mois_num:
        raise ProgrammePdfError(f"Mois non reconnu : {mois}")
    return f"{annee}-{mois_num:02d}-{int(jour):02d}"


def _find_date(all_text: str) -> str:
    match = re.search(
        r"\b(?:LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI|DIMANCHE)"
        r"\s+(\d{1,2})\s+([A-ZÉÈÊËÀÂÎÏÔÛÙÜŸÇ]+)\s+(\d{4})\b",
        all_text,
        re.IGNORECASE,
    )
    if not match:
        raise ProgrammePdfError("Date du programme introuvable")
    return _parse_date_fr(*match.groups())


def _find_hippodrome(all_text: str) -> str:
    match = re.search(
        r"HIPPODROME\s+DE\s+(.+?)(?:\s*\(R\d+\))?\s*$",
        all_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        raise ProgrammePdfError("Hippodrome introuvable")

    nom = re.sub(r"\s*\(R\d+\)\s*$", "", match.group(1).strip(), flags=re.IGNORECASE)
    nom = re.sub(r"\s+", " ", nom).strip()

    if not nom:
        raise ProgrammePdfError("Nom de l'hippodrome vide")

    return "HIPPODROME DE " + nom


def _find_reunion_numero(all_text: str) -> int:
    match = re.search(r"HIPPODROME.*?\(R(\d+)\)", all_text, re.IGNORECASE)
    return int(match.group(1)) if match else 1


def _split_cell(cell: str | None) -> list[str]:
    if not cell:
        return []
    return [value.strip() for value in str(cell).split("\n") if value.strip()]


def _column_values(table: list[list], column_substrings: list[str]) -> list[str]:
    if not table:
        return []

    header = [
        str(cell or "").upper().replace("\n", " ").strip()
        for cell in table[0]
    ]

    col_idx = None
    for index, value in enumerate(header):
        if any(sub.upper() in value for sub in column_substrings):
            col_idx = index
            break

    if col_idx is None:
        return []

    values: list[str] = []
    for row in table[1:]:
        if col_idx < len(row):
            values.extend(_split_cell(row[col_idx]))
    return values


def _find_partants_tables(pdf: pdfplumber.PDF) -> list[list[list]]:
    """
    Retourne toutes les tables ayant le schéma des partants.

    Dans le PDF testé, chaque course possède une table de deux lignes :
    l'en-tête puis une ligne dont chaque cellule contient les valeurs
    séparées par des retours à la ligne.
    """
    tables = []

    for page in pdf.pages:
        for table in page.extract_tables():
            if not table:
                continue

            header = [
                str(cell or "").upper().replace("\n", " ").strip()
                for cell in table[0]
            ]

            has_horses = any("CHEVAUX" in value for value in header)
            has_jockeys = any("JOCKEYS" in value for value in header)
            has_trainers = any("ENTRAINEUR" in value for value in header)

            if has_horses and has_jockeys and has_trainers:
                tables.append(table)

    if not tables:
        raise ProgrammePdfError(
            "Aucune table de partants (CHEVAUX/JOCKEYS/ENTRAINEURS) trouvée"
        )

    return tables


def _parse_sexe_age(value: str | None) -> tuple[str | None, int | None]:
    if not value:
        return None, None

    match = re.match(r"^([A-ZÀ-ÖØ-Ý])\s*(\d+)$", value.strip(), re.IGNORECASE)
    if not match:
        return None, None

    return match.group(1).upper(), int(match.group(2))


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = value.strip().replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)

    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_distance(value: str | None) -> int | None:
    number = _parse_number(value)
    return int(number) if number is not None else None


def _parse_weight(value: str | None) -> float | None:
    return _parse_number(value)


def _extract_course_hours(all_text: str, date_iso: str) -> list[str | None]:
    """
    Les horaires apparaissent dans le PDF dans l'ordre des courses.
    Exemple : 11H 55, 12H 31, 13H 09...
    """
    matches = re.findall(
        r"\b(\d{1,2})H\s*(\d{2})\b",
        all_text,
        re.IGNORECASE,
    )

    hours: list[str | None] = []
    seen: set[str] = set()

    for hour, minute in matches:
        value = f"{int(hour):02d}:{minute}"
        if value in seen:
            continue
        seen.add(value)
        hours.append(f"{date_iso}T{value}:00")

    return hours


def _extract_course_metadata(page_text: str, course_number: int) -> dict:
    """
    Les lignes de titre sont fortement bruitées par l'extraction PDF.
    On conserve uniquement les informations fiables. Les champs textuels
    impossibles à reconstruire proprement restent None/fallback.
    """
    lines = page_text.splitlines()

    for index, line in enumerate(lines):
        if not re.search(rf"\bCOURSE\s+{course_number}\b", line, re.IGNORECASE):
            continue

        # Le texte extrait mélange plusieurs colonnes. On cherche une
        # distance explicite dans la zone du titre comme secours.
        nearby = " ".join(lines[index:index + 2])

        distance_match = re.search(
            r"(\d[\d\s]{2,5})\s*M(?:ETRES)?\b",
            nearby,
            re.IGNORECASE,
        )
        distance_m = None
        if distance_match:
            try:
                distance_m = int(re.sub(r"\s", "", distance_match.group(1)))
            except ValueError:
                distance_m = None

        return {
            "libelle": f"Course {course_number}",
            "discipline": "plat",
            "distance_m": distance_m,
            "allocation_euros": None,
        }

    return {
        "libelle": f"Course {course_number}",
        "discipline": "plat",
        "distance_m": None,
        "allocation_euros": None,
    }


def _parse_course_table(
    table: list[list],
    course_number: int,
    heure_depart: str | None,
    metadata: dict,
) -> CourseExtraite:
    chevaux = _column_values(table, ["CHEVAUX"])
    numeros_raw = _column_values(table, ["N°", "N °", "NO"])
    sexe_age = _column_values(table, ["S/A"])
    distances = _column_values(table, ["DISTANCE", "DIST"])
    poids = _column_values(table, ["POIDS"])
    jockeys = _column_values(table, ["JOCKEYS", "DRIVERS"])
    entraineurs = _column_values(table, ["ENTRAINEURS", "ENTRAINEUR"])
    proprietaires = _column_values(table, ["PROPRIETAIRES", "PROPRIETAIRE"])

    if not chevaux:
        raise ProgrammePdfError(
            f"Course {course_number}: aucun cheval trouvé dans la table"
        )

    partants: list[PartantExtrait] = []

    for index, cheval in enumerate(chevaux):
        sexe, age = _parse_sexe_age(
            sexe_age[index] if index < len(sexe_age) else None
        )

        numero = index + 1
        if index < len(numeros_raw):
            raw_numero = numeros_raw[index].strip()
            if raw_numero.isdigit():
                numero = int(raw_numero)

        partants.append(
            PartantExtrait(
                numero=numero,
                cheval_nom=cheval,
                driver_jockey=(
                    jockeys[index] if index < len(jockeys) else None
                ),
                entraineur=(
                    entraineurs[index] if index < len(entraineurs) else None
                ),
                proprietaire=(
                    proprietaires[index]
                    if index < len(proprietaires)
                    else None
                ),
                sexe=sexe,
                age=age,
                cote_matin=None,
                distance_m=(
                    _parse_distance(distances[index])
                    if index < len(distances)
                    else None
                ),
                poids_kg=(
                    _parse_weight(poids[index])
                    if index < len(poids)
                    else None
                ),
            )
        )

    distance_m = metadata.get("distance_m")
    if distance_m is None and distances:
        distance_m = _parse_distance(distances[0])

    return CourseExtraite(
        numero=course_number,
        libelle=metadata.get("libelle") or f"Course {course_number}",
        discipline=metadata.get("discipline") or "plat",
        distance_m=distance_m,
        allocation_euros=metadata.get("allocation_euros"),
        heure_depart=heure_depart,
        partants=partants,
    )


def parse_programme_pdf(file_bytes: bytes) -> ProgrammeExtrait:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        if not pdf.pages:
            raise ProgrammePdfError("PDF vide")

        all_text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        )

        date_iso = _find_date(all_text)
        hippodrome_nom = _find_hippodrome(all_text)
        reunion_numero = _find_reunion_numero(all_text)

        tables = _find_partants_tables(pdf)
        hours = _extract_course_hours(all_text, date_iso)

        courses: list[CourseExtraite] = []

        for index, table in enumerate(tables, start=1):
            page_text = ""
            for page in pdf.pages:
                if table in page.extract_tables():
                    page_text = page.extract_text() or ""
                    break

            metadata = _extract_course_metadata(page_text, index)
            heure_depart = hours[index - 1] if index <= len(hours) else None

            courses.append(
                _parse_course_table(
                    table,
                    index,
                    heure_depart,
                    metadata,
                )
            )

        if not courses:
            raise ProgrammePdfError("Aucune course trouvée dans le PDF")

        return ProgrammeExtrait(
            hippodrome_nom=hippodrome_nom,
            date=date_iso,
            reunion_numero=reunion_numero,
            courses=courses,
        )
