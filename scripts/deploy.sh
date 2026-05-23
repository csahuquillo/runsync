#!/usr/bin/env bash
# scripts/deploy.sh — upload one or more files from server/app/ to the EC2 host
# via AWS Systems Manager (SSM), validate Python syntax, and restart runsync.
#
# Usage:
#   INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=myprofile \
#     scripts/deploy.sh main.py
#
#   INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=myprofile \
#     scripts/deploy.sh main.py connectors.py
#
# Required env:
#   INSTANCE_ID  — EC2 instance ID where runsync lives.
#   AWS_PROFILE  — local AWS profile with ssm:SendCommand on that instance.
# Optional env:
#   AWS_REGION   — defaults to eu-west-3.
#
# This script assumes /opt/runsync/app/ on the instance and a systemd unit
# called runsync.service. Adjust if your install path is different.
set -euo pipefail

: "${INSTANCE_ID:?INSTANCE_ID env var is required (e.g. i-0123456789abcdef0)}"
: "${AWS_PROFILE:?AWS_PROFILE env var is required}"
REGION="${AWS_REGION:-eu-west-3}"

if [ $# -eq 0 ]; then
  echo "usage: $0 <file.py> [<file2.py> ...]  (paths relative to server/app/)"
  exit 1
fi

REMOTE="set -e"
for f in "$@"; do
  src="server/app/$f"
  if [ ! -f "$src" ]; then
    echo "ERROR: file not found: $src"
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

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters commands="[\"$(echo "$REMOTE" | sed 's/"/\\"/g')\"]" \
  --query "Command.CommandId" --output text)

echo "CMD_ID=$CMD_ID — waiting..."
sleep 6
aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "{Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}" \
  --output json
