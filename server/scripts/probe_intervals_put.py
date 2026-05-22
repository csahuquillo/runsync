import os, json
from pathlib import Path
for line in Path("/etc/runsync.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
import requests

auth = ("API_KEY", os.environ["INTERVALS_API_KEY"])
url = "https://intervals.icu/api/v1/activity/i150530805"
hdr = {"Content-Type": "application/json"}

# Target: Adidas Boston 13 = intervals_id 46050
# Tags to set: Aeróbico, Base

bodies = [
    ("gear_id+tags_list", {"gear_id": "46050", "tags": ["Aeróbico", "Base"]}),
    ("gear_obj+tags_csv", {"gear": {"id": "46050"}, "tags": "Aeróbico,Base"}),
    ("gear_id+tags_csv",  {"gear_id": "46050", "tags": "Aeróbico,Base"}),
    ("gear_obj_only",     {"gear": {"id": "46050"}}),
    ("gear_id_only",      {"gear_id": "46050"}),
    ("description_only",  {"description": "#Aeróbico #Base"}),
]

for label, body in bodies:
    r = requests.put(url, auth=auth, headers=hdr, json=body, timeout=15)
    print(f"--- {label}: HTTP {r.status_code}")
    print(f"    body: {json.dumps(body, ensure_ascii=False)}")
    print(f"    resp: {r.text[:200]}")
    # Tras el PUT, leer el gear y tags actuales
    g = requests.get(url, auth=auth, timeout=15).json()
    print(f"    now: gear.id={g.get('gear',{}).get('id') if isinstance(g.get('gear'), dict) else g.get('gear')!r} tags={g.get('tags')!r} desc={(g.get('description') or '')[:60]!r}")
    print()
