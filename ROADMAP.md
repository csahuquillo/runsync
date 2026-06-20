# ROADMAP

## Hecho ✅

- [x] Endpoint `/sync-workout` con auth Bearer.
- [x] Parsing dual: multipart + JSON con `image_b64`.
- [x] Conector Strava (rename + gear + `workout_type`/`trainer`/`commute` desde tags conocidos + resto como hashtags en description). Default `workout_type=3` (Entrenamiento).
- [x] Conector intervals.icu (rename + `gear: {id}` + tags como lista nativa en el campo `tags`, no en description).
- [x] Conector Garmin Connect (rename + gear + descripción con #tags) con MFA bootstrap.
- [x] Conector Telegram (Telethon como usuario) con soporte multi-chat (CSV en `TELEGRAM_CHAT_ID`).
- [x] Telegram corre en `asyncio.to_thread` para no chocar con el event loop de FastAPI.
- [x] Default `skip_telegram=true` mientras se valida el flujo end-to-end.
- [x] Aliases en `gear_map.py` para tolerar nombres cortos del menú del Atajo (`NB More v5`, `Boston 13`, etc.).
- [x] Logging detallado de requests/responses en `/sync-workout`.
- [x] Atajo iOS funcional (menús de entreno, zapatillas, tags + envío JSON con imagen base64).

## Pendiente — corto plazo

- [ ] **Cambiar default `skip_telegram` a `false`** una vez verificado el envío real a los 2 grupos.
- [ ] **Verificar visualmente en intervals.icu** que el gear+descripción aplicados están bien (no solo HTTP 200).
- [ ] **Quitar la pantalla "Mostrar Contenido de URL"** del Atajo: deja una notificación discreta de éxito/error en lugar del JSON.
- [x] Documentar el bootstrap completo de Telegram (`telegram_cli.py send-code/sign-in/password`) — `docs/deploy.md` / `docs/deploy.es.md` §5.3 (máquina de estados `_pending.json`, `find-chat`, prueba `send-photo`).

## Pendiente — Strava API cambios (efectivo 1 jun 2027)

Anuncio Strava de 2026-06-01. No urgente (un año de margen) pero hay que hacerlo antes del 2027-06-01 o el conector deja de funcionar.

- [ ] **Cambiar base URL Strava** de `https://www.strava.com/api/v3` → `https://www.api-v3.strava.com`. Solo afecta a la constante `_STRAVA_BASE` en `server/app/connectors.py:58`. El endpoint `oauth/token` (refresh) NO cambia, sigue en `strava.com`.
- [ ] **Migrar `oauth/deauthorize` → `oauth/revoke`** si en algún momento se añade un flujo de revocación. Hoy no se usa ninguno; verificar antes de implementar.
- [x] ~~Mover Bearer de form params a header~~ — ya va en header (`_strava_headers()` línea 95-96). Sin cambios necesarios.

Notas:
- Suscripción Strava Premium ya activa, así que el requisito de "subscription required for Standard Tier" (30 jun 2026) no afecta.
- runsync es integración directa, no intermediary platform → no afectado por la restricción de 1 jun 2026.
- No usamos endpoints de Clubs ni Segments Explore (deprecados 1 sep 2026) → no afectado.

## Pendiente — medio plazo

- [ ] **WhatsApp** (mandar imagen a 1 grupo + 1 contacto). Opciones:
  - A. Compartir manual desde el Atajo iOS al final (recomendado, 1-2 taps).
  - B. WhatsApp Cloud API (Meta) — no soporta grupos personales; descartado.
  - C. Selenium/whatsapp-web automatizado en el servidor — frágil pero único modo que cubre grupos.
  - D. Librerías no oficiales (whatsmeow, baileys) — riesgo de baneo.
- [ ] **Conector Runalyze**. Hoy depende del auto-import desde Garmin/Strava. Si Runalyze tarda demasiado o no recoge los cambios posteriores, evaluar API directa.
- [ ] **Refactor del bootstrap de sesiones**: hoy Garmin y Telegram requieren scripts CLI distintos; unificar en un `runsync-admin` único.
- [ ] **Idempotencia**: si se ejecuta `/sync-workout` dos veces para el mismo entreno, hoy renombra dos veces y envía dos veces a Telegram. Detectar duplicados (mismo activity_id + nombre) y devolver `skipped: true`.

## Pendiente — largo plazo / nice-to-have

- [ ] Tests unitarios (al menos para `_parse_workout_body` y `gear_map.get` con aliases).
- [ ] CI básico (lint + tests) en GitHub Actions.
- [ ] Despliegue automatizado vía GitHub Action (con role IAM via OIDC, no claves).
- [ ] Métricas: contar entrenos por mes y por plataforma, tasa de fallo por conector.
- [ ] Soporte para deportes distintos a `Run` (bike, trail, etc.) — hoy hardcoded `Run`/`TrailRun` en Strava y `running` en Garmin.
- [ ] UI web pequeña para revisar últimos N entrenos sincronizados.

## Bugs conocidos / deuda técnica

- **Telegram coroutine bug** (resuelto): se envolvió en `asyncio.to_thread`. Si vuelve a aparecer es señal de que alguien metió código async dentro del thread; revisar.
- **`gear_map.py` hardcoded**: cualquier zapatilla nueva requiere editar el código y redesplegar. Mover a `/etc/runsync.gear.json` o tabla SQLite ligera.
- **Bearer token único**: hoy hay un solo `RUNSYNC_TOKEN`. Si se compromete, rotar manualmente. Si se quiere multi-dispositivo, soportar varios tokens (CSV) o JWT con expiración.
- **Sin rate limiting** en `/sync-workout`. Bajo nivel de exposición pero conviene meter límite básico con `slowapi` o nginx.
