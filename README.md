# runsync

> **Sync one workout to Strava, intervals.icu, Garmin Connect, and Telegram with a single tap from your iPhone's share sheet.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

📖 **[Leer en español](README.es.md)**

## The problem

After every run you repeat the same chore on four different platforms:

- Rename the activity on **Strava** and pick which shoe you wore.
- Same on **intervals.icu**.
- Same on **Garmin Connect**.
- Export a clean image from **[Bevel](https://bevel.fit/)** and post it to your Telegram running group with a caption like *"12 km — #Z2 #Base"*.

That's five minutes after every run. Multiply by 4–5 runs a week.

## The solution

A single iOS Shortcut + a tiny Python backend. From the share sheet on the Bevel image:

1. Tap the Shortcut.
2. Pick the **workout name** (menu with your common ones + "other → type").
3. Pick the **shoes** (menu with your active pairs).
4. Pick the **tags** (multi-select: Z2, Base, Tempo…).
5. Done → the backend renames today's activity on the three platforms, sets the correct gear, puts hashtags in the description, and sends the photo + caption to whatever Telegram chats you want.

Total: ~10 seconds.

## Is this for you?

✅ **Yes** if:
- You run regularly and upload to Strava + Garmin + (intervals.icu or similar).
- You use or want to use [Bevel](https://bevel.fit/) to generate clean workout images.
- You have an iPhone (iPad/Mac Shortcuts also work).
- You can host a small backend on a VPS (€4/mo on any host) or already have one.
- You can follow technical instructions (no need to be a programmer, but you should be comfortable reading commands).

❌ **No** if:
- You want a serverless app → this requires hosting the backend yourself.
- You're on Android only → the Shortcut is iOS-native.
- You only use one platform → a one-off script would be enough.

## What you see (demo)

```
Bevel exports image ─→ iOS share sheet ─→ Run the Shortcut
                                                 │
                                ┌────────────────┘
                                ▼
                    ┌──────────────────────┐
                    │ Menu: Workout name   │   "12 km", "60s", "Long run", "Other…"
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Menu: Shoes          │   active pairs configured in your menus
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │ List: Tags           │   ☑ Aerobic  ☑ Base  ☑ Z2
                    └──────────┬───────────┘
                               ▼ (encodes image to base64, POSTs JSON with Bearer)
                    ┌──────────────────────┐
                    │ api.your-domain.com  │
                    │  FastAPI / Python    │
                    └──────────┬───────────┘
                               │
                ┌──────┬───────┼───────┬─────────────┐
                ▼      ▼       ▼       ▼             ▼
             Strava intervals Garmin Telegram   (Runalyze
             rename rename    rename sends photo auto-imports
             +gear  +gear     +gear  to N chats  from Garmin
             +tags  +tags     +tags  + caption)  /Strava)
```

Final notification on the iPhone: `runsync ✅` or `runsync ❌` if anything failed.

## Architecture

```
┌─────────────────┐     POST JSON     ┌──────────────────────────┐
│  iOS Shortcut   │  ───────────────▶ │  Your domain (HTTPS)     │
│  Sincronizar    │   image_b64,      │  FastAPI + uvicorn       │
│  Entreno        │   name, shoes,    │  behind nginx            │
└─────────────────┘   tags, Bearer    └──────────┬───────────────┘
                                                 │
                  ┌──────────────────────────────┼─────────────────────────┐
                  ▼                ▼             ▼             ▼           ▼
              Strava API    intervals.icu    Garmin       Telethon     Runalyze*
              OAuth2        API key auth     Connect      (user        (auto-import
              token         (PUT activity)   (garmin-     session)     from Garmin
              refresh                        connect)                  or Strava)
```

- **iOS Shortcuts** (not committed to the repo, see [docs/atajo-setup.md](docs/atajo-setup.md) to rebuild it).
- **Python 3.12 backend** with FastAPI/uvicorn, launched by systemd.
- **TLS** via nginx + Let's Encrypt.
- **Persistent sessions** per service: Strava OAuth auto-refreshes, Garmin saves tokens, Telegram uses a Telethon session (user account, not bot — messages appear from your own user).

`*` Runalyze has no direct connector: it picks up changes when it re-imports from Garmin or Strava.

## Cost vs. savings

| Up-front cost | Estimated time |
|---|---|
| VPS + domain + nginx + TLS | 30 min if you already have it; 1-2 h from scratch |
| Strava OAuth setup | 10 min |
| intervals.icu API key | 2 min |
| Garmin MFA-aware login bootstrap | 5 min |
| Telegram session bootstrap | 5 min |
| Build the iOS Shortcut following [the guide](docs/atajo-setup.md) | 30-45 min |
| **Total** | **~2-3 hours** |

After that: **~10 seconds per workout** vs. ~5 minutes by hand. Paid back in a week.

## Security

This project asks you to host a server that holds credentials for Strava, Garmin, Telegram, and intervals.icu. Before going further, make sure you understand and apply the following:

- **All endpoints that modify state are protected by a Bearer token** (`RUNSYNC_TOKEN`). Generate a long random string (`openssl rand -hex 32`) and use it as your token. Don't reuse passwords.
- **TLS is mandatory.** Don't run this on plain HTTP — your Bearer token would travel in plain text. Use Let's Encrypt (free).
- **`/etc/runsync.env` must be `chmod 600` and owned by the `runsync` user.** systemd reads it on boot.
- **Never commit your real `.env`**, your Garmin tokenstore, your Strava tokens, or your Telethon session file. The `.gitignore` already excludes these patterns, but double-check.
- **The exported `.shortcut` file contains your Bearer token embedded.** Don't share it. Each user rebuilds the Shortcut on their device.
- **Strava gear IDs and Garmin UUIDs in `gear_map.py` are specific to your accounts.** The repo ships placeholders; replace them locally only.
- **The backend exposes a small attack surface.** Endpoints without auth (`/health`, `/debug-form`, `/strava/callback`, `/shortcut`) only echo or implement OAuth; review them yourself before deploying publicly.
- **Run as an unprivileged user** (`runsync`). The shipped systemd unit uses `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=true`.
- **No rate limiting is shipped.** If you're nervous, put runsync behind nginx or Cloudflare with basic rate limiting on `/sync-workout` (the deploy doc shows how).

If any of these worry you, host on a private network (VPN-only access) or skip the public deploy and run it locally on a Raspberry Pi at home with a private DNS.

## Quick start

1. **Clone and read the docs.**
   ```bash
   git clone https://github.com/csahuquillo/runsync.git
   cd runsync
   ```
2. **Deploy the backend** following [docs/deploy.md](docs/deploy.md). You need a Linux VPS with Python 3.12, nginx, and a domain.
3. **Configure `/etc/runsync.env`** with your credentials — template at [`runsync.env.example`](runsync.env.example).
4. **Interactive bootstrap** of Strava (browser OAuth), Garmin (MFA email), and Telegram (SMS code). See [docs/deploy.md § Session bootstrap](docs/deploy.md#5-session-bootstrap).
5. **Replace the placeholder gear** in `server/app/gear_map.py` with your real shoe IDs. See the file's docstring for how to obtain each ID.
6. **Build the Shortcut on your iPhone** following [docs/atajo-setup.md](docs/atajo-setup.md). ~40 minutes with the step-by-step guide.
7. **Test** with `curl https://your-domain.com/health` from another machine, then run the Shortcut on a Bevel image.

## Endpoints

| Method | Path             | Auth        | Purpose |
|--------|------------------|-------------|---------|
| GET    | `/health`        | —           | Trivial liveness probe |
| POST   | `/debug-form`    | —           | Echo. Accepts multipart or JSON; returns what it received (useful to debug the Shortcut) |
| POST   | `/sync-workout`  | Bearer      | The endpoint the Shortcut hits |
| GET    | `/strava/callback` | —         | Strava OAuth callback |
| GET    | `/shortcut`      | —           | Serves the `.shortcut` file if you uploaded one |

### `/sync-workout` request body

```jsonc
POST /sync-workout
Authorization: Bearer <RUNSYNC_TOKEN>
Content-Type: application/json

{
  "name":           "12 km",                  // becomes the activity name
  "shoes":          "Adidas Boston 13",       // canonical or alias (see gear_map.py)
  "tags":           "Aerobic,Base,Z2",        // CSV; each token becomes a #hashtag
  "image_filename": "Image.png",
  "image_b64":      "iVBORw0KGgo...",         // base64-encoded PNG/JPEG
  "skip_telegram":  "false"                   // optional; default true (do not send)
}
```

Response:

```json
{
  "ok": true,
  "results": {
    "strava":    { "ok": true, "activity_id": 1234567890, ... },
    "intervals": { "ok": true, "activity_id": "i123456789", ... },
    "garmin":    { "ok": true, "activity_id": 9876543210, ... },
    "telegram":  { "ok": true, "sent": [{...},{...}] }
  }
}
```

Global `ok` is `true` only if all four connectors succeeded.

## Repository layout

```
runsync/
├── README.md               ← this file (English)
├── README.es.md            ← Spanish translation
├── AGENTS.md               ← conventions for contributors / agents
├── ROADMAP.md              ← done / pending / known bugs
├── LICENSE                 ← MIT
├── runsync.env.example     ← template .env, no secrets
├── docs/
│   ├── architecture.md     ← detailed architecture + data flow
│   ├── architecture.es.md
│   ├── deploy.md           ← full deployment guide
│   ├── deploy.es.md
│   ├── atajo-setup.md      ← build the iOS Shortcut step by step
│   ├── atajo-setup.es.md
│   ├── troubleshooting.md  ← common pitfalls
│   └── troubleshooting.es.md
├── server/
│   ├── app/                ← FastAPI code (main, connectors, gear_map)
│   ├── requirements.txt    ← runtime deps
│   ├── systemd/
│   │   └── runsync.service ← systemd unit
│   └── scripts/            ← diagnostic helpers (not runtime)
└── scripts/
    ├── check-debug-form.sh ← test multipart against /debug-form
    └── deploy.sh           ← upload changes to the server via AWS SSM
```

## FAQ

### Why not Strava webhooks → IFTTT → everything else?
Strava webhooks land ~a minute after the activity uploads and don't let you pick gear/tags per workout. Here you decide in the moment.

### Why Bevel and not the Strava app?
Bevel exports a clean image ready for social. But you can use any image source — the Shortcut just needs an image input.

### What if I don't use Strava / intervals / etc.?
The backend is organized so each connector is independent. Delete the one you don't want in `connectors.py` and remove the call in `main.py`. PRs welcome for new platforms (Coros, Polar Flow, Suunto…).

### Why JSON+base64 instead of multipart?
iOS Shortcuts sends multipart inconsistently. The image arrived as plain text and broke the parser. JSON+base64 is 33% heavier but works 100% of the time. See [docs/architecture.md](docs/architecture.md).

### WhatsApp?
WhatsApp has no decent API for personal groups. The reliable way: add a `Share` action at the end of the iOS Shortcut (opens the system share sheet so you pick the recipient manually, 1-2 taps). More details in [ROADMAP.md](ROADMAP.md).

### Can I use only Telegram, without Garmin/Strava/intervals?
Yes — comment out the connector calls in `main.py:sync_workout()`. Telegram has a `skip_telegram` flag to toggle on/off per request.

### How much does it cost?
Only the VPS and domain. ~€5/month at any host (Hetzner, OVH, AWS Lightsail, Digital Ocean…). Strava, intervals, Garmin, Telegram are free for personal use.

## Known limitations

- **iOS only** (the Shortcut). The backend is HTTP-agnostic — you can POST from anywhere.
- **One primary sport**: today it filters for `Run`/`TrailRun`. For bike or trail you'd edit the filters in `connectors.py`.
- **No idempotency**: if you run the Shortcut twice for the same activity, it renames twice and sends twice to Telegram. Tracked in ROADMAP.
- **Manual session bootstrap** for Garmin (MFA email) and Telegram (SMS). Once at the start; not repeated unless the session is invalidated.

More detail in [ROADMAP.md](ROADMAP.md).

## Contributing

PRs welcome, especially:
- Connectors for other platforms (Coros, Suunto, Polar Flow, direct Runalyze API).
- Tests.
- Basic CI (lint + tests + deploy via OIDC).
- Support for cycling / trail / swim.

Read [AGENTS.md](AGENTS.md) before sending a PR — project conventions.

## License

[MIT](LICENSE) © 2026 Carlos Sahuquillo

---

If this saves you time, a ⭐ on the repo makes my day.
