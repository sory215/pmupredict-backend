from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PronosticExterne:
    source: str
    pronostiqueur: str
    type_source: str

    date: str
    reunion: int
    course: int

    classement: list[int] = field(default_factory=list)

    base: list[int] = field(default_factory=list)
    chances: list[int] = field(default_factory=list)
    outsiders: list[int] = field(default_factory=list)

    commentaire: str = ""
    url: str = ""

    def all_numbers(self) -> list[int]:
        """
        Retourne le classement principal sans doublons.
        """
        result = []

        for numero in (
            self.classement
            + self.base
            + self.chances
            + self.outsiders
        ):
            if numero not in result:
                result.append(numero)

        return result
