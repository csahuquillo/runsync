#!/usr/bin/env bash
# scripts/deploy.sh — sube uno o varios ficheros de server/app/ a la EC2 vía SSM,
# valida sintaxis y reinicia el servicio runsync.
#
# Uso:
#   scripts/deploy.sh main.py                       # un solo fichero
#   scripts/deploy.sh main.py connectors.py         # varios
#
# Requiere AWS_PROFILE=entrenandoany (region eu-west-3).
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:-i-0b7f4135fd87a0a80}"
REGION="${AWS_REGION:-eu-west-3}"
PROFILE="${AWS_PROFILE:-entrenandoany}"

if [ $# -eq 0 ]; then
  echo "uso: $0 <fichero.py> [<fichero2.py> ...]  (rutas relativas a server/app/)"
  exit 1
fi

# Construye el script remoto con todos los uploads + validación + restart.
REMOTE="set -e"
for f in "$@"; do
  src="server/app/$f"
  if [ ! -f "$src" ]; then
    echo "ERROR: no existe $src"
    exit 2
  fi
  b64=$(base64 -i "$src" | tr -d '\n')
  REMOTE="$REMOTE
cp /opt/runsync/app/$f /opt/runsync/app/$f.bak.\$(date +%s)
echo '$b64' | base64 -d > /tmp/$f.new
chown runsync:runsync /tmp/$f.new
mv /tmp/$f.new /opt/runsync/app/$f
/opt/runsync/venv/bin/python -c \"import ast; ast.parse(open('/opt/runsync/app/$f').read())\""
done
REMOTE="$REMOTE
systemctl restart runsync.service
sleep 2
systemctl is-active runsync.service"

CMD_ID=$(AWS_PROFILE=$PROFILE aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters commands="[\"$(echo "$REMOTE" | sed 's/"/\\"/g')\"]" \
  --query "Command.CommandId" --output text)

echo "CMD_ID=$CMD_ID — esperando..."
sleep 6
AWS_PROFILE=$PROFILE aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "{Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}" \
  --output json
