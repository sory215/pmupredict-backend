from __future__ import annotations

from typing import Callable


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
