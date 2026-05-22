# runsync

Sincronizador de entrenamientos de carrera: desde un Atajo de iOS, con una imagen exportada de [Bevel](https://bevel.fit/) y unos pocos campos (nombre, zapatillas, tags), publica el entreno en **Strava**, **intervals.icu** y **Garmin Connect**, y envía la foto + caption a uno o varios chats de **Telegram**.

```
┌─────────────────┐     POST JSON     ┌──────────────────────────┐
│  Atajo iOS      │  ───────────────▶ │  api.sahuquillo.org      │
│  Sincronizar    │   image_b64,      │  FastAPI / uvicorn       │
│  Entreno        │   name, shoes,    │  (EC2 + systemd)         │
└─────────────────┘   tags, ...       └──────────┬───────────────┘
                                                 │
                  ┌──────────────────────────────┼─────────────────────────┐
                  ▼                ▼             ▼             ▼           ▼
              Strava API    intervals.icu    Garmin       Telethon     Runalyze*
              (rename +     (rename +        Connect      (send         (auto-import
               gear +       gear +           (rename +    photo +       desde Garmin
               desc tags)   desc tags)       gear +       caption       o Strava)
                                             desc tags)   a N chats)
```

`*` Runalyze no tiene conector propio; se entera de los cambios cuando vuelve a importar de Garmin/Strava.

## Por qué existe

Bevel exporta una imagen bonita del entreno pero requiere repetir el mismo trabajo (nombre, zapatillas, hashtags) en cuatro sitios. runsync ahorra ese trabajo en un único POST disparado desde la hoja de compartir del iPhone.

## Estructura del repo

```
runsync-atajo/
├── README.md               ← este fichero
├── AGENTS.md               ← convenciones del proyecto para agentes / contributors
├── ROADMAP.md              ← qué hay hecho, qué falta, qué bugs hay
├── LICENSE                 ← MIT
├── runsync.env.example     ← plantilla del .env que va en /etc/runsync.env
├── docs/
│   ├── architecture.md     ← diagrama detallado + flujo de datos
│   ├── deploy.md           ← cómo desplegar en EC2 vía SSM
│   ├── atajo-setup.md      ← cómo recrear el Atajo iOS desde cero
│   └── atajo-pasos.md      ← guía paso a paso de los arreglos clásicos
├── server/
│   ├── app/                ← código FastAPI que corre como app.main:app
│   │   ├── main.py         ← endpoints HTTP
│   │   ├── connectors.py   ← strava / intervals / garmin / telegram
│   │   ├── gear_map.py     ← mapeo canónico de zapatillas → IDs por plataforma
│   │   ├── garmin_cli.py   ← CLI auxiliar de login Garmin con MFA
│   │   ├── garmin_login_bg.py
│   │   └── telegram_cli.py ← CLI para autenticar la sesión de Telethon
│   ├── requirements.txt    ← deps runtime declaradas
│   ├── requirements-frozen.txt  ← pip freeze del venv en producción
│   ├── systemd/
│   │   └── runsync.service ← unit que arranca uvicorn
│   └── scripts/            ← utilidades de diagnóstico (no parte del runtime)
└── scripts/
    └── check-debug-form.sh ← prueba multipart contra /debug-form
```

## Endpoints

| Método | Ruta             | Auth        | Para qué |
|--------|------------------|-------------|----------|
| GET    | `/health`        | —           | Probe trivial |
| POST   | `/debug-form`    | —           | Eco. Acepta multipart o JSON, devuelve lo que recibe |
| POST   | `/sync-workout`  | Bearer      | Procesa el entreno y publica en las 4 plataformas |
| GET    | `/strava/callback` | —         | OAuth callback de Strava |
| GET    | `/shortcut`      | —           | Sirve el .shortcut para importarlo |

### Cuerpo de `/sync-workout`

Acepta dos formatos. **Usa JSON** (multipart no funciona fiable en iOS Shortcuts):

```jsonc
POST /sync-workout
Authorization: Bearer <RUNSYNC_TOKEN>
Content-Type: application/json

{
  "name":           "12 km en Valencia",       // se usa como nombre de actividad
  "shoes":          "Adidas Boston 13",        // canonical o alias (ver gear_map.py)
  "tags":           "Aeróbico,Base,Z2",        // CSV; cada uno se vuelve #hashtag
  "image_filename": "Imagen.png",
  "image_b64":      "iVBORw0KGgo...",          // PNG/JPEG codificado en base64
  "skip_telegram":  "false"                    // opcional; default true (no envía)
}
```

Respuesta:

```json
{
  "ok": true,
  "results": {
    "strava":    { "ok": true, "platform": "strava",    "activity_id": 18606114945, ... },
    "intervals": { "ok": true, "platform": "intervals", "activity_id": "i150530805", ... },
    "garmin":    { "ok": true, "platform": "garmin",    "activity_id": 22969608335, ... },
    "telegram":  { "ok": true, "platform": "telegram",  "sent": [{...},{...}] }
  }
}
```

`ok` global = `true` solo si los 4 conectores dieron OK.

## Setup rápido

Ver [docs/deploy.md](docs/deploy.md) para el detalle. Resumen:

1. EC2 con Python 3.12, usuario `runsync`, `/opt/runsync/` con venv e instalado `requirements.txt`.
2. `/etc/runsync.env` con las variables (ver `runsync.env.example`).
3. `systemd` unit en `/etc/systemd/system/runsync.service` (copia desde `server/systemd/`).
4. Nginx (o tu reverse proxy) con TLS terminando en `api.sahuquillo.org` y proxy a `127.0.0.1:8000`.
5. Bootstrap interactivo de sesiones para Garmin (MFA) y Telegram (código SMS) → ver [docs/deploy.md](docs/deploy.md).

## Atajo iOS

Ver [docs/atajo-setup.md](docs/atajo-setup.md) para crearlo desde cero, o [docs/atajo-pasos.md](docs/atajo-pasos.md) para los gotchas más comunes.

## Limitaciones conocidas

- **WhatsApp**: no hay conector. Para enviar a un contacto/grupo de WhatsApp, lo más fiable es añadir una acción `Compartir` al final del Atajo y elegir destino a mano.
- **Runalyze**: no hay conector directo; depende del auto-import de Garmin/Strava.
- **iOS Shortcuts + multipart**: no fiable. Por eso usamos JSON + base64.
- **Telegram via Telethon**: necesita session persistente. Si caduca, re-autenticar con `telegram_cli.py`.

Ver [ROADMAP.md](ROADMAP.md) para el pendiente.

## Licencia

[MIT](LICENSE) © Carlos Sahuquillo
