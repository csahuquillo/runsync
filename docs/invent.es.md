# Despliegue en INVENT

Estado actual: `runsync` corre en INVENT y se mantiene tambien activo en SB Mail
como fallback hasta cambiar el atajo iOS o mover `api.sahuquillo.org`.

## INVENT

- Ruta: `/opt/automations/runsync/current`
- Symlink de compatibilidad: `/opt/runsync`
- Servicio: `runsync.service`
- Puerto local: `127.0.0.1:8010`
- Proxy Apache: `/runsync/`
- Health: `https://invent.qualipharmagroup.com/runsync/health`
- Endpoint del atajo: `https://invent.qualipharmagroup.com/runsync/sync-workout`
- Certificado TLS: Let's Encrypt para `invent.qualipharmagroup.com`
- Superficie publica: solo `/runsync/health` y `/runsync/sync-workout`.
  `/runsync/sync-workout` exige Bearer token; `/runsync/shortcut` y
  `/runsync/debug-form` quedan bloqueados desde Apache.

El servicio mantiene las rutas internas `/opt/runsync/...` porque el codigo y
las sesiones historicas las usan para Garmin, Strava y Telegram.

## Estado

Desde el repositorio de automatizaciones:

```bash
cd "/Users/ccsp/Documents/5 PROYECTOS/Automatizaciones" && ./status invent runsync
```

En el servidor:

```bash
automation-status --name runsync --logs
systemctl status runsync.service --no-pager
curl -fsS http://127.0.0.1:8010/health
```

## Notas de migracion

- Migrado el 2026-05-29 desde SB Mail (`/opt/runsync`).
- Se copiaron `sessions/`, `/etc/runsync.env`, `Sincronizar_Entreno.shortcut`
  y el `gear_map.py` real del servidor sin imprimir secretos.
- `/shortcut` exige Bearer token. No debe ser publico porque el atajo exportado
  puede contener el token del cliente.
- Garmin usa el metodo PUT real de `garminconnect`; no usar
  `connectapi(..., method="PUT")` porque en `garminconnect 0.3.3` `connectapi`
  siempre hace GET.

## Pendiente

Para apagar SB Mail como dependencia hay que hacer una de estas dos cosas:

1. Cambiar el atajo iOS para que apunte a
   `https://invent.qualipharmagroup.com/runsync/sync-workout`.
2. Migrar `api.sahuquillo.org` a INVENT con DNS y certificado TLS nuevo si se
   quiere mantener la URL antigua.

Hasta entonces, SB Mail sigue siendo el endpoint productivo anterior.
