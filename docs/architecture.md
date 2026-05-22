# Arquitectura

## Componentes

| Componente | Dónde vive | Stack |
|---|---|---|
| Atajo iOS "Sincronizar Entreno" | iPhone | iOS Shortcuts |
| Reverse proxy + TLS | EC2 | nginx + certbot |
| API runsync | EC2 `/opt/runsync/` | FastAPI + uvicorn (systemd) |
| Sesiones persistentes | EC2 `/opt/runsync/sessions/` | Strava OAuth tokens, Garmin tokenstore, Telethon session |
| DNS | Ionos | `api.sahuquillo.org` → IP de la EC2 |

## Flujo de datos

```
┌─────────────────────────┐
│ iPhone — Bevel          │
│ (exporta imagen entreno)│
└──────────┬──────────────┘
           │ Hoja de compartir
           ▼
┌─────────────────────────┐
│ Atajo iOS               │
│ - menú nombre entreno   │
│ - menú zapatillas       │
│ - menú tags (multi)     │
│ - codifica imagen base64│
└──────────┬──────────────┘
           │ POST JSON
           │ Authorization: Bearer ...
           ▼
┌─────────────────────────┐
│ nginx (TLS)             │
│ api.sahuquillo.org      │
└──────────┬──────────────┘
           │ proxy_pass http://127.0.0.1:8000
           ▼
┌─────────────────────────────────────────────────┐
│ FastAPI app.main:app                            │
│                                                 │
│ /sync-workout:                                  │
│   1. _require_auth() — valida Bearer            │
│   2. _parse_workout_body() — JSON o multipart   │
│   3. connectors.strava_sync()                   │
│   4. connectors.intervals_sync()                │
│   5. connectors.garmin_sync()                   │
│   6. asyncio.to_thread(                         │
│        connectors.telegram_send_photo)          │
│   7. devuelve dict con resultados por conector  │
└─────────────────────────────────────────────────┘
```

## Cómo cada conector identifica la actividad de hoy

| Plataforma | Estrategia | Endpoint |
|---|---|---|
| Strava | Lista las últimas 10 actividades del atleta, filtra `sport_type ∈ {Run, TrailRun}` cuya `start_date_local` empieza por la fecha local de hoy | `GET /athlete/activities?per_page=10` |
| intervals.icu | Lista actividades desde "oldest=hoy" con `limit=10`, filtra `type == "Run"` | `GET /athlete/{id}/activities` |
| Garmin Connect | `api.get_activities(0, 10)`, filtra `activityType.typeKey` que empiece por `running` y fecha hoy | wrapper de `garminconnect` |

Si no encuentra actividad del día, devuelve `{"ok": false, "error": "no run found for today"}` y no toca nada — fallo seguro.

## Modelo de gear

```
gear_map.py
├── GEAR (dict)
│   └── "Adidas Boston 13" → { strava_id, intervals_id, garmin_uuid }
└── ALIASES (dict)
    └── "NB More v5" → "New Balance More 5"
```

`gear_map.get(name)` resuelve directos o vía alias. Los IDs **no se inventan**: hay que sacarlos de cada plataforma:

- **Strava**: `https://www.strava.com/gear/<id>` (URL al gestionar la zapatilla).
- **intervals.icu**: en `Settings → Equipment`, el ID está en la URL al editar.
- **Garmin**: `garmin_cli list-gear` ejecutado en el servidor lo devuelve.

## Sesiones persistentes

| Servicio | Fichero | Bootstrap |
|---|---|---|
| Strava | `/opt/runsync/sessions/strava.json` | OAuth code via `/strava/callback`, refresh automático |
| Garmin | `/opt/runsync/sessions/garmin/` (tokenstore) | `garmin_cli send-code` + `sign-in <code>` (MFA email) |
| Telegram | `/opt/runsync/sessions/me.session` | `telegram_cli send-code <phone>` + `sign-in <code>` + opcional `password <2fa>` |

Todos persisten entre reinicios. Strava se auto-refresca; Garmin renueva tokens si caducan; Telethon mantiene la sesión activa indefinidamente salvo que se invalide manualmente.

## Seguridad

- Sin SSH al servidor — acceso solo vía AWS Systems Manager.
- `/etc/runsync.env` con `mode 600` propiedad `runsync:runsync`. systemd lo carga como `EnvironmentFile`.
- `RUNSYNC_TOKEN` único compartido entre servidor y Atajo.
- Endpoints sin auth: `/health`, `/debug-form` (eco, no propaga), `/strava/callback` (validado por OAuth state), `/shortcut`.
- No hay rate limiting hoy (deuda técnica).
