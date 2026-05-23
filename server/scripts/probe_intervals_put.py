"""Probe different body shapes for intervals.icu PUT /activity/{id}.

This script was useful for discovering that intervals expects
    {"gear": {"id": "..."}}
and not
    {"gear": "..."}
or
    {"gear_id": "..."}

Usage:
    python probe_intervals_put.py <activity_id> <intervals_gear_id>

Reads INTERVALS_API_KEY from /etc/runsync.env or the environment.
"""
import json
import os
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("usage: python probe_intervals_put.py <activity_id> <gear_id>",
          file=sys.stderr)
    sys.exit(2)
activity_id = sys.argv[1]
gear_id = sys.argv[2]

env_path = Path("/etc/runsync.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import requests

auth = ("API_KEY", os.environ["INTERVALS_API_KEY"])
url = f"https://intervals.icu/api/v1/activity/{activity_id}"
hdr = {"Content-Type": "application/json"}

bodies = [
    ("gear_id+tags_list", {"gear_id": gear_id, "tags": ["Tag1", "Tag2"]}),
    ("gear_obj+tags_csv", {"gear": {"id": gear_id}, "tags": "Tag1,Tag2"}),
    ("gear_id+tags_csv",  {"gear_id": gear_id, "tags": "Tag1,Tag2"}),
    ("gear_obj_only",     {"gear": {"id": gear_id}}),
    ("gear_id_only",      {"gear_id": gear_id}),
    ("description_only",  {"description": "#Tag1 #Tag2"}),
]

for label, body in bodies:
    r = requests.put(url, auth=auth, headers=hdr, json=body, timeout=15)
    print(f"--- {label}: HTTP {r.status_code}")
    print(f"    body: {json.dumps(body, ensure_ascii=False)}")
    print(f"    resp: {r.text[:200]}")
    g = requests.get(url, auth=auth, timeout=15).json()
    gear_now = g.get("gear", {}).get("id") if isinstance(g.get("gear"), dict) else g.get("gear")
    print(f"    now: gear.id={gear_now!r} tags={g.get('tags')!r} "
          f"desc={(g.get('description') or '')[:60]!r}")
    print()
