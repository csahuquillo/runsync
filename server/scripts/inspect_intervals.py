import os
from pathlib import Path
for line in Path("/etc/runsync.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
import requests
auth = ("API_KEY", os.environ["INTERVALS_API_KEY"])
r = requests.get("https://intervals.icu/api/v1/activity/i150530805", auth=auth, timeout=15)
print("status:", r.status_code)
d = r.json()
for k in ["id","name","type","gear","gear_id","tags","description","start_date_local"]:
    if k in d:
        print(f"  {k}={d[k]!r}")
print("--- all top-level keys ---")
print(", ".join(sorted(d.keys())))
