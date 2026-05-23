# AGENTS.md

Conventions for humans and agents contributing to this repo.

## What this is

Python (FastAPI) API that receives a POST from the iOS Shortcut "Sincronizar Entreno" and propagates the workout to Strava, intervals.icu, Garmin Connect, and Telegram. Designed to run as a small backend on a Linux VPS / EC2 / VM.

## Inviolable rules

1. **Never print the contents of `/etc/runsync.env`** or any other file containing credentials. If you need to read one specific value, use `grep ^KEY= /etc/runsync.env`. Never `cat` the whole file.
2. **The `.env` lives only on the server.** Don't replicate locally and don't commit it. Modify via targeted `sed -i`.
3. **No SSH credentials, no IP addresses, no real domain names in commits.** Use placeholders (`api.example.com`, `i-0XXXXXXXXXXXXXXXX`, etc.).
4. **Back up before modifying server files**: `cp X X.bak.$(date +%s)`.
5. **Validate Python syntax** before `systemctl restart`: `python -c "import ast; ast.parse(open('...').read())"`.
6. **Never commit**: `.env`, `sessions/`, `*.session`, `strava.json`, `*.shortcut` (the exported iOS Shortcut contains your Bearer token embedded), backups `*.bak.*`.
7. **The iOS Shortcut itself is not versioned in this repo.** Its structure is documented in `docs/atajo-setup.md` / `docs/atajo-setup.es.md`. Anyone who wants to use runsync rebuilds the Shortcut on their device with their own Bearer token.
8. **Treat the `gear_map.py` committed in the repo as a template.** Replace placeholders with your real IDs locally; don't push real IDs back upstream unless you want them public (your Strava gear IDs and Garmin UUIDs are personal data, even if technically discoverable).

## Code conventions

- Python 3.12. Type hints where they help. `from __future__ import annotations` at the top.
- FastAPI endpoints: always return JSON-serializable `dict`; avoid raw `Response` unless necessary.
- Connector failures: never raise `HTTPException 500` to the client — capture and return `{"ok": false, "platform": "...", "error": "..."}` inside the per-connector results dict. The Shortcut client prefers a 200 with details over a 500.
- Logging: `log.info(...)` with `%r` formatters. `log.warning` for non-critical failures. `log.exception` only for genuinely unexpected exceptions.

## Change workflow

For any server-side code change:

1. Edit locally in `server/app/...`.
2. Validate: `python -m py_compile server/app/*.py` (or `ast.parse`).
3. Upload via SSM with base64 + atomic `mv` (see pattern in `docs/deploy.md`).
4. `systemctl restart runsync.service && systemctl is-active runsync.service`.
5. Test against `/debug-form` or `/sync-workout` before claiming "done".

For changes to `gear_map.py` (adding a shoe): first run `python -m app.garmin_cli list-gear` on the server to get the Garmin UUID; the Strava ID is in the URL at `https://www.strava.com/gear/<id>`; the intervals.icu ID is in the equipment URL there.

## Structure

- `server/app/main.py`: HTTP endpoints. Dual parsing (JSON / multipart) in `_parse_workout_body`.
- `server/app/connectors.py`: one `<platform>_sync(name, gear_canonical, tags)` function per platform + `telegram_send_photo(image_bytes, filename, caption)`.
- `server/app/gear_map.py`: canonical table + aliases for the short menu names in the Shortcut.
- `server/app/*_cli.py`: authentication helpers (the API does not run them; used for manual bootstrap of sessions).

## Where NOT to look

- `server/scripts/`: one-off diagnostic utilities (probes for intervals.icu, listing Telegram dialogs). Not part of runtime, may be stale.

## Deploy

- No CI/CD shipped. Deploys are manual via SSM with the base64 + atomic-`mv` pattern documented in `docs/deploy.md`.
- TLS and domain are user-specific; the repo never references a specific domain.

## When something breaks in production

Logs: `sudo journalctl -u runsync.service -n 100 --no-pager`. The `_validation_handler` in `main.py` already logs detailed info on 422 errors with the form payload received.

The `/debug-form` endpoint is the first stop when diagnosing Shortcut problems — it echoes whatever is sent and lets you distinguish client bugs from server bugs.
