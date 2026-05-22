"""
CLI auxiliar para gestionar la sesión de Garmin Connect en el servidor.

Login en dos pasos vía proceso en background (porque garminconnect mantiene
estado MFA en memoria del proceso). El send-code arranca un proceso que se
queda esperando el código en un fichero; sign-in escribe el código en ese
fichero y el proceso completa el login.

Uso:
    garmin_cli send-code            # arranca login en background, dispara MFA
    garmin_cli sign-in 123456       # escribe el código, espera y reporta
    garmin_cli whoami               # comprueba sesión válida y muestra perfil
    garmin_cli list-gear            # lista equipamiento con sus IDs
    garmin_cli last-activity        # muestra la última actividad
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TOKENSTORE = "/opt/runsync/sessions/garmin"
ENV_PATH = "/etc/runsync.env"

# Ficheros de coordinación con el proceso de login en background
MFA_CODE_FILE = "/opt/runsync/sessions/_garmin_mfa_code"
MFA_STATUS_FILE = "/opt/runsync/sessions/_garmin_login_status"
MFA_LOG_FILE = "/opt/runsync/sessions/_garmin_login.log"
MFA_PID_FILE = "/opt/runsync/sessions/_garmin_login.pid"
BG_SCRIPT = "/opt/runsync/app/garmin_login_bg.py"


def load_env() -> None:
    p = Path(ENV_PATH)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def get_creds() -> tuple[str, str]:
    load_env()
    u = os.environ.get("GARMIN_USERNAME")
    p = os.environ.get("GARMIN_PASSWORD")
    if not u or not p:
        print("ERROR: faltan GARMIN_USERNAME o GARMIN_PASSWORD", file=sys.stderr)
        sys.exit(2)
    return u, p


def make_client(return_on_mfa: bool = False):
    from garminconnect import Garmin
    u, p = get_creds()
    return Garmin(u, p, return_on_mfa=return_on_mfa)


def _cleanup_pending() -> None:
    for f in (MFA_CODE_FILE, MFA_STATUS_FILE, MFA_LOG_FILE, MFA_PID_FILE):
        Path(f).unlink(missing_ok=True)


def _read_status() -> str:
    p = Path(MFA_STATUS_FILE)
    return p.read_text().strip() if p.exists() else "(no_status)"


def cmd_send_code() -> None:
    # Si ya hay un proceso en marcha, matarlo
    pid_path = Path(MFA_PID_FILE)
    if pid_path.exists():
        try:
            old_pid = int(pid_path.read_text().strip())
            os.kill(old_pid, 9)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    _cleanup_pending()

    # Arrancar el proceso de background
    proc = subprocess.Popen(
        ["/opt/runsync/venv/bin/python", BG_SCRIPT],
        stdout=open(MFA_LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    Path(MFA_PID_FILE).write_text(str(proc.pid))

    # Esperar hasta que el bg llegue a AWAITING_CODE (o falle)
    for _ in range(45):
        time.sleep(1)
        s = _read_status()
        if s in ("AWAITING_CODE", "OK"):
            break
        if s.startswith("ERROR"):
            break
        if proc.poll() is not None:
            break

    s = _read_status()
    if s == "AWAITING_CODE":
        print("OK: MFA disparado. Garmin te habrá enviado un código por email. "
              "Ejecuta: garmin_cli sign-in <codigo>")
    elif s == "OK":
        print("OK: login completado sin MFA (tokens reutilizados o cuenta sin 2FA).")
    else:
        print(f"ERROR: estado {s!r}. Revisa {MFA_LOG_FILE}")
        if Path(MFA_LOG_FILE).exists():
            print("--- LOG ---")
            print(Path(MFA_LOG_FILE).read_text()[-2000:])
        sys.exit(1)


def cmd_sign_in(code: str) -> None:
    if _read_status() != "AWAITING_CODE":
        print(f"ERROR: el proceso de login no está esperando código (estado: {_read_status()!r}). "
              "Ejecuta primero send-code.", file=sys.stderr)
        sys.exit(2)
    Path(MFA_CODE_FILE).write_text(code)
    os.chmod(MFA_CODE_FILE, 0o600)

    # Esperar al desenlace
    for _ in range(60):
        time.sleep(1)
        s = _read_status()
        if s == "OK" or s.startswith("ERROR"):
            break

    s = _read_status()
    if s == "OK":
        print("OK: login completado, tokens guardados.")
        _cleanup_pending()
    else:
        print(f"ERROR: estado {s!r}. Revisa {MFA_LOG_FILE}", file=sys.stderr)
        if Path(MFA_LOG_FILE).exists():
            print("--- LOG ---", file=sys.stderr)
            print(Path(MFA_LOG_FILE).read_text()[-2000:], file=sys.stderr)
        sys.exit(1)


def cmd_whoami() -> None:
    api = make_client()
    api.login(tokenstore=TOKENSTORE)
    me = {
        "username": api.username,
        "display_name": api.display_name,
        "full_name": api.full_name,
        "unit_system": api.unit_system,
    }
    print(json.dumps(me, indent=2, ensure_ascii=False))


def cmd_list_gear() -> None:
    """Lista equipamiento ACTIVO con sus UUIDs para el mapeo."""
    api = make_client()
    api.login(tokenstore=TOKENSTORE)
    # Necesitamos profileId del perfil social (no el id de usuario)
    profile = api.connectapi("/userprofile-service/socialProfile")
    profile_pk = profile.get("profileId")
    if not profile_pk:
        print("ERROR: profileId no encontrado en el perfil", file=sys.stderr)
        sys.exit(1)
    gear = api.get_gear(profile_pk) or []
    active = [g for g in gear if g.get("gearStatusName") == "active"]
    simplified = [{
        "uuid": g.get("uuid"),
        "gearPk": g.get("gearPk"),
        "displayName": g.get("displayName"),
        "customMakeModel": g.get("customMakeModel"),
        "type": g.get("gearTypeName"),
    } for g in active]
    print(json.dumps({"profileId": profile_pk, "active_count": len(active), "gear": simplified},
                     indent=2, ensure_ascii=False))


def cmd_last_activity() -> None:
    api = make_client()
    api.login(tokenstore=TOKENSTORE)
    acts = api.get_activities(0, 1)
    if not acts:
        print("(sin actividades)")
        return
    a = acts[0]
    print(json.dumps({
        "activityId": a.get("activityId"),
        "activityName": a.get("activityName"),
        "startTimeLocal": a.get("startTimeLocal"),
        "type": (a.get("activityType") or {}).get("typeKey"),
        "distance_km": round((a.get("distance") or 0) / 1000.0, 2),
        "duration_min": round((a.get("duration") or 0) / 60.0, 1),
    }, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("send-code")
    sp = sub.add_parser("sign-in"); sp.add_argument("code")
    sub.add_parser("whoami")
    sub.add_parser("list-gear")
    sub.add_parser("last-activity")
    args = parser.parse_args()
    if args.cmd == "send-code":
        cmd_send_code()
    elif args.cmd == "sign-in":
        cmd_sign_in(args.code)
    elif args.cmd == "whoami":
        cmd_whoami()
    elif args.cmd == "list-gear":
        cmd_list_gear()
    elif args.cmd == "last-activity":
        cmd_last_activity()


if __name__ == "__main__":
    main()
