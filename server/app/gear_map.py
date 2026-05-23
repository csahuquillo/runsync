"""
Canonical mapping of running shoes to per-platform IDs.

Each shoe has a `canonical` name and the IDs that each platform uses to identify
the gear. ALIASES lets the iOS Shortcut send shorter names (e.g. "NB More v5")
that resolve to the canonical entry.

HOW TO POPULATE THIS FILE
=========================

For each pair of shoes you want to track you need three identifiers — one per
platform. None of them are secrets, but they ARE specific to your accounts.

- garmin_uuid:
    Run `python -m app.garmin_cli list-gear` on the server (after Garmin login).
    Each entry shows a `uuid` field — paste that here.

- intervals_id:
    Go to intervals.icu → Settings → Equipment, click the shoe, the URL
    will be something like .../settings/equipment/12345 → use that number
    as a string ("12345").

- strava_id:
    Go to strava.com/settings/gear, click the shoe, the URL will be
    .../gear/g99999999 → copy the WHOLE thing including the leading "g".

The values committed to git in this template are PLACEHOLDERS — replace them
with your own before deploying.
"""

from typing import TypedDict


class GearEntry(TypedDict, total=False):
    canonical: str
    garmin_uuid: str
    intervals_id: str
    strava_id: str


# Replace the placeholder values below with the IDs from your own accounts.
# See module docstring for instructions.
GEAR: dict[str, GearEntry] = {
    "Example Shoe A": {
        "canonical": "Example Shoe A",
        "garmin_uuid": "REPLACE_WITH_GARMIN_UUID",
        "intervals_id": "REPLACE_WITH_INTERVALS_ID",
        "strava_id": "gREPLACE_WITH_STRAVA_ID",
    },
    "Example Shoe B": {
        "canonical": "Example Shoe B",
        "garmin_uuid": "REPLACE_WITH_GARMIN_UUID",
        "intervals_id": "REPLACE_WITH_INTERVALS_ID",
        "strava_id": "gREPLACE_WITH_STRAVA_ID",
    },
}

# Optional: short names used in the iOS Shortcut menu → canonical name in GEAR.
# Useful so you can keep the menu compact ("UA Elite 2") while the canonical
# entry keeps the full model name.
ALIASES: dict[str, str] = {
    # "UA Elite 2": "Example Shoe B",
}


def get(canonical_name: str) -> GearEntry | None:
    if canonical_name in GEAR:
        return GEAR[canonical_name]
    aliased = ALIASES.get(canonical_name)
    if aliased:
        return GEAR.get(aliased)
    return None
