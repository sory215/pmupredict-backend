from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ResultSource(ABC):
    """
    Interface commune pour toutes les sources de résultats PMU.
    """

    name: str = "unknown"

    @abstractmethod
    def fetch(self, jour: str) -> list[dict[str, Any]]:
        """
        Retourne une liste normalisée de courses.
        """
        raise NotImplementedError

    def available(self) -> bool:
        return True
