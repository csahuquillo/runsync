# Troubleshooting

Errores típicos y cómo diagnosticarlos.

📖 **[Read in English](troubleshooting.md)**

## El Atajo enseña ❌ tras ejecutarse

**Paso 1:** añade `Mostrar Contenido de URL` temporalmente justo después del HTTP request para ver el JSON completo. Vuelve a ejecutar y léelo.

**Paso 2:** mira `results.<conector>.error` para los conectores con `ok: false`.

| Error | Causa | Arreglo |
|---|---|---|
| `Unauthorized` | Bearer token incorrecto o ausente | Comprueba que la cabecera `Authorization` del Atajo coincide con `Bearer <RUNSYNC_TOKEN>` en `/etc/runsync.env` |
| `unknown gear: <nombre>` | La zapatilla no está en `gear_map.py` | Añádela a `GEAR` o a `ALIASES` |
| `no run found for today` | La plataforma aún no tiene actividad de hoy | Espera a que Garmin/Strava terminen de sincronizar el reloj, o comprueba que realmente corriste hoy |
| `HTTP 400` de intervals.icu | Body con forma equivocada | Comprueba que `connectors.intervals_sync` manda `{"gear": {"id": ...}}` no `{"gear_id": ...}` |
| `AttributeError: 'coroutine' object has no attribute 'id'` | Telethon llamado como sync dentro del event loop de FastAPI | Asegura que `connectors.telegram_send_photo` se llama vía `await asyncio.to_thread(...)` |

## El Atajo enseña ✅ pero las plataformas no han cambiado

- **Strava:** comprueba que la actividad de hoy en Strava tiene `sport_type=Run` o `TrailRun`. Si la registraste como `Workout`, el conector la salta. Abre la actividad → *Editar* → cambia tipo a "Correr".
- **Garmin:** la actividad renombrada puede ser anterior a hoy. La "fecha de hoy" en Garmin depende de la zona horaria del dispositivo — si viajaste, puede desviarse.
- **intervals.icu:** comprueba que la actividad existe hoy (intervals tira de Strava unos 2 minutos después de subir). Si intervals aún no la tiene, el conector devuelve "no run found".

## El Atajo crashea / se queda colgado

- Lo más común: la imagen es demasiado grande. iOS Atajos tiene límites de memoria. Una imagen de Bevel pesa <2 MB, pero si tienes un wallpaper enorme como entrada, codificar base64 puede pasarse.
- Workaround: añade `Redimensionar imagen` antes de `Codificar Base64`, max 1500 px de ancho.

## `/sync-workout` devuelve 401 Unauthorized

El Bearer del header del Atajo no coincide con `RUNSYNC_TOKEN` en `/etc/runsync.env`. Causas típicas:
- Cambiaste el token en el servidor y no actualizaste el Atajo.
- Espacio extra en el header (ej. `Bearer  abc` con dos espacios).
- Nombre del header mal (ej. `authorization` minúscula vale, pero `Auth` no).

Comprueba el token real del servidor (sin imprimirlo):
```bash
sudo grep ^RUNSYNC_TOKEN= /etc/runsync.env | wc -c   # da la longitud
```

Y compara con la longitud del que tienes en el Atajo.

## Telegram no llega

- Comprueba `skip_telegram` en el body del Atajo. Si es `true`, es por diseño.
- Comprueba `TELEGRAM_CHAT_ID` en `/etc/runsync.env` tiene los IDs correctos separados por coma. Los IDs de grupos son números negativos que empiezan por `-100` (supergrupos/canales).
- Comprueba que la sesión de Telethon sigue autenticada:
  ```bash
  sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli whoami
  ```
  Si dice `NO_SESSION`, re-bootstrapea con `send-code` + `sign-in`.

## Garmin sigue pidiendo MFA

El tokenstore de Garmin expira cada cierto tiempo. Re-bootstrap:
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli send-code
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli sign-in 123456
```

Si sigue fallando, puede que la contraseña haya cambiado o que Garmin haya bloqueado la IP por muchos intentos. Espera un poco y reintenta.

## Cómo inspeccionar qué recibe `/sync-workout`

El `_validation_handler` en `main.py` loguea cada 422 con detalle completo. Para requests exitosas también, `main.py` loguea `sync-workout received: ...` con todos los campos parseados.

```bash
sudo journalctl -u runsync.service -f
```

Para un eco sin auth:
```bash
RUNSYNC_URL=https://api.tudominio.com scripts/check-debug-form.sh
```

## Rollback tras un deploy malo

```bash
ls -lt /opt/runsync/app/main.py.bak.* | head -3
sudo cp /opt/runsync/app/main.py.bak.<epoch> /opt/runsync/app/main.py
sudo systemctl restart runsync.service
```

Cada `scripts/deploy.sh` hace backup. Se acumulan; límpialos cada cierto tiempo:
```bash
ls -1t /opt/runsync/app/*.bak.* | tail -n +10 | xargs sudo rm
```
