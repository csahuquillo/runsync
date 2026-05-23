# Troubleshooting

Common pitfalls and how to diagnose them.

📖 **[Leer en español](troubleshooting.es.md)**

## The Shortcut shows ❌ after running

**Step 1:** add a `Show Contents of URL` action temporarily right after the HTTP request to see the full JSON. Re-run the Shortcut and read the response.

**Step 2:** look at `results.<connector>.error` for the connector(s) with `ok: false`.

| Error | Cause | Fix |
|---|---|---|
| `Unauthorized` | Wrong or missing Bearer token | Check the `Authorization` header in the Shortcut matches `Bearer <RUNSYNC_TOKEN>` in `/etc/runsync.env` |
| `unknown gear: <name>` | The shoe name isn't in `gear_map.py` | Add it to `GEAR` or to `ALIASES` |
| `no run found for today` | The platform doesn't see any running activity today yet | Wait for Garmin/Strava to finish syncing your watch, or check that you ran today |
| `HTTP 400` from intervals.icu | Body shape wrong | Check `connectors.intervals_sync` is using `{"gear": {"id": ...}}` not `{"gear_id": ...}` |
| `AttributeError: 'coroutine' object has no attribute 'id'` | Telethon called sync inside FastAPI's event loop | Make sure `connectors.telegram_send_photo` is called via `await asyncio.to_thread(...)` |

## The Shortcut shows ✅ but the platforms didn't change

- **Strava:** check that the Strava activity from today actually has `sport_type=Run` or `TrailRun`. If you logged it as e.g. `Workout`, the connector skips it. Open the activity, click *Edit*, change type to "Run".
- **Garmin:** the renamed activity might be older than today. Garmin's "today" depends on the device timezone — if you traveled, this can drift.
- **intervals.icu:** check that the activity exists today (it pulls from Strava ~2 minutes after a Strava upload). If intervals doesn't have it yet, the connector returns "no run found".

## The Shortcut crashes / hangs

- Most often: the image is too big. iOS Shortcuts has memory limits. A Bevel image is normally <2 MB, but if you have a huge wallpaper as input, base64 encoding can exceed the limit.
- Workaround: add a `Resize Image` action before `Encode Base64`, target max 1500 px width.

## `/sync-workout` returns 401 Unauthorized

The Bearer token in the Shortcut's header doesn't match `RUNSYNC_TOKEN` in `/etc/runsync.env`. Common causes:
- You changed the token on the server and didn't update the Shortcut.
- Extra space in the header value (e.g. `Bearer  abc` with two spaces).
- The header name is wrong (e.g. `authorization` lowercase is OK, but `Auth` is not).

Check the server's actual token (don't print it):
```bash
sudo grep ^RUNSYNC_TOKEN= /etc/runsync.env | wc -c   # gives length
```

And compare with the length of what's in the Shortcut.

## Telegram doesn't arrive

- Check `skip_telegram` in the Shortcut's body. If it's `true`, that's by design.
- Check `TELEGRAM_CHAT_ID` in `/etc/runsync.env` has the correct IDs separated by commas. Group IDs are negative numbers starting with `-100` (supergroups/channels).
- Check the Telethon session is still authenticated:
  ```bash
  sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli whoami
  ```
  If it says `NO_SESSION`, rebootstrap with `send-code` + `sign-in`.

## Garmin login keeps asking for MFA

The Garmin tokenstore expires periodically. Re-bootstrap:
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli send-code
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli sign-in 123456
```

If it keeps failing, the password might have changed or Garmin might have blocked the IP after too many attempts. Wait a bit and retry.

## How to inspect what `/sync-workout` is receiving

The `_validation_handler` in `main.py` logs every 422 with full detail. For successful requests too, `main.py` logs `sync-workout received: ...` with all parsed fields.

```bash
sudo journalctl -u runsync.service -f
```

For a raw echo without auth:
```bash
RUNSYNC_URL=https://api.your-domain.com scripts/check-debug-form.sh
```

## Rollback after a bad deploy

```bash
ls -lt /opt/runsync/app/main.py.bak.* | head -3
sudo cp /opt/runsync/app/main.py.bak.<epoch> /opt/runsync/app/main.py
sudo systemctl restart runsync.service
```

Each `scripts/deploy.sh` invocation makes a backup. They accumulate; clean them periodically:
```bash
ls -1t /opt/runsync/app/*.bak.* | tail -n +10 | xargs sudo rm
```
