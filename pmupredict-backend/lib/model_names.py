from __future__ import annotations

import re
import unicodedata


def canonical_discipline(value: object) -> str:
    """Retourne un suffixe de modèle stable, sans accents ni espaces."""
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    aliases = {
        "trot_attele": "attele",
        "trot_attelee": "attele",
        "attele": "attele",
        "trot": "trot",
        "plat": "plat",
    }

    return aliases.get(text, text or "inconnu")


def model_name(discipline: object, base: str = "lgbm_ranker") -> str:
    return f"{base}_{canonical_discipline(discipline)}"
