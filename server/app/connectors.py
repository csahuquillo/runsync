"""
Conectores a Garmin, Strava, intervals.icu y Telegram.

Cada conector expone una función `sync(name, gear_canonical, tags)` que devuelve
un dict con `{'ok': bool, ...}` (campos adicionales: activity_id, previous_name,
error, etc.).

Telegram tiene su propia firma porque trabaja con imagen, no con actividad.

Las credenciales se leen del entorno (cargado por load_env() al importar).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from app.gear_map import get as get_gear

log = logging.getLogger("runsync.connectors")

# Cargar /etc/runsync.env al importar (idempotente)
_ENV_PATH = "/etc/runsync.env"


def _load_env() -> None:
    p = Path(_ENV_PATH)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _today_local() -> str:
    """Fecha local en formato YYYY-MM-DD."""
    return datetime.date.today().isoformat()


# ==========================================================================
# STRAVA
# ==========================================================================

_STRAVA_TOKEN_PATH = "/opt/runsync/sessions/strava.json"
_STRAVA_BASE = "https://www.strava.com/api/v3"


def _strava_load_tokens() -> dict:
    return json.loads(Path(_STRAVA_TOKEN_PATH).read_text())


def _strava_save_tokens(t: dict) -> None:
    Path(_STRAVA_TOKEN_PATH).write_text(json.dumps(t, indent=2))
    os.chmod(_STRAVA_TOKEN_PATH, 0o600)


def _strava_access_token() -> str:
    """Devuelve un access_token válido (refresca si expira en <60s)."""
    t = _strava_load_tokens()
    if t["expires_at"] > time.time() + 60:
        return t["access_token"]
    log.info("strava: refrescando access_token (expirado o casi)")
    r = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "refresh_token": t["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=15)
    r.raise_for_status()
    new = r.json()
    t.update({
        "access_token": new["access_token"],
        "refresh_token": new["refresh_token"],
        "expires_at": new["expires_at"],
        "expires_in": new.get("expires_in"),
        "token_type": new.get("token_type"),
    })
    _strava_save_tokens(t)
    return t["access_token"]


def _strava_headers() -> dict:
    return {"Authorization": f"Bearer {_strava_access_token()}"}


def _strava_find_run_today() -> dict | None:
    r = requests.get(f"{_STRAVA_BASE}/athlete/activities",
                     headers=_strava_headers(),
                     params={"per_page": 10},
                     timeout=15)
    r.raise_for_status()
    today = _today_local()
    for a in r.json():
        if a.get("sport_type") in ("Run", "TrailRun") and (a.get("start_date_local") or "").startswith(today):
            return a
    return None


def strava_sync(name: str, gear_canonical: str, tags: list[str]) -> dict:
    g = get_gear(gear_canonical)
    if not g:
        return {"ok": False, "platform": "strava", "error": f"unknown gear: {gear_canonical}"}
    act = _strava_find_run_today()
    if not act:
        return {"ok": False, "platform": "strava", "error": "no run found for today"}

    body: dict[str, Any] = {"name": name, "gear_id": g.get("strava_id")}
    # Strava expone como campos nativos algunas etiquetas; el resto queda como hashtags
    # en description. workout_type para Run: 1=Carrera, 2=Tirada larga, 3=Entrenamiento.
    # Por defecto marcamos toda carrera como Entrenamiento (3); si los tags incluyen
    # tirada larga sube a 2; si incluyen carrera/race sube a 1 (gana sobre las otras).
    STRAVA_WORKOUT_TYPE = {
        "carrera": 1, "race": 1,
        "tiradalarga": 2, "longrun": 2,
        "entrenamiento": 3, "workout": 3,
    }
    STRAVA_BOOL_FIELDS = {
        "cinta": "trainer", "treadmill": "trainer",
        "desplazamiento": "commute", "commute": "commute",
    }
    workout_type: int = 3  # default: Entrenamiento
    leftover: list[str] = []
    for t in tags:
        k = t.lower().replace(" ", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if k in STRAVA_WORKOUT_TYPE:
            wt = STRAVA_WORKOUT_TYPE[k]
            # Race (1) gana sobre Long run (2) gana sobre default. Entrenamiento (3) ya es default.
            if wt == 1 or (wt == 2 and workout_type != 1):
                workout_type = wt
        elif k in STRAVA_BOOL_FIELDS:
            body[STRAVA_BOOL_FIELDS[k]] = True
        else:
            leftover.append(t)
    body["workout_type"] = workout_type
    if leftover:
        body["description"] = " ".join(f"#{t}" for t in leftover)
    r = requests.put(f"{_STRAVA_BASE}/activities/{act['id']}",
                     headers={**_strava_headers(), "Content-Type": "application/json"},
                     json=body, timeout=15)
    if not r.ok:
        return {"ok": False, "platform": "strava", "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "activity_id": act["id"]}
    return {"ok": True, "platform": "strava", "activity_id": act["id"],
            "previous_name": act.get("name")}


# ==========================================================================
# intervals.icu
# ==========================================================================

_INTERVALS_BASE = "https://intervals.icu/api/v1"


def _intervals_auth() -> tuple[str, str]:
    return ("API_KEY", os.environ["INTERVALS_API_KEY"])


def _intervals_find_run_today() -> dict | None:
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    today = _today_local()
    r = requests.get(f"{_INTERVALS_BASE}/athlete/{athlete_id}/activities",
                     auth=_intervals_auth(),
                     params={"oldest": today, "limit": 10},
                     timeout=15)
    r.raise_for_status()
    for a in r.json():
        if a.get("type") == "Run" and (a.get("start_date_local") or "").startswith(today):
            return a
    return None


def intervals_sync(name: str, gear_canonical: str, tags: list[str]) -> dict:
    g = get_gear(gear_canonical)
    if not g:
        return {"ok": False, "platform": "intervals", "error": f"unknown gear: {gear_canonical}"}
    act = _intervals_find_run_today()
    if not act:
        return {"ok": False, "platform": "intervals", "error": "no run found for today"}

    # intervals.icu: el campo es "gear" (string id), no "gear_id"
    body: dict[str, Any] = {"name": name, "gear": {"id": g.get("intervals_id")}}
    if tags:
        # tags es un Set<String> nativo en intervals.icu; mandarlos como lista
        # los pinta como etiquetas reales, no como hashtags en la descripción.
        body["tags"] = list(tags)
    r = requests.put(f"{_INTERVALS_BASE}/activity/{act['id']}",
                     auth=_intervals_auth(),
                     headers={"Content-Type": "application/json"},
                     json=body, timeout=15)
    if not r.ok:
        return {"ok": False, "platform": "intervals", "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "activity_id": act["id"]}
    return {"ok": True, "platform": "intervals", "activity_id": act["id"],
            "previous_name": act.get("name")}


# ==========================================================================
# GARMIN
# ==========================================================================

_GARMIN_TOKENSTORE = "/opt/runsync/sessions/garmin"


def _garmin_client():
    from garminconnect import Garmin
    api = Garmin(os.environ["GARMIN_USERNAME"], os.environ["GARMIN_PASSWORD"])
    api.login(tokenstore=_GARMIN_TOKENSTORE)
    return api


def _garmin_find_run_today(api) -> dict | None:
    acts = api.get_activities(0, 10) or []
    today = _today_local()
    for a in acts:
        if ((a.get("activityType") or {}).get("typeKey", "")).startswith("running") \
                and (a.get("startTimeLocal") or "").startswith(today):
            return a
    return None


def garmin_sync(name: str, gear_canonical: str, tags: list[str]) -> dict:
    g = get_gear(gear_canonical)
    if not g:
        return {"ok": False, "platform": "garmin", "error": f"unknown gear: {gear_canonical}"}
    try:
        api = _garmin_client()
        act = _garmin_find_run_today(api)
        if not act:
            return {"ok": False, "platform": "garmin", "error": "no run found for today"}
        activity_id = act["activityId"]
        previous_name = act.get("activityName")

        # Renombrar
        api.set_activity_name(activity_id, name)

        # Cambiar gear: quitar el actual y añadir el nuevo
        current_gear = api.get_activity_gear(activity_id) or []
        for cg in current_gear:
            if cg.get("uuid") and cg["uuid"] != g["garmin_uuid"]:
                try:
                    api.remove_gear_from_activity(cg["uuid"], activity_id)
                except Exception as e:
                    log.warning("garmin: no pude quitar gear %s: %s", cg.get("uuid"), e)
        # Solo añadir si no está ya
        if not any(cg.get("uuid") == g["garmin_uuid"] for cg in current_gear):
            api.add_gear_to_activity(g["garmin_uuid"], activity_id)

        # Añadir tags en la descripción
        if tags:
            tag_text = " ".join(f"#{t}" for t in tags)
            try:
                api.client.put(
                    "connectapi",
                    f"{api.garmin_connect_activity}/{activity_id}",
                    json={
                        "activityId": activity_id,
                        "activityName": name,
                        "description": tag_text,
                    },
                    api=True,
                )
            except Exception as e:
                # No crítico, log y seguir
                log.warning("garmin: no pude poner descripción/tags: %s", e)

        return {"ok": True, "platform": "garmin", "activity_id": activity_id,
                "previous_name": previous_name}
    except Exception as e:
        return {"ok": False, "platform": "garmin", "error": f"{type(e).__name__}: {e}"}


# ==========================================================================
# TELEGRAM (Telethon, como usuario)
# ==========================================================================

_TELEGRAM_SESSION = "/opt/runsync/sessions/me"


def telegram_send_photo(image_bytes: bytes, image_filename: str | None, caption: str) -> dict:
    """Envía la imagen a uno o varios chats de Telegram.

    TELEGRAM_CHAT_ID puede ser un id o una lista separada por comas
    (p. ej. "-1001234567890,-1009876543210"). ok=True solo si llegó a todos.
    """
    try:
        from telethon.sync import TelegramClient

        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        raw_ids = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not raw_ids:
            return {"ok": False, "platform": "telegram", "error": "TELEGRAM_CHAT_ID empty"}
        chat_ids: list[int] = []
        for piece in raw_ids.split(","):
            p = piece.strip()
            if not p:
                continue
            try:
                chat_ids.append(int(p))
            except ValueError:
                return {"ok": False, "platform": "telegram",
                        "error": f"TELEGRAM_CHAT_ID inválido: {p!r}"}
        if not chat_ids:
            return {"ok": False, "platform": "telegram", "error": "no chat ids configured"}

        tmp = Path(f"/tmp/runsync_tg_{int(time.time()*1000)}_{image_filename or 'img.png'}")
        tmp.write_bytes(image_bytes)

        client = TelegramClient(_TELEGRAM_SESSION, api_id, api_hash)
        client.connect()
        try:
            if not client.is_user_authorized():
                return {"ok": False, "platform": "telegram", "error": "no_session"}
            sent: list[dict] = []
            failures: list[dict] = []
            for cid in chat_ids:
                try:
                    msg = client.send_file(cid, str(tmp), caption=caption)
                    sent.append({"chat_id": cid, "message_id": msg.id})
                except Exception as e:
                    failures.append({"chat_id": cid, "error": f"{type(e).__name__}: {e}"})
            ok = bool(sent) and not failures
            res: dict = {"ok": ok, "platform": "telegram", "sent": sent}
            if failures:
                res["failures"] = failures
            return res
        finally:
            client.disconnect()
            tmp.unlink(missing_ok=True)
    except Exception as e:
        return {"ok": False, "platform": "telegram", "error": f"{type(e).__name__}: {e}"}
