# AGENTS.md — runsync

Convenciones para humanos y agentes que toquen este repo.

## Qué es esto

API Python (FastAPI) que recibe un POST del Atajo iOS de Bevel y propaga el entreno a Strava / intervals.icu / Garmin Connect + envía la imagen a Telegram. Corre en una EC2 (`i-0b7f4135fd87a0a80`, region `eu-west-3`, account `737143846226`).

## Reglas inviolables

1. **Nunca imprimir el contenido de `/etc/runsync.env`** ni credenciales. Si necesitas leer una clave concreta, `grep ^CLAVE= /etc/runsync.env`. Sin `cat`.
2. **El .env vive solo en el servidor.** No replicar en local ni en repo. Modificar con `sed -i` puntual.
3. **Acceso al servidor: SSM-only.** Sin SSH, sin túneles. Usar `AWS_PROFILE=entrenandoany` (region `eu-west-3`).
4. **Backups antes de modificar** ficheros del servidor: `cp X X.bak.$(date +%s)`.
5. **Validar sintaxis Python** antes de `systemctl restart`: `python -c "import ast; ast.parse(open('...').read())"`.
6. **Nunca commitear**: `.env`, `sessions/`, `*.session`, `strava.json`, `*.shortcut` (contienen Bearer), backups `*.bak.*`.
7. **El Atajo iOS no se versiona en el repo.** Su contenido se documenta en `docs/atajo-setup.md`. Razón: el `.shortcut` exportado lleva el Bearer embebido.

## Convenciones de código

- Python 3.12. Type hints siempre que sean útiles. `from __future__ import annotations` ya en los ficheros.
- Endpoints FastAPI: siempre devolver `dict` JSON-serializable; no `Response` directos salvo necesidad.
- Errores en conectores: nunca lanzar `HTTPException` 500 al cliente — capturar y devolver `{"ok": false, "platform": "...", "error": "..."}` dentro del dict de resultados. El cliente (Atajo) prefiere un 200 con detalles a un 500.
- Logging: `log.info(...)` con plantilla `%r` para valores. `log.warning` para fallos no críticos. `log.exception` solo para excepciones inesperadas.
- Nombres de variables internas: snake_case en español si encajan con el dominio (`nombre_entreno`, `zapas`, `tags_csv`); en inglés si son técnicos (`session`, `client`, `response`).

## Flujo de trabajo de cambios

Para cualquier cambio en el código del servidor:

1. Editar localmente en `server/app/...`.
2. Validar `python -m py_compile server/app/*.py` (o `ast.parse`).
3. Subir vía SSM con `base64 -d` + `mv` atómico (ver patrón en `docs/deploy.md`).
4. `systemctl restart runsync.service && systemctl is-active runsync.service`.
5. Probar contra `/debug-form` o `/sync-workout` antes de decir "hecho".

Para cambios en `gear_map.py` (añadir zapatilla nueva): ejecutar primero `garmin_cli list-gear` en el servidor para obtener el UUID de Garmin; el ID de Strava se ve en `https://www.strava.com/gear/<id>`; el de intervals.icu en su UI de equipamiento.

## Estructura

- `server/app/main.py`: endpoints. Parsing dual (JSON / multipart) en `_parse_workout_body`.
- `server/app/connectors.py`: una función `<plat>_sync(name, gear_canonical, tags)` por plataforma + `telegram_send_photo(image_bytes, filename, caption)`.
- `server/app/gear_map.py`: tabla canónica + aliases para los nombres cortos del menú del Atajo.
- `server/app/*_cli.py`: utilidades de autenticación (no las ejecuta la API, son para el bootstrap manual).

## Donde NO mirar

- `server/scripts/`: utilidades de diagnóstico de una sola vez (probes de la API de intervals, listados de chats de Telegram). No forman parte del runtime y pueden estar obsoletas.

## Despliegue

- Producción única: instancia EC2 mencionada arriba.
- No hay CI/CD. Despliegues a mano vía SSM con el patrón base64 + atomic `mv`.
- TLS y dominio: `api.sahuquillo.org` (DNS gestionado en Ionos).

## Cuando algo falla en producción

Logs: `sudo journalctl -u runsync.service -n 100 --no-pager`. La función `_validation_handler` (ver `main.py`) ya loguea con detalle los 422 con el form recibido.

Endpoint `/debug-form` es la primera parada al diagnosticar problemas del Atajo — devuelve eco de lo que llega y permite distinguir bugs cliente vs. servidor.
