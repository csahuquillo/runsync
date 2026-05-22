#!/usr/bin/env bash
# Envía un POST multipart de prueba a /debug-form imitando lo que debe mandar el Atajo.
# Uso: ./check-debug-form.sh [ruta_imagen]
set -euo pipefail

URL="https://api.sahuquillo.org/debug-form"
IMG="${1:-}"

TMP=""
if [ -z "$IMG" ]; then
  TMP="$(mktemp -t runsync-img.XXXXXX.png)"
  # PNG 1x1 transparente
  printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82' > "$TMP"
  IMG="$TMP"
fi

curl -sS -X POST "$URL" \
  -F "name=50 S" \
  -F "shoes=Adidas Boston 13" \
  -F "tags=Aeróbico,Base,Z2" \
  -F "image=@${IMG};filename=Imagen.png;type=image/png" \
| python3 -m json.tool

[ -n "$TMP" ] && rm -f "$TMP" || true
