"""
Parseur pour le format "Journal Hippique PMU'B" (LONAB) — un PDF par jour,
couvrant la course phare ("Quarté") de la réunion.

Approche : la grille des partants est une vraie table avec bordures dans le
PDF — on utilise pdfplumber.extract_tables() pour la récupérer directement,
au lieu de reclassifier ligne par ligne un texte linéarisé (fragile, cassé
par les colonnes d'articles qui s'entremêlent à l'extraction texte brute).

Les métadonnées d'en-tête (hippodrome, date, distance...) sont dans l'encart
"QUARTE" en haut à droite de la première page ; on isole cette moitié de page
avant extraction, car le texte pleine page mélange l'encart avec les fiches
chevaux en colonnes à sa gauche (vérifié visuellement).

Limite connue : ce PDF ne couvre qu'UNE SEULE course par jour (la course
phare), pas la réunion complète. reunion_numero est donc toujours 1.
"""

import re
from dataclasses import dataclass, field
from io import BytesIO

import pdfplumber

MOIS_FR = {
    "JANVIER": 1, "FEVRIER": 2, "FÉVRIER": 2, "MARS": 3, "AVRIL": 4,
    "MAI": 5, "JUIN": 6, "JUILLET": 7, "AOUT": 8, "AOÛT": 8,
    "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11, "DECEMBRE": 12, "DÉCEMBRE": 12,
}

DISCIPLINE_MAP = {
    "ATTELE": "trot", "ATTELÉ": "trot", "MONTE": "trot_monte", "MONTÉ": "trot_monte",
    "PLAT": "plat", "HAIES": "obstacle", "STEEPLE": "obstacle", "CROSS": "obstacle",
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
    date: str  # YYYY-MM-DD
    reunion_numero: int
    courses: list[CourseExtraite]


def _parse_date_fr(jour: str, mois: str, annee: str) -> str:
    mois_num = MOIS_FR.get(mois.upper())
    if not mois_num:
        raise ProgrammePdfError(f"Mois non reconnu : {mois}")
    return f"{annee}-{mois_num:02d}-{int(jour):02d}"


def _parse_header(header_text: str) -> dict:
    date_match = re.search(
        r'"QUARTE"\s+DU\s+\w+\s+(\d{1,2})\s+([A-ZÉÛ]+)\s+(\d{4})', header_text, re.IGNORECASE
    )
    if not date_match:
        raise ProgrammePdfError("Ligne de date introuvable (format \"QUARTE\" DU ...)")
    date_iso = _parse_date_fr(*date_match.groups())

    lines = header_text.splitlines()
    lieu_line = None
    for i, line in enumerate(lines):
        if '"QUARTE"' in line.upper():
            lieu_line = lines[i + 1].strip() if i + 1 < len(lines) else None
            break
    if not lieu_line:
        raise ProgrammePdfError("Ligne hippodrome/prix/discipline introuvable")

    parts = [p.strip() for p in lieu_line.split(" - ")]
    if len(parts) < 3:
        raise ProgrammePdfError(f"Format inattendu pour la ligne lieu : {lieu_line!r}")
    hippodrome_nom, prix_libelle, discipline_raw = parts[0], parts[1], parts[-1]
    discipline = DISCIPLINE_MAP.get(discipline_raw.upper(), discipline_raw.lower())

    concurrents_match = re.search(r"(\d+)\s+CONCURRENTS\s*-\s*(\d+)\w*\s+COURSE", header_text, re.IGNORECASE)
    if not concurrents_match:
        raise ProgrammePdfError("Ligne 'X CONCURRENTS - Nème COURSE' introuvable")
    n_partants, course_numero = int(concurrents_match.group(1)), int(concurrents_match.group(2))

    allocation_match = re.search(r"([\d\s]+)\s*EUROS", header_text)
    allocation_euros = int(re.sub(r"\s", "", allocation_match.group(1))) if allocation_match else None

    distance_match = re.search(r"-\s*([\d\s]+)\s*METRES", header_text, re.IGNORECASE)
    distance_m = int(re.sub(r"\s", "", distance_match.group(1))) if distance_match else None

    return {
        "hippodrome_nom": hippodrome_nom,
        "prix_libelle": prix_libelle,
        "discipline": discipline,
        "date": date_iso,
        "n_partants": n_partants,
        "course_numero": course_numero,
        "allocation_euros": allocation_euros,
        "distance_m": distance_m,
    }


def _find_heure_depart(all_pages_text: str, date_iso: str) -> str | None:
    depart_match = re.search(r"D[ÉE]PART DE LA COURSE\s*:\s*(\d{1,2})h\s*(\d{2})", all_pages_text, re.IGNORECASE)
    if not depart_match:
        return None
    h, m = depart_match.groups()
    return f"{date_iso}T{int(h):02d}:{m}:00"


def _find_partants_table(pdf: pdfplumber.PDF) -> list[list]:
    """Cherche, sur toutes les pages, la table dont l'en-tête contient
    CHEVAUX + ENTRAINEURS + PROPRIETAIRES, et fusionne ses lignes de données
    (parfois scindées en plusieurs blocs, ex. partants 1-10 puis 11-16)."""
    for page in pdf.pages:
        for table in page.extract_tables():
            if not table:
                continue
            header = [str(c or "").upper().replace("\n", " ") for c in table[0]]
            if any("CHEVAUX" in h for h in header) and any("ENTRAINEUR" in h for h in header):
                return table
    raise ProgrammePdfError("Table des partants (CHEVAUX/ENTRAINEURS/...) introuvable sur aucune page")


def _split_cell(cell: str | None) -> list[str]:
    if not cell:
        return []
    return [v.strip() for v in cell.split("\n") if v.strip()]


def _column_values(table: list[list], column_substrings: list[str]) -> list[str]:
    """Trouve la colonne dont l'en-tête contient une des sous-chaînes données,
    et renvoie ses valeurs concaténées sur toutes les lignes de données."""
    header = [str(c or "").upper().replace("\n", " ") for c in table[0]]
    col_idx = None
    for i, h in enumerate(header):
        if any(sub in h for sub in column_substrings):
            col_idx = i
            break
    if col_idx is None:
        return []
    values = []
    for row in table[1:]:
        values.extend(_split_cell(row[col_idx] if col_idx < len(row) else None))
    return values


def parse_programme_pdf(file_bytes: bytes) -> ProgrammeExtrait:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        if not pdf.pages:
            raise ProgrammePdfError("PDF vide")

        # En-tête : moitié droite de la première page (isole l'encart "QUARTE"
        # des fiches chevaux en colonnes qui l'entourent à gauche)
        page0 = pdf.pages[0]
        width, height = page0.width, page0.height
        header_text = page0.crop((width / 2, 0, width, height)).extract_text() or ""
        header = _parse_header(header_text)

        # Heure de départ : recherche sur le texte complet de toutes les pages
        all_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        heure_depart = _find_heure_depart(all_text, header["date"])

        # Table des partants
        table = _find_partants_table(pdf)

    n = header["n_partants"]

    numeros_raw = _column_values(table, ["N°", "N °", "NO"])
    chevaux = _column_values(table, ["CHEVAUX"])
    drivers_jockeys = _column_values(table, ["DRIVERS", "JOCKEYS"])
    entraineurs = _column_values(table, ["ENTRAINEUR"])
    proprietaires = _column_values(table, ["PROPRIETAIRE"])
    sexe_age = _column_values(table, ["SEXE"])
    dist_m_raw = _column_values(table, ["DIST"])
    poids_raw = _column_values(table, ["POIDS"])
    cotes_raw = _column_values(table, ["PARIS TURF", "PARIS"])

    if len(chevaux) < n:
        raise ProgrammePdfError(
            f"Attendu {n} chevaux (d'après '{n} CONCURRENTS'), seulement {len(chevaux)} trouvés dans la table."
        )

    partants = []
    for i in range(n):
        sexe, age = None, None
        if i < len(sexe_age) and "." in sexe_age[i]:
            sexe, age_str = sexe_age[i].split(".", 1)
            try:
                age = int(age_str)
            except ValueError:
                age = None

        cote_matin = None
        if i < len(cotes_raw) and "/" in cotes_raw[i]:
            num, den = cotes_raw[i].split("/")
            try:
                cote_matin = round(1 + int(num) / int(den), 2)
            except (ValueError, ZeroDivisionError):
                cote_matin = None

        distance_m = None
        if i < len(dist_m_raw):
            m = re.match(r"([\d.]+)", dist_m_raw[i])
            if m:
                try:
                    distance_m = int(float(m.group(1)))
                except ValueError:
                    distance_m = None

        poids_kg = None
        if i < len(poids_raw):
            try:
                poids_kg = float(poids_raw[i].replace(".KG", ""))
            except ValueError:
                poids_kg = None

        partants.append(
            PartantExtrait(
                numero=int(numeros_raw[i]) if i < len(numeros_raw) and numeros_raw[i].isdigit() else i + 1,
                cheval_nom=chevaux[i],
                driver_jockey=drivers_jockeys[i] if i < len(drivers_jockeys) else None,
                entraineur=entraineurs[i] if i < len(entraineurs) else None,
                proprietaire=proprietaires[i] if i < len(proprietaires) else None,
                sexe=sexe,
                age=age,
                cote_matin=cote_matin,
                distance_m=distance_m,
                poids_kg=poids_kg,
            )
        )

    course = CourseExtraite(
        numero=header["course_numero"],
        libelle=header["prix_libelle"],
        discipline=header["discipline"],
        distance_m=header["distance_m"],
        allocation_euros=header["allocation_euros"],
        heure_depart=heure_depart,
        partants=partants,
    )

    return ProgrammeExtrait(
        hippodrome_nom=header["hippodrome_nom"],
        date=header["date"],
        reunion_numero=1,
        courses=[course],
    )
