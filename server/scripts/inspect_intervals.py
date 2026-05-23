"""Inspect an intervals.icu activity by ID.

Usage:
    python inspect_intervals.py <activity_id>
    # e.g. python inspect_intervals.py i123456789

Reads INTERVALS_API_KEY from /etc/runsync.env or the environment.
"""
import os
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("usage: python inspect_intervals.py <activity_id>", file=sys.stderr)
    sys.exit(2)
activity_id = sys.argv[1]

env_path = Path("/etc/runsync.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import requests

auth = ("API_KEY", os.environ["INTERVALS_API_KEY"])
r = requests.get(f"https://intervals.icu/api/v1/activity/{activity_id}",
                 auth=auth, timeout=15)
print("status:", r.status_code)
d = r.json()
for k in ["id", "name", "type", "gear", "gear_id", "tags", "description",
          "start_date_local"]:
    if k in d:
        print(f"  {k}={d[k]!r}")
print("--- all top-level keys ---")
print(", ".join(sorted(d.keys())))
