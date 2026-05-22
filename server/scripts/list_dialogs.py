"""Lista la cuenta logueada en la sesión de Telethon y TODOS sus diálogos."""
import os
from pathlib import Path

for line in Path("/etc/runsync.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from telethon.sync import TelegramClient

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]
session = "/opt/runsync/sessions/me"

client = TelegramClient(session, api_id, api_hash)
client.connect()
try:
    if not client.is_user_authorized():
        print("ERROR: sesión no autorizada")
        raise SystemExit(1)

    me = client.get_me()
    print(f"=== Sesión autenticada como: ===")
    print(f"  id={me.id}  username={getattr(me, 'username', None)!r}")
    print(f"  first_name={me.first_name!r}  phone={getattr(me, 'phone', None)!r}")
    print()
    print(f"{'TIPO':<10} {'ID':>16}  TÍTULO")
    print("-" * 70)
    total = 0
    for d in client.iter_dialogs():
        ent = d.entity
        if hasattr(ent, "megagroup") and ent.megagroup:
            tipo = "supergrupo"
        elif hasattr(ent, "broadcast") and ent.broadcast:
            tipo = "canal"
        elif ent.__class__.__name__ == "Chat":
            tipo = "grupo"
        elif ent.__class__.__name__ == "User":
            tipo = "privado"
        else:
            tipo = ent.__class__.__name__
        if tipo == "privado":
            continue
        title = getattr(ent, "title", None) or getattr(ent, "first_name", "?")
        print(f"{tipo:<10} {d.id:>16}  {title}")
        total += 1
    print()
    print(f"TOTAL grupos/canales: {total}")
finally:
    client.disconnect()
