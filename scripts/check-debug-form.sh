#!/usr/bin/env bash
# Send a multipart POST to /debug-form mimicking what the iOS Shortcut sends.
#
# Usage:
#   RUNSYNC_URL=https://api.your-domain.com ./check-debug-form.sh
#   RUNSYNC_URL=https://api.your-domain.com ./check-debug-form.sh ~/Pictures/img.png
#
# Required env:
#   RUNSYNC_URL  — Base URL of your runsync deployment.
set -euo pipefail

: "${RUNSYNC_URL:?RUNSYNC_URL env var is required (e.g. https://api.example.com)}"
URL="${RUNSYNC_URL%/}/debug-form"
IMG="${1:-}"

TMP=""
if [ -z "$IMG" ]; then
  TMP="$(mktemp -t runsync-img.XXXXXX.png)"
  # 1x1 transparent PNG
  printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82' > "$TMP"
  IMG="$TMP"
fi

curl -sS -X POST "$URL" \
  -F "name=Test workout" \
  -F "shoes=Example Shoe A" \
  -F "tags=Tag1,Tag2" \
  -F "image=@${IMG};filename=Image.png;type=image/png" \
| python3 -m json.tool

[ -n "$TMP" ] && rm -f "$TMP" || true
