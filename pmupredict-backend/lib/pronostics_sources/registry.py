from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SourceConfig:
    key: str
    nom: str
    type_source: str
    actif: bool = True
    priorite: int = 1
    independant: bool = True
    description: str = ""


# Registre des collecteurs Python.
COLLECTORS: dict[str, Callable] = {}


def register(name: str):
    def decorator(func):
        COLLECTORS[name] = func
        return func

    return decorator


def get(name: str):
    return COLLECTORS.get(name)


def names():
    return sorted(COLLECTORS)


# Sources externes retenues pour PMUPredict.
#
# priorite:
#   1 = source principale
#   2 = source complémentaire
#   3 = agrégateur / consensus
#
# independant=False signifie que la source peut reprendre
# les sélections d'autres médias et ne doit pas être comptée
# comme un pronostiqueur indépendant dans la fusion.

SOURCES: dict[str, SourceConfig] = {
    "turf_pronostics": SourceConfig(
        key="turf_pronostics",
        nom="Turf-Pronostics",
        type_source="communaute",
        priorite=1,
        independant=True,
        description="Pronostics individuels de la communauté Turf-Pronostics.",
    ),
    "canalturf_nicolas": SourceConfig(
        key="canalturf_nicolas",
        nom="Nicolas Labourasse - Canalturf",
        type_source="presse",
        priorite=1,
        independant=True,
        description="Sélection du journaliste Nicolas Labourasse.",
    ),
    "rue_des_joueurs_sarah": SourceConfig(
        key="rue_des_joueurs_sarah",
        nom="Sarah - Rue des Joueurs",
        type_source="presse",
        priorite=1,
        independant=True,
        description="Pronostics de l'experte turf de Rue des Joueurs.",
    ),
    "zone_turf": SourceConfig(
        key="zone_turf",
        nom="Zone-Turf",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Sélections et top chances de la rédaction Zone-Turf.",
    ),
    "turfoo": SourceConfig(
        key="turfoo",
        nom="Turfoo",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Pronostics et classement éditorial Turfoo.",
    ),
    "geny": SourceConfig(
        key="geny",
        nom="Geny / Genybet",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Pronostics, sélection et données de marché Geny.",
    ),
    "turfomania": SourceConfig(
        key="turfomania",
        nom="Turfomania",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Sélections et analyses Turfomania.",
    ),
    "equidia": SourceConfig(
        key="equidia",
        nom="Equidia",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Pronostics et analyses Equidia.",
    ),
    "paris_turf": SourceConfig(
        key="paris_turf",
        nom="Paris-Turf",
        type_source="presse",
        priorite=2,
        independant=True,
        description="Sélections de la presse hippique Paris-Turf.",
    ),
    "zeturf": SourceConfig(
        key="zeturf",
        nom="ZEturf",
        type_source="marche",
        priorite=2,
        independant=True,
        description="Pronostics et signaux de l'opérateur ZEturf.",
    ),
    "canalturf_presse": SourceConfig(
        key="canalturf_presse",
        nom="Canalturf - Synthèse presse",
        type_source="agregateur",
        priorite=3,
        independant=False,
        description="Synthèse des sélections publiées par plusieurs journaux.",
    ),
    "frequence_turf": SourceConfig(
        key="frequence_turf",
        nom="Fréquence Turf",
        type_source="agregateur",
        priorite=3,
        independant=False,
        description="Agrégation de pronostics de plusieurs médias hippiques.",
    ),
}


def get_source(name: str) -> SourceConfig | None:
    """Retourne la configuration d'une source."""
    return SOURCES.get(name)


def source_names(actives_only: bool = True) -> list[str]:
    """Retourne les identifiants des sources connues."""
    if actives_only:
        return sorted(
            key for key, source in SOURCES.items()
            if source.actif
        )
    return sorted(SOURCES)


def independent_sources() -> list[SourceConfig]:
    """Sources pouvant alimenter le consensus indépendant."""
    return [
        source
        for source in SOURCES.values()
        if source.actif and source.independant
    ]


def aggregator_sources() -> list[SourceConfig]:
    """Sources de synthèse à ne pas compter comme indépendantes."""
    return [
        source
        for source in SOURCES.values()
        if source.actif and not source.independant
    ]
