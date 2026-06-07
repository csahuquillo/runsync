---
description: Estado de todas las automatizaciones gestionadas por INVENT (AWS) vía SSM
argument-hint: "[nombre-automatización]  (vacío = todas)"
---

# /status — estado de las automatizaciones en INVENT

Objetivo: replicar el `/status` del escritorio. Consulta INVENT (el sistema en
AWS que gestiona runsync y el resto de automatizaciones) vía **AWS SSM** y
reporta el estado de **todas** las automatizaciones, o solo de `$ARGUMENTS` si
se pasa un nombre.

Contexto del despliegue (ver `docs/invent.es.md`):

- Cada automatización vive en `/opt/automations/<nombre>/current` con su
  `<nombre>.service` systemd.
- En el servidor existe la herramienta `automation-status --name <n> --logs`.
- runsync escucha en `127.0.0.1:8010`; salud pública en
  `https://invent.qualipharmagroup.com/runsync/health`.

## Configuración (no se commitea)

La conexión necesita identificar la instancia EC2 de INVENT y el perfil AWS.
Igual que en el `agent-hub`, esto se carga desde un `env.local` (gitignored) o
desde variables de entorno ya presentes en la sesión:

- `INVENT_INSTANCE_ID` (o `INSTANCE_ID`) — id de la instancia EC2 (`i-0…`).
- `AWS_PROFILE` — perfil con permiso `ssm:SendCommand` sobre esa instancia.
- `AWS_REGION` — opcional, por defecto `eu-west-3`.

> Nunca hardcodees el id de instancia ni dominios reales en el repo
> (regla de `AGENTS.md`). Déjalos en `env.local` o en el entorno.

## Procedimiento

Ejecuta este bloque. Carga `env.local` si existe, lanza `automation-status`
sobre cada automatización vía SSM y devuelve la salida:

```bash
set -uo pipefail

# 1) Cargar config local (patrón agent-hub/env.local). No se commitea.
for f in "$PWD/env.local" "$PWD/.claude/env.local" "$HOME/.config/runsync/env.local"; do
  if [ -f "$f" ]; then set -a; . "$f"; set +a; echo "config: $f"; fi
done

INSTANCE="${INVENT_INSTANCE_ID:-${INSTANCE_ID:-}}"
PROFILE="${AWS_PROFILE:-}"
REGION="${AWS_REGION:-eu-west-3}"
TARGET="$ARGUMENTS"   # vacío = todas las automatizaciones

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI no disponible. /status necesita acceso AWS SSM (úsalo desde tu escritorio/CLI configurado)."
  exit 1
fi
if [ -z "$INSTANCE" ]; then
  echo "ERROR: falta el id de instancia de INVENT."
  echo "Define INVENT_INSTANCE_ID (o INSTANCE_ID) en env.local o en el entorno."
  exit 1
fi

# 2) Script remoto: por cada automatización, su estado + últimos logs.
if [ -n "$TARGET" ]; then SCOPE="/opt/automations/$TARGET/"; else SCOPE="/opt/automations/*/"; fi
REMOTE="for d in $SCOPE; do [ -d \"\$d\" ] || continue; n=\$(basename \"\$d\"); printf '\n=== %s ===\n' \"\$n\"; if command -v automation-status >/dev/null 2>&1; then automation-status --name \"\$n\" --logs 2>&1 | tail -n 25; else echo \"servicio: \$(systemctl is-active \"\$n.service\" 2>&1)\"; systemctl status \"\$n.service\" --no-pager 2>&1 | tail -n 8; fi; done"

# 3) Enviar por SSM y esperar.
CMD_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE" \
  --document-name AWS-RunShellScript \
  --comment "/status — automatizaciones INVENT" \
  --parameters commands="$REMOTE" \
  ${PROFILE:+--profile "$PROFILE"} --region "$REGION" \
  --query Command.CommandId --output text) || { echo "send-command falló"; exit 1; }

ST=Pending
for _ in $(seq 1 40); do
  ST=$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE" \
        ${PROFILE:+--profile "$PROFILE"} --region "$REGION" --query Status --output text 2>/dev/null || echo Pending)
  case "$ST" in Success|Failed|Cancelled|TimedOut) break;; esac
  sleep 2
done

echo "--- SSM: $ST (instancia $INSTANCE, región $REGION) ---"
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE" \
  ${PROFILE:+--profile "$PROFILE"} --region "$REGION" --query StandardOutputContent --output text
ERR=$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE" \
       ${PROFILE:+--profile "$PROFILE"} --region "$REGION" --query StandardErrorContent --output text 2>/dev/null || true)
if [ -n "${ERR:-}" ] && [ "$ERR" != "None" ]; then echo "--- stderr ---"; echo "$ERR"; fi
```

## Salida

Resume lo recibido en una tabla clara, una fila por automatización:

| Automatización | Servicio | Salud | Últimos errores |
|---|---|---|---|

- **Servicio**: `active` / `failed` / `inactive` (de systemd / `automation-status`).
- **Salud**: si la automatización expone health (runsync → `/runsync/health`),
  refléjalo; si no, déjalo en `—`.
- **Últimos errores**: la línea más relevante de los logs, o `—` si está limpio.

Marca con ✅ las que estén `active` y sanas, con ❌ las `failed`, y con ⚠️ las
que estén activas pero con errores recientes en los logs. Si `automation-status`
no estaba disponible en el servidor, indícalo y usa lo que devuelva systemd.
