"""
runsync — sincronizador de entrenamientos.

Recibe POST desde el Atajo de iOS con:
- name: nombre del entrenamiento
- shoes: nombre canónico de la zapatilla
- tags: lista de tags separada por comas
- image: imagen exportada desde Bevel

Soporta dos formatos de body:
- multipart/form-data con campo `image` como archivo (el original)
- application/json con campos `image_b64` (base64) y opcional `image_filename`
  (necesario porque iOS Shortcuts no manda multipart de forma fiable)

Endpoints:
- GET  /health         → salud, no requiere auth
- POST /debug-form     → eco, sin auth
- POST /sync-workout   → procesa un entreno, requiere Bearer token
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("runsync")

API_TOKEN = os.environ.get("RUNSYNC_TOKEN")
if not API_TOKEN:
    log.warning("RUNSYNC_TOKEN no configurado — las requests autenticadas fallarán")

app = FastAPI(title="runsync", version="0.2.0")


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    """Log detallado de los errores 422 para diagnosticar problemas del Atajo."""
    ctype = request.headers.get("content-type", "(none)")
    try:
        form = await request.form()
        keys = list(form.keys())
        details = {}
        for k, v in form.items():
            try:
                if hasattr(v, "filename"):
                    details[k] = f"<file filename={v.filename!r}>"
                else:
                    sv = str(v)
                    details[k] = sv[:60] + ("..." if len(sv) > 60 else "")
            except Exception:
                details[k] = "<unreadable>"
    except Exception as e:
        keys, details = None, f"could_not_parse: {e}"
    log.warning(
        "VALIDATION ERROR | path=%s content-type=%s | form_keys=%s | form_preview=%s | errors=%s",
        request.url.path, ctype, keys, details, exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "form_keys_seen": keys})


@app.get("/shortcut")
def get_shortcut() -> FileResponse:
    return FileResponse(
        "/opt/runsync/Sincronizar_Entreno.shortcut",
        media_type="application/octet-stream",
        filename="Sincronizar_Entreno.shortcut",
    )


def _truthy(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "si", "sí", "on"}


# --- Body parsing ------------------------------------------------------------

async def _parse_workout_body(request: Request) -> dict:
    """Parsea el body del Atajo en multipart o JSON, devuelve dict normalizado:
    {name, shoes, tags, image_bytes (bytes), image_filename (str|None)}
    Lanza HTTPException(422) si faltan name/shoes.
    """
    ctype = (request.headers.get("content-type") or "").lower()

    if ctype.startswith("application/json"):
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {e}")
        name = (data.get("name") or "").strip()
        shoes = (data.get("shoes") or "").strip()
        tags = data.get("tags") or ""
        image_b64 = data.get("image_b64") or ""
        image_filename = data.get("image_filename") or "image.bin"
        skip_telegram = _truthy(data.get("skip_telegram")) if "skip_telegram" in data else True
        if not name or not shoes:
            raise HTTPException(status_code=422, detail="name and shoes are required")
        if image_b64:
            try:
                img_bytes = base64.b64decode(image_b64, validate=False)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"image_b64 decode error: {e}")
        else:
            img_bytes = b""
            image_filename = None
        return {
            "name": name,
            "shoes": shoes,
            "tags": str(tags),
            "image_bytes": img_bytes,
            "image_filename": image_filename,
            "skip_telegram": skip_telegram,
        }

    # multipart/form-data o x-www-form-urlencoded
    form = await request.form()
    name = (form.get("name") or "").strip()
    shoes = (form.get("shoes") or "").strip()
    tags = form.get("tags") or ""
    skip_telegram = _truthy(form.get("skip_telegram")) if "skip_telegram" in form else True
    if not name or not shoes:
        raise HTTPException(status_code=422, detail="name and shoes are required")
    img_bytes = b""
    image_filename = None
    image = form.get("image")
    if image is not None and hasattr(image, "read"):
        img_bytes = await image.read()
        image_filename = image.filename
    return {
        "name": name,
        "shoes": shoes,
        "tags": str(tags),
        "image_bytes": img_bytes,
        "image_filename": image_filename,
        "skip_telegram": skip_telegram,
    }


@app.post("/debug-form")
async def debug_form(request: Request) -> dict:
    """Endpoint de debug: acepta multipart o JSON y devuelve qué llegó."""
    ctype = request.headers.get("content-type", "(none)")
    try:
        if (ctype or "").lower().startswith("application/json"):
            data = await request.json()
            items: dict = {}
            for k, v in data.items():
                if k == "image_b64" and isinstance(v, str) and v:
                    try:
                        raw = base64.b64decode(v, validate=False)
                        items["image"] = {
                            "_file": True,
                            "filename": data.get("image_filename") or "image.bin",
                            "size": len(raw),
                        }
                    except Exception as e:
                        items[k] = f"<base64_error: {e}>"
                else:
                    items[k] = v if isinstance(v, (int, float, bool)) else str(v)
            return {"ok": True, "content_type": ctype, "fields": items}

        form = await request.form()
        items = {}
        for k, v in form.items():
            if hasattr(v, "filename"):
                content = await v.read()
                items[k] = {"_file": True, "filename": v.filename, "size": len(content)}
            else:
                items[k] = str(v)
        return {"ok": True, "content_type": ctype, "fields": items}
    except Exception as e:
        return {"ok": False, "error": str(e), "content_type": ctype}


def _require_auth(authorization: Optional[str]) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="Server token not configured")
    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "runsync"}


@app.post("/sync-workout")
async def sync_workout(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    _require_auth(authorization)
    parsed = await _parse_workout_body(request)

    name = parsed["name"]
    shoes = parsed["shoes"]
    tags = parsed["tags"]
    img_bytes = parsed["image_bytes"]
    img_filename = parsed["image_filename"]

    tag_list = [t.strip() for t in re.split(r"[,\n;]+", tags) if t.strip()] if tags else []

    log.info(
        "sync-workout received: name=%r shoes=%r tags=%r image=%r (%d bytes) skip_telegram=%r ctype=%r",
        name, shoes, tag_list, img_filename, len(img_bytes), parsed.get("skip_telegram"),
        request.headers.get("content-type"),
    )

    from app import connectors

    results: dict[str, dict] = {}
    results["strava"] = connectors.strava_sync(name, shoes, tag_list)
    results["intervals"] = connectors.intervals_sync(name, shoes, tag_list)
    results["garmin"] = connectors.garmin_sync(name, shoes, tag_list)

    # Mientras se valida, Telegram se salta por defecto (el parser lo deja en True
    # si no llega la clave). Para activarlo desde el Atajo, mandar
    # "skip_telegram": "false" en el body JSON.
    if parsed.get("skip_telegram"):
        log.info("sync-workout: skip_telegram=true, no se envía a Telegram")
        results["telegram"] = {"ok": True, "platform": "telegram", "skipped": True}
    elif img_bytes:
        caption = name
        if tag_list:
            caption += "\n\n" + " ".join(f"#{t}" for t in tag_list)
        # Telethon es async pero la función connectors.* es sync (telethon.sync).
        # La metemos en un hilo para que tenga su propio event loop y no
        # colisione con el de FastAPI.
        results["telegram"] = await asyncio.to_thread(
            connectors.telegram_send_photo, img_bytes, img_filename, caption
        )
    else:
        results["telegram"] = {"ok": False, "platform": "telegram", "error": "no_image_provided"}

    all_ok = all(r.get("ok") for r in results.values())
    response = {"ok": all_ok, "results": results}
    log.info("sync-workout response: %s", json.dumps(response, default=str)[:2000])
    return response


# --- Strava OAuth ------------------------------------------------------------

STRAVA_TOKEN_PATH = "/opt/runsync/sessions/strava.json"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


@app.get("/strava/callback", response_class=HTMLResponse)
def strava_callback(
    code: Optional[str] = Query(default=None),
    scope: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> str:
    if error:
        log.warning("strava callback error: %s", error)
        return f"<h1>Strava error: {error}</h1>"
    if not code:
        return "<h1>Strava callback sin code — algo va mal</h1>"

    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        return "<h1>Server sin credenciales de Strava</h1>"

    try:
        r = requests.post(STRAVA_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }, timeout=15)
        r.raise_for_status()
        tokens = r.json()
    except Exception as e:
        log.exception("strava token exchange failed")
        return f"<h1>Fallo intercambiando code por tokens</h1><pre>{e}</pre>"

    Path(STRAVA_TOKEN_PATH).write_text(json.dumps(tokens, indent=2))
    os.chmod(STRAVA_TOKEN_PATH, 0o600)

    athlete = tokens.get("athlete") or {}
    granted_scope = scope or "(no scope reported)"
    return (
        "<h1>Strava conectado ✓</h1>"
        f"<p>Atleta: <b>{athlete.get('firstname','')} {athlete.get('lastname','')}</b> "
        f"(id {athlete.get('id')})</p>"
        f"<p>Scope concedido: <code>{granted_scope}</code></p>"
        f"<p>Tokens guardados en el servidor. Puedes cerrar esta pestaña.</p>"
    )
