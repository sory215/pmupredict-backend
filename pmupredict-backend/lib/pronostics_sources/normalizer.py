from __future__ import annotations

import re


def numbers(value) -> list[int]:
    """
    Transforme différentes représentations en liste de numéros.

    Exemples :
        "4-7-2-5"       -> [4, 7, 2, 5]
        "4 7 2 5"       -> [4, 7, 2, 5]
        [4, 7, 2, 5]    -> [4, 7, 2, 5]
    """
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        result = []
        for x in value:
            try:
                n = int(x)
                if n > 0 and n not in result:
                    result.append(n)
            except (TypeError, ValueError):
                continue
        return result

    text = str(value)

    result = []
    for x in re.findall(r"\d+", text):
        try:
            n = int(x)
            if n > 0 and n not in result:
                result.append(n)
        except ValueError:
            continue

    return result


def normalize_race(reunion, course) -> tuple[int, int]:
    return int(reunion), int(course)
