"""Feature engineering sans fuite temporelle."""
from __future__ import annotations

import re
import pandas as pd

FEATURE_COLUMNS = [
    "cote_actuelle",
    "cote_rang",
    "poids_kg",
    "score_musique",
    "nb_courses_musique",
    "taux_top3_musique",
    "taux_incident_musique",
    "ecart_cote",
    "jockey_encoded",
    "discipline_encoded",
    "distance_m",
    "nb_partants",
    "prev_rang_1",
    "prev_rang_2",
    "jours_repos",
    "diff_allocation",
    "bonus_changement_ferrure",
]

_TOKEN_MUSIQUE = re.compile(r"(\d+)([a-zA-Z]?)")


class SimpleLabelEncoder:
    """Remplacement léger de sklearn.preprocessing.LabelEncoder."""

    def __init__(self):
        self.classes_ = []

    def fit(self, values):
        values = [str(v) for v in values]
        self.classes_ = sorted(set(values))
        return self

    def transform(self, values):
        mapping = {value: i for i, value in enumerate(self.classes_)}
        return [mapping[str(v)] for v in values]


def _parser_musique(m) -> dict:
    if not isinstance(m, str) or not m:
        return {
            "score_musique": 0,
            "nb_courses_musique": 0,
            "taux_top3_musique": 0.0,
            "taux_incident_musique": 0.0,
        }

    tokens = _TOKEN_MUSIQUE.findall(
        re.sub(r"\([^)]*\)", "", m)
    )

    if not tokens:
        return {
            "score_musique": 0,
            "nb_courses_musique": 0,
            "taux_top3_musique": 0.0,
            "taux_incident_musique": 0.0,
        }

    positions = [int(p) for p, _ in tokens]
    n = len(positions)
    top3 = sum(p in (1, 2, 3) for p in positions)

    return {
        "score_musique": top3,
        "nb_courses_musique": n,
        "taux_top3_musique": top3 / n,
        "taux_incident_musique": sum(p == 0 for p in positions) / n,
    }


def enrichir_historique(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col, default in {
        "cheval_nom": "inconnu",
        "allocation": 0,
        "est_deferre": False,
    }.items():
        if col not in df.columns:
            df[col] = default

    df["heure_depart"] = pd.to_datetime(
        df["heure_depart"],
        utc=True,
        errors="coerce",
    )

    df = df.sort_values(
        ["cheval_nom", "heure_depart", "course_id"]
    ).reset_index(drop=True)

    grp = df.groupby("cheval_nom", group_keys=False)

    if "position" in df.columns:
        df["prev_rang_1"] = grp["position"].shift(1)
        df["prev_rang_2"] = grp["position"].shift(2)

    df["prev_heure_depart"] = grp["heure_depart"].shift(1)

    df["jours_repos"] = (
        df["heure_depart"] - df["prev_heure_depart"]
    ).dt.total_seconds() / 86400

    df["prev_allocation"] = grp["allocation"].shift(1)

    df["diff_allocation"] = (
        pd.to_numeric(df["allocation"], errors="coerce")
        - pd.to_numeric(df["prev_allocation"], errors="coerce")
    ).fillna(0)

    df["prev_est_deferre"] = grp["est_deferre"].shift(1)

    df["bonus_changement_ferrure"] = (
        (
            df["est_deferre"].fillna(False).astype(bool)
            & (df["prev_est_deferre"].fillna(False) == False)
        )
        .astype(int)
    )

    return df


def _safe_encoder(values, encoder=None):
    values = values.fillna("inconnu").astype(str)

    if encoder is None:
        encoder = SimpleLabelEncoder()
        encoder.fit(values)

    known = set(map(str, encoder.classes_))

    fallback = (
        str(encoder.classes_[0])
        if len(encoder.classes_)
        else "inconnu"
    )

    values = values.map(
        lambda x: x if x in known else fallback
    )

    return values, encoder


def build_features(
    df: pd.DataFrame,
    jockey_encoder=None,
    discipline_encoder=None,
):
    df = df.copy()

    stats = (
        df.get(
            "musique",
            pd.Series(index=df.index, dtype=object),
        )
        .apply(_parser_musique)
        .apply(pd.Series)
    )

    df = pd.concat(
        [
            df.drop(
                columns=[
                    c for c in stats.columns
                    if c in df.columns
                ]
            ),
            stats,
        ],
        axis=1,
    )

    for col, default in {
        "cote_matin": 0,
        "cote_actuelle": 0,
        "poids_kg": 0,
        "distance_m": 0,
        "allocation": 0,
    }.items():
        if col not in df.columns:
            df[col] = default

    df["ecart_cote"] = (
        pd.to_numeric(df["cote_matin"], errors="coerce")
        - pd.to_numeric(df["cote_actuelle"], errors="coerce")
    ).fillna(0)

    df["cote_actuelle"] = (
        pd.to_numeric(df["cote_actuelle"], errors="coerce")
        .fillna(0)
    )

    df["cote_rang"] = (
        df.groupby("course_id")["cote_actuelle"]
        .rank(method="min", ascending=True)
        .fillna(0)
    )

    df["nb_partants"] = (
        df.groupby("course_id")["course_id"]
        .transform("size")
    )

    df["jockey"], jockey_encoder = _safe_encoder(
        df.get(
            "jockey",
            pd.Series(index=df.index, dtype=object),
        ),
        jockey_encoder,
    )

    df["discipline"], discipline_encoder = _safe_encoder(
        df.get(
            "discipline",
            pd.Series(index=df.index, dtype=object),
        ),
        discipline_encoder,
    )

    df["jockey_encoded"] = jockey_encoder.transform(
        df["jockey"]
    )

    df["discipline_encoded"] = discipline_encoder.transform(
        df["discipline"]
    )

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0

    return (
        df[FEATURE_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0),
        jockey_encoder,
        discipline_encoder,
    )


def rang_vers_pertinence(position):
    if position is None or pd.isna(position):
        return 0

    return max(0, 6 - int(position))
