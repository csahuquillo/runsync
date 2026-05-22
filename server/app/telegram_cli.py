"""
CLI auxiliar para gestionar la sesión de Telethon en el servidor.

Permite hacer el bootstrap interactivo de autenticación dividido en pasos
(necesario porque cada llamada SSM es no-interactiva), y luego validar y
mandar mensajes/imágenes al grupo.

Uso:
    telegram_cli send-code +34XXXXXXXXX
    telegram_cli sign-in 12345                    # con código que llega por Telegram
    telegram_cli password "mi_2fa"                # solo si hay 2FA
    telegram_cli whoami                           # confirma sesión válida
    telegram_cli find-chat "Corriendo a NY"
    telegram_cli send-photo <chat_id> <ruta_imagen> <caption>

Lee TELEGRAM_API_ID y TELEGRAM_API_HASH desde /etc/runsync.env (o el entorno).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SESSION_PATH = "/opt/runsync/sessions/me"
PENDING_PATH = "/opt/runsync/sessions/_pending.json"
ENV_PATH = "/etc/runsync.env"


def load_env() -> None:
    """Carga simple de /etc/runsync.env si existe."""
    p = Path(ENV_PATH)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def get_credentials() -> tuple[int, str]:
    load_env()
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        print("ERROR: faltan TELEGRAM_API_ID o TELEGRAM_API_HASH", file=sys.stderr)
        sys.exit(2)
    return int(api_id), api_hash


def make_client():
    # telethon.sync envuelve el cliente para que los métodos se puedan llamar
    # de forma síncrona desde un script no-async.
    from telethon.sync import TelegramClient
    api_id, api_hash = get_credentials()
    return TelegramClient(SESSION_PATH, api_id, api_hash)


def cmd_send_code(phone: str) -> None:
    client = make_client()
    client.connect()
    try:
        sent = client.send_code_request(phone)
        Path(PENDING_PATH).write_text(json.dumps({
            "phone": phone,
            "phone_code_hash": sent.phone_code_hash,
        }))
        os.chmod(PENDING_PATH, 0o600)
        print(f"OK: código enviado a {phone}. Revisa la app de Telegram.")
    finally:
        client.disconnect()


def cmd_sign_in(code: str) -> None:
    if not Path(PENDING_PATH).exists():
        print("ERROR: no hay send-code previo (falta _pending.json)", file=sys.stderr)
        sys.exit(2)
    pending = json.loads(Path(PENDING_PATH).read_text())
    client = make_client()
    client.connect()
    try:
        from telethon.errors import SessionPasswordNeededError
        try:
            user = client.sign_in(
                phone=pending["phone"],
                code=code,
                phone_code_hash=pending["phone_code_hash"],
            )
        except SessionPasswordNeededError:
            print("NEEDS_2FA: hay password de verificación en dos pasos. "
                  "Ejecuta: telegram_cli password '<tu_password>'")
            return
        Path(PENDING_PATH).unlink(missing_ok=True)
        print(f"OK: sesión iniciada como {user.first_name} ({user.id})")
    finally:
        client.disconnect()


def cmd_password(password: str) -> None:
    client = make_client()
    client.connect()
    try:
        user = client.sign_in(password=password)
        Path(PENDING_PATH).unlink(missing_ok=True)
        print(f"OK: sesión iniciada con 2FA como {user.first_name} ({user.id})")
    finally:
        client.disconnect()


def cmd_whoami() -> None:
    client = make_client()
    client.connect()
    try:
        if not client.is_user_authorized():
            print("NO_SESSION: la sesión no está autenticada")
            sys.exit(1)
        me = client.get_me()
        print(json.dumps({
            "id": me.id,
            "first_name": me.first_name,
            "username": me.username,
            "phone": me.phone,
        }))
    finally:
        client.disconnect()


def cmd_find_chat(query: str) -> None:
    client = make_client()
    client.connect()
    try:
        if not client.is_user_authorized():
            print("NO_SESSION", file=sys.stderr)
            sys.exit(1)
        matches = []
        for d in client.iter_dialogs():
            title = (d.title or "")
            if query.lower() in title.lower():
                matches.append({
                    "id": d.id,
                    "title": title,
                    "type": type(d.entity).__name__,
                })
        print(json.dumps(matches, indent=2, ensure_ascii=False))
    finally:
        client.disconnect()


def cmd_send_photo(chat_id: str, path: str, caption: str) -> None:
    client = make_client()
    client.connect()
    try:
        if not client.is_user_authorized():
            print("NO_SESSION", file=sys.stderr)
            sys.exit(1)
        target = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
        msg = client.send_file(target, path, caption=caption)
        print(f"OK: mensaje {msg.id} enviado a {target}")
    finally:
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("send-code"); sp.add_argument("phone")
    sp = sub.add_parser("sign-in"); sp.add_argument("code")
    sp = sub.add_parser("password"); sp.add_argument("password")
    sub.add_parser("whoami")
    sp = sub.add_parser("find-chat"); sp.add_argument("query")
    sp = sub.add_parser("send-photo")
    sp.add_argument("chat_id")
    sp.add_argument("path")
    sp.add_argument("caption", nargs="?", default="")

    args = parser.parse_args()
    if args.cmd == "send-code":
        cmd_send_code(args.phone)
    elif args.cmd == "sign-in":
        cmd_sign_in(args.code)
    elif args.cmd == "password":
        cmd_password(args.password)
    elif args.cmd == "whoami":
        cmd_whoami()
    elif args.cmd == "find-chat":
        cmd_find_chat(args.query)
    elif args.cmd == "send-photo":
        cmd_send_photo(args.chat_id, args.path, args.caption)


if __name__ == "__main__":
    main()
