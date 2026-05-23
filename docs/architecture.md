# Architecture

📖 **[Leer en español](architecture.es.md)**

## Components

| Component | Where it lives | Stack |
|---|---|---|
| iOS Shortcut "Sincronizar Entreno" | iPhone | iOS Shortcuts |
| Reverse proxy + TLS | VPS | nginx + Let's Encrypt |
| runsync API | VPS `/opt/runsync/` | FastAPI + uvicorn (systemd) |
| Persistent sessions | VPS `/opt/runsync/sessions/` | Strava OAuth tokens, Garmin tokenstore, Telethon session |
| DNS | Your DNS provider | `api.your-domain.com` → server's IP |

## Data flow

```
┌─────────────────────────┐
│ iPhone — Bevel          │
│ (exports workout image) │
└──────────┬──────────────┘
           │ iOS share sheet
           ▼
┌─────────────────────────┐
│ iOS Shortcut            │
│ - workout name menu     │
│ - shoes menu            │
│ - tags menu (multi)     │
│ - encodes image base64  │
└──────────┬──────────────┘
           │ POST JSON
           │ Authorization: Bearer ...
           ▼
┌─────────────────────────┐
│ nginx (TLS)             │
│ api.your-domain.com     │
└──────────┬──────────────┘
           │ proxy_pass http://127.0.0.1:8000
           ▼
┌─────────────────────────────────────────────────┐
│ FastAPI app.main:app                            │
│                                                 │
│ /sync-workout:                                  │
│   1. _require_auth() — validates Bearer         │
│   2. _parse_workout_body() — JSON or multipart  │
│   3. connectors.strava_sync()                   │
│   4. connectors.intervals_sync()                │
│   5. connectors.garmin_sync()                   │
│   6. await asyncio.to_thread(                   │
│        connectors.telegram_send_photo)          │
│   7. returns dict with per-connector results    │
└─────────────────────────────────────────────────┘
```

## How each connector finds today's activity

| Platform | Strategy | Endpoint |
|---|---|---|
| Strava | List last 10 activities, filter `sport_type ∈ {Run, TrailRun}` whose `start_date_local` starts with today's local date | `GET /athlete/activities?per_page=10` |
| intervals.icu | List activities with `oldest=today` and `limit=10`, filter `type == "Run"` | `GET /athlete/{id}/activities` |
| Garmin Connect | `api.get_activities(0, 10)`, filter `activityType.typeKey` starting with `running` and today's date | `garminconnect` library |

If no activity is found for today, the connector returns `{"ok": false, "error": "no run found for today"}` and touches nothing — safe failure.

## Gear model

```
gear_map.py
├── GEAR (dict)
│   └── "Adidas Boston 13" → { strava_id, intervals_id, garmin_uuid }
└── ALIASES (dict)
    └── "NB More v5" → "New Balance More 5"
```

`gear_map.get(name)` resolves direct matches or aliases. The IDs are **not invented** — you have to grab them from each platform:

- **Strava**: `https://www.strava.com/gear/<id>` (URL when managing the shoe).
- **intervals.icu**: in `Settings → Equipment`, the ID is in the URL when editing.
- **Garmin**: `garmin_cli list-gear` run on the server returns them.

## Persistent sessions

| Service | File | Bootstrap |
|---|---|---|
| Strava | `/opt/runsync/sessions/strava.json` | OAuth code via `/strava/callback`, auto-refresh |
| Garmin | `/opt/runsync/sessions/garmin/` (tokenstore) | `garmin_cli send-code` + `sign-in <code>` (email MFA) |
| Telegram | `/opt/runsync/sessions/me.session` | `telegram_cli send-code <phone>` + `sign-in <code>` + optional `password <2fa>` |

All persist across restarts. Strava auto-refreshes; Garmin renews tokens when they expire; Telethon keeps the session alive indefinitely unless manually invalidated.

## Why JSON + base64 instead of multipart

iOS Shortcuts has a known issue sending multipart/form-data: the variable picker for the `image` field doesn't reliably pick file variables, and when you use "Shortcut Input" directly, the request body becomes `application/x-www-form-urlencoded` with the image base64-stuffed as text (broken).

The reliable workaround is:
1. Add an "Obtener archivo de tipo public.image" step in the Shortcut to coerce the input to a real file.
2. Add a "Codificar Base64" step to get a clean text representation.
3. Send the whole payload as JSON with `image_b64` as a regular text field.

The backend accepts both formats (JSON and multipart) — multipart is kept for compatibility and manual `curl` testing.

## Security model

- No SSH to the server in the recommended setup — access only via AWS Systems Manager (SSM).
- `/etc/runsync.env` has `mode 600` owned by `runsync:runsync`. systemd loads it as `EnvironmentFile`.
- Single `RUNSYNC_TOKEN` shared between server and Shortcut.
- Unauthenticated endpoints: `/health`, `/debug-form` (echo, doesn't propagate), `/strava/callback` (validated by OAuth state), `/shortcut`.
- No rate limiting on the API itself today (recommended to add at nginx level — see [deploy.md](deploy.md)).
- Run as unprivileged `runsync` user under systemd with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=true`.
