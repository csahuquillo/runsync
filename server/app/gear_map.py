"""
Mapeo canónico de zapatillas a IDs por plataforma.

Cada zapatilla tiene un "canonical_name" y los IDs específicos de cada plataforma.
Aliases permite que el Atajo mande nombres cortos ("NB More v5") y resuelvan
al canonical correcto.
"""

from typing import TypedDict


class GearEntry(TypedDict, total=False):
    canonical: str
    garmin_uuid: str
    intervals_id: str
    strava_id: str


GEAR: dict[str, GearEntry] = {
    "Adidas Boston 13": {
        "canonical": "Adidas Boston 13",
        "garmin_uuid": "2dbeff764147449bbcbf1fa2ef1877e3",
        "intervals_id": "46050",
        "strava_id": "g27390582",
    },
    "New Balance More 5": {
        "canonical": "New Balance More 5",
        "garmin_uuid": "5ed712903bbe401a8ed10a1412087f3e",
        "intervals_id": "45167",
        "strava_id": "g27102433",
    },
    "Under Armour Infinite Elite 2": {
        "canonical": "Under Armour Infinite Elite 2",
        "garmin_uuid": "bc5ffd705ca64197a4385ebe6c21ec6b",
        "intervals_id": "39316",
        "strava_id": "g25057367",
    },
}

# Aliases que mandan los menús del Atajo (versión corta) → canonical en GEAR
ALIASES: dict[str, str] = {
    "NB More v5": "New Balance More 5",
    "New Balance More v5": "New Balance More 5",
    "Under Armour Elite 2": "Under Armour Infinite Elite 2",
    "UA Elite 2": "Under Armour Infinite Elite 2",
    "Boston 13": "Adidas Boston 13",
}


def get(canonical_name: str) -> GearEntry | None:
    if canonical_name in GEAR:
        return GEAR[canonical_name]
    aliased = ALIASES.get(canonical_name)
    if aliased:
        return GEAR.get(aliased)
    return None
