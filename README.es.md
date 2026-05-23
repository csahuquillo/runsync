# runsync

> **Sincroniza un entreno en Strava, intervals.icu, Garmin Connect y Telegram con un solo tap desde la hoja de compartir del iPhone.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

📖 **[Read in English](README.md)**

## El problema

Después de cada carrera repites el mismo trabajo aburrido en cuatro sitios distintos:

- Renombrar la actividad en **Strava** y poner el modelo de zapatilla.
- Lo mismo en **intervals.icu**.
- Y otra vez en **Garmin Connect**.
- Exportar una imagen bonita desde **[Bevel](https://bevel.fit/)** y mandarla al grupo de Telegram con un caption tipo *"12 km — #Z2 #Base"*.

Cinco minutos perdidos cada vez. Multiplica por 4-5 entrenos a la semana.

## La solución

Un Atajo de iOS conectado a una mini-API en Python. Desde la hoja de compartir sobre la imagen de Bevel:

1. Tocas el Atajo.
2. Eliges el **nombre del entreno** (menú con tus opciones habituales + "otro").
3. Eliges las **zapatillas** (menú con tus pares activos).
4. Eliges los **tags** (multi-selección: Z2, Base, Tempo…).
5. Tap final → el backend renombra la actividad de hoy en las tres plataformas, le pone el gear correcto, los hashtags en la descripción, y envía la foto + caption a los chats de Telegram que quieras.

Total: ~10 segundos.

## ¿Esto te sirve?

✅ **Sí** si:
- Corres regularmente y subes a Strava + Garmin + (intervals.icu o similar).
- Usas o quieres usar [Bevel](https://bevel.fit/) para sacar imágenes de tus entrenos.
- Tienes un iPhone (o iPad/Mac, los Atajos también van).
- Te apañas con un VPS pequeño (4€/mes en cualquier hosting) o ya tienes uno.
- Sabes seguir instrucciones técnicas (no hace falta ser programador, pero sí leer comandos).

❌ **No** si:
- Quieres una app sin servidor → esto requiere alojar el backend tú mismo.
- Usas solo Android → el Atajo es nativo de iOS.
- Solo usas una plataforma → con un script simple te basta.

## Demo (lo que ves)

```
Bevel exporta una imagen ─→ Hoja de compartir iOS ─→ Ejecutas el Atajo
                                                          │
                                ┌─────────────────────────┘
                                ▼
                    ┌──────────────────────┐
                    │ Menú: Nombre entreno │   "12 km", "60 S", "Tirada Larga", "Otro…"
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Menú: Zapatillas     │   pares activos configurados en tus menús
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Lista: Tags          │   ☑ Aeróbico  ☑ Base  ☑ Z2
                    └──────────┬───────────┘
                               ▼ (codifica imagen en base64, POST JSON con Bearer)
                    ┌──────────────────────┐
                    │  api.tudominio.com   │
                    │   FastAPI / Python   │
                    └──────────┬───────────┘
                               │
                ┌──────┬───────┼───────┬─────────────┐
                ▼      ▼       ▼       ▼             ▼
             Strava intervals Garmin  Telegram   (Runalyze
             rename rename    rename  envía foto  auto-importa
             +gear  +gear     +gear   a N chats   desde Garmin
             +tags  +tags     +tags   + caption)  /Strava)
```

Notificación final en el iPhone: `runsync ✅` o `runsync ❌` si algo falló.

## Arquitectura

```
┌─────────────────┐     POST JSON     ┌──────────────────────────┐
│  Atajo iOS      │  ───────────────▶ │  Tu dominio (HTTPS)      │
│  Sincronizar    │   image_b64,      │  FastAPI + uvicorn       │
│  Entreno        │   name, shoes,    │  detrás de nginx         │
└─────────────────┘   tags, Bearer    └──────────┬───────────────┘
                                                 │
                  ┌──────────────────────────────┼─────────────────────────┐
                  ▼                ▼             ▼             ▼           ▼
              Strava API    intervals.icu    Garmin       Telethon     Runalyze*
              OAuth2        API key auth     Connect      (session     (auto-import
              token         (PUT activity)   (garmin-     usuario)     desde Garmin
              refresh                        connect)                  o Strava)
```

- **iOS Shortcuts** (no se commitea en el repo, ver [docs/atajo-setup.es.md](docs/atajo-setup.es.md) para reconstruirlo).
- **Backend Python 3.12** con FastAPI/uvicorn, levantado por systemd.
- **TLS** via nginx + Let's Encrypt.
- **Sesiones persistentes** por servicio: Strava OAuth se auto-refresca, Garmin guarda tokens, Telegram usa session de Telethon (no bot — mensajes como tu usuario).

`*` Runalyze sin conector propio: se entera de los cambios cuando vuelve a importar de Garmin o Strava.

## Qué te ahorra y qué cuesta montarlo

| Inversión inicial | Tiempo estimado |
|---|---|
| VPS con dominio + nginx + TLS | 30 min si ya lo tienes; 1-2 h desde cero |
| OAuth con Strava | 10 min |
| API key intervals.icu | 2 min |
| Bootstrap login Garmin con MFA | 5 min |
| Bootstrap sesión Telegram | 5 min |
| Construir el Atajo iOS siguiendo [la guía](docs/atajo-setup.es.md) | 30-45 min |
| **Total** | **~2-3 horas** |

A partir de ahí: **~10 segundos por entreno** vs. ~5 minutos a mano. Amortizado en una semana.

## Seguridad

Este proyecto te pide montar un servidor con credenciales de Strava, Garmin, Telegram e intervals.icu. Antes de continuar, entiende y aplica esto:

- **Todos los endpoints que modifican estado están protegidos por un Bearer token** (`RUNSYNC_TOKEN`). Genera una cadena aleatoria larga (`openssl rand -hex 32`) y úsala como token. No reutilices contraseñas.
- **TLS obligatorio.** No corras esto en HTTP plano — tu Bearer viajaría sin cifrar. Usa Let's Encrypt (gratis).
- **`/etc/runsync.env` con `chmod 600` y propiedad del usuario `runsync`.** systemd lo lee al arrancar.
- **Nunca commitees** tu `.env` real, el tokenstore de Garmin, los tokens de Strava ni el fichero de sesión de Telethon. El `.gitignore` ya los excluye, pero revisa.
- **El fichero `.shortcut` exportado lleva tu Bearer token embebido.** No lo compartas. Cada usuario reconstruye el Atajo en su dispositivo.
- **Los IDs de gear de Strava y los UUIDs de Garmin en `gear_map.py` son específicos de tu cuenta.** El repo trae placeholders; sustitúyelos localmente.
- **El backend expone una superficie de ataque pequeña.** Los endpoints sin auth (`/health`, `/debug-form`, `/strava/callback`, `/shortcut`) solo hacen eco u OAuth; revísalos tú antes de desplegar público.
- **Corre como usuario sin privilegios** (`runsync`). El unit de systemd que viene usa `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=true`.
- **No hay rate limiting incluido.** Si te preocupa, pon runsync detrás de nginx o Cloudflare con rate limiting básico en `/sync-workout`.

Si alguna de estas cosas te incomoda, aloja en red privada (acceso solo por VPN) o monta runsync en una Raspberry Pi en casa con DNS interno.

## Quick start

1. **Clona y léete los docs.**
   ```bash
   git clone https://github.com/csahuquillo/runsync.git
   cd runsync
   ```
2. **Despliega el backend** siguiendo [docs/deploy.es.md](docs/deploy.es.md). Necesitas un VPS Linux con Python 3.12, nginx, y un dominio.
3. **Configura `/etc/runsync.env`** con tus credenciales — plantilla en [`runsync.env.example`](runsync.env.example).
4. **Bootstrap interactivo** de Strava (OAuth en navegador), Garmin (MFA email) y Telegram (código SMS). Ver [docs/deploy.es.md § Bootstrap de sesiones](docs/deploy.es.md#5-bootstrap-de-sesiones).
5. **Sustituye los placeholders de gear** en `server/app/gear_map.py` por los IDs reales de tus zapatillas. El docstring del fichero explica cómo obtenerlos.
6. **Construye el Atajo en tu iPhone** siguiendo [docs/atajo-setup.es.md](docs/atajo-setup.es.md). ~40 min con la guía paso a paso.
7. **Prueba** con `curl https://tu-dominio.com/health` desde otra máquina, y luego ejecuta el Atajo sobre una imagen de Bevel.

## Endpoints

| Método | Ruta             | Auth        | Para qué |
|--------|------------------|-------------|----------|
| GET    | `/health`        | —           | Probe trivial |
| POST   | `/debug-form`    | —           | Eco. Acepta multipart o JSON, devuelve lo que recibe (útil para depurar el Atajo) |
| POST   | `/sync-workout`  | Bearer      | El que dispara el Atajo |
| GET    | `/strava/callback` | —         | OAuth callback de Strava |
| GET    | `/shortcut`      | —           | Sirve el `.shortcut` si lo subes manualmente |

### Cuerpo de `/sync-workout`

```jsonc
POST /sync-workout
Authorization: Bearer <RUNSYNC_TOKEN>
Content-Type: application/json

{
  "name":           "12 km",                  // se usa como nombre de actividad
  "shoes":          "Adidas Boston 13",       // canonical o alias (ver gear_map.py)
  "tags":           "Aeróbico,Base,Z2",       // CSV; cada uno se vuelve #hashtag
  "image_filename": "Imagen.png",
  "image_b64":      "iVBORw0KGgo...",         // PNG/JPEG codificado en base64
  "skip_telegram":  "false"                   // opcional; default true (no envía)
}
```

Respuesta:

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

`ok` global = `true` solo si los 4 conectores dieron OK.

## Estructura del repo

```
runsync/
├── README.md               ← English (principal)
├── README.es.md            ← este fichero
├── AGENTS.md               ← convenciones para colaboradores / agentes
├── ROADMAP.md              ← hecho / pendiente / bugs conocidos
├── LICENSE                 ← MIT
├── runsync.env.example     ← plantilla del .env, sin secretos
├── docs/
│   ├── architecture.md     ← arquitectura detallada + flujo de datos (EN)
│   ├── architecture.es.md
│   ├── deploy.md           ← guía completa de despliegue (EN)
│   ├── deploy.es.md
│   ├── atajo-setup.md      ← construir el Atajo iOS paso a paso (EN)
│   ├── atajo-setup.es.md
│   └── troubleshooting.md
├── server/
│   ├── app/                ← código FastAPI (main, conectores, gear_map)
│   ├── requirements.txt    ← deps runtime
│   ├── systemd/
│   │   └── runsync.service ← unit de systemd
│   └── scripts/            ← utilidades de diagnóstico (no runtime)
└── scripts/
    ├── check-debug-form.sh ← prueba multipart contra /debug-form
    └── deploy.sh           ← sube cambios al servidor vía AWS SSM
```

## FAQ

### ¿Por qué no usar Strava webhooks → IFTTT → todo lo demás?
Los webhooks de Strava llegan ~minuto después de la actividad y no te permiten elegir zapatilla/tags por entreno. Aquí decides en el momento.

### ¿Por qué Bevel y no la app de Strava?
Bevel exporta una imagen pulida lista para redes. Pero puedes usar cualquier imagen: el Atajo solo necesita una entrada de tipo imagen.

### ¿Y si no estoy en Strava / no uso intervals / etc.?
El backend está organizado para que cada conector sea independiente. Borra el que no quieras en `connectors.py` y en `main.py`. PRs bienvenidos para añadir más plataformas (Coros, Polar Flow, Suunto…).

### ¿Por qué JSON con base64 y no multipart?
iOS Shortcuts envía multipart de forma inconsistente. La imagen llegaba como texto y rompía el parser. JSON con base64 es 33% más pesado pero funciona el 100% de las veces. Ver [docs/architecture.es.md](docs/architecture.es.md).

### ¿WhatsApp?
WhatsApp no tiene API decente para grupos personales. La forma fiable: añadir una acción `Compartir` al final del Atajo iOS (te abre el selector y eliges destino a mano, 1-2 taps). Más detalles en [ROADMAP.md](ROADMAP.md).

### ¿Y si solo quiero usarlo con un grupo de Telegram, sin Garmin/Strava/intervals?
Ya viene preparado: comentas las llamadas a los conectores que no usas en `main.py:sync_workout()`. Telegram tiene flag `skip_telegram` para alternar.

### ¿Cuánto cuesta?
Lo único de pago es el VPS y el dominio. ~5€/mes en cualquier hosting (Hetzner, OVH, AWS Lightsail, Digital Ocean…). Strava, intervals, Garmin, Telegram son gratis para uso personal.

## Limitaciones conocidas

- **iOS only** (el Atajo). El backend es agnóstico, puedes mandarle POST desde cualquier sitio.
- **Un solo deporte primario**: hoy busca actividades de tipo `Run`/`TrailRun`. Para bici o trail, hay que editar los filtros en `connectors.py`.
- **Idempotencia**: si se ejecuta el Atajo dos veces para el mismo entreno, hoy renombra dos veces y envía dos veces a Telegram. Pendiente, ver ROADMAP.
- **Bootstrap manual** de sesiones (Garmin MFA, Telegram SMS). Una vez al inicio, no se repite mientras la sesión esté activa.

Más detalle en [ROADMAP.md](ROADMAP.md).

## Contribuir

PRs bienvenidas, especialmente:
- Conectores para otras plataformas (Coros, Suunto, Polar, Runalyze API directa).
- Tests.
- CI básico (lint + tests + deploy automático via OIDC).
- Soporte para ciclismo / trail / swim.

Lee [AGENTS.md](AGENTS.md) antes de mandar PR — convenciones del proyecto.

## Licencia

[MIT](LICENSE) © 2026 Carlos Sahuquillo

---

¿Lo usas y te ahorra tiempo? Una ⭐ en el repo me alegra el día.
