"""
Proceso de login a Garmin en background.

Se invoca desde garmin_cli.py send-code. Ejecuta login() con un prompt_mfa
que espera a que aparezca el código en /opt/runsync/sessions/_garmin_mfa_code.
Comunica su estado por /opt/runsync/sessions/_garmin_login_status.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

ENV_PATH = "/etc/runsync.env"
TOKENSTORE = "/opt/runsync/sessions/garmin"
MFA_CODE_FILE = "/opt/runsync/sessions/_garmin_mfa_code"
STATUS_FILE = "/opt/runsync/sessions/_garmin_login_status"


def set_status(s: str) -> None:
    Path(STATUS_FILE).write_text(s)


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


def wait_for_code() -> str:
    """Callback prompt_mfa: bloquea hasta que aparezca el código en el fichero."""
    set_status("AWAITING_CODE")
    p = Path(MFA_CODE_FILE)
    waited = 0
    while not p.exists():
        time.sleep(1)
        waited += 1
        if waited > 600:  # 10 min máximo
            raise TimeoutError("Tiempo agotado esperando código MFA")
    code = p.read_text().strip()
    p.unlink(missing_ok=True)
    set_status("CODE_RECEIVED")
    return code


def main() -> None:
    load_env()
    set_status("STARTING")
    try:
        from garminconnect import Garmin
        u = os.environ.get("GARMIN_USERNAME")
        pw = os.environ.get("GARMIN_PASSWORD")
        if not u or not pw:
            set_status("ERROR: missing credentials")
            sys.exit(2)

        api = Garmin(u, pw, prompt_mfa=wait_for_code)
        api.login(tokenstore=TOKENSTORE)
        set_status("OK")
        print(f"login ok: display_name={api.display_name!r} full_name={api.full_name!r}")
    except Exception as e:
        set_status(f"ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
