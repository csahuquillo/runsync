# Guía de despliegue

📖 **[Read in English](deploy.md)**

Esta guía explica cómo desplegar runsync en un VPS Linux desde cero. Tiempo estimado: 1-2 h incluyendo bootstraps de OAuth/MFA.

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Provisión del servidor](#2-provisión-del-servidor)
3. [Código y dependencias](#3-código-y-dependencias)
4. [Configuración](#4-configuración)
5. [Bootstrap de sesiones](#5-bootstrap-de-sesiones)
6. [nginx + TLS](#6-nginx--tls)
7. [Verificar](#7-verificar)
8. [Actualizar código](#8-actualizar-código)
9. [Backups](#9-backups)
10. [Checklist de hardening](#10-checklist-de-hardening)

---

## 1. Requisitos previos

- Un servidor Linux bajo tu control: Ubuntu 22.04+ o Debian 12 recomendado. Con 1 GB de RAM va sobrado.
- Un dominio tuyo apuntable a la IP del servidor.
- Python 3.12 disponible (la mayoría de distros modernas).
- Cuentas en los servicios donde quieras sincronizar:
  - **Strava** con acceso API ([crear app](https://www.strava.com/settings/api)).
  - **intervals.icu** (Settings → API).
  - **Garmin Connect** con tu email y contraseña reales.
  - **Telegram** con API ID + Hash desde [my.telegram.org](https://my.telegram.org).

---

## 2. Provisión del servidor

Usuario dedicado, sin privilegios, dueño de todo:

```bash
sudo useradd --system --shell /usr/sbin/nologin --home-dir /opt/runsync runsync
sudo mkdir -p /opt/runsync
sudo chown runsync:runsync /opt/runsync
```

Paquetes del sistema:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv nginx certbot python3-certbot-nginx
```

Virtualenv:

```bash
sudo -u runsync python3.12 -m venv /opt/runsync/venv
sudo -u runsync /opt/runsync/venv/bin/pip install --upgrade pip
```

---

## 3. Código y dependencias

Copia el código de la app a `/opt/runsync/`. Lo más fácil es `scp`/`rsync` desde tu portátil, o `git clone` directamente en el servidor:

```bash
# Opción A: git clone en el servidor
cd /tmp
git clone https://github.com/csahuquillo/runsync.git
sudo cp -r runsync/server/app /opt/runsync/
sudo cp runsync/server/requirements.txt /opt/runsync/
sudo chown -R runsync:runsync /opt/runsync/app
sudo chown runsync:runsync /opt/runsync/requirements.txt

# Opción B: scp desde tu portátil
scp -r server/app server/requirements.txt tu-servidor:/tmp/
ssh tu-servidor 'sudo mv /tmp/app /opt/runsync/ && sudo mv /tmp/requirements.txt /opt/runsync/ && sudo chown -R runsync:runsync /opt/runsync'
```

Instala las deps:

```bash
sudo -u runsync /opt/runsync/venv/bin/pip install -r /opt/runsync/requirements.txt
```

Deberías tener:

```
/opt/runsync/
├── app/                ← paquete Python (main.py, connectors.py, gear_map.py, ...)
├── venv/               ← virtualenv
├── requirements.txt
└── sessions/           ← se crea al hacer el bootstrap
```

Crea ya el `sessions/`:

```bash
sudo -u runsync mkdir -p /opt/runsync/sessions
sudo chmod 700 /opt/runsync/sessions
```

---

## 4. Configuración

### Genera el Bearer token

```bash
openssl rand -hex 32
```

Copia la salida — ese es tu `RUNSYNC_TOKEN`. El Atajo iOS lo envía en la cabecera `Authorization: Bearer ...`. **No reutilices una contraseña.**

### Escribe `/etc/runsync.env`

Plantilla:

```bash
sudo cp runsync.env.example /etc/runsync.env
sudo chmod 600 /etc/runsync.env
sudo chown runsync:runsync /etc/runsync.env
sudo nano /etc/runsync.env
```

Detalle de cada variable:

#### `RUNSYNC_TOKEN`
La cadena hex que acabas de generar.

#### Strava — `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
1. Entra en https://www.strava.com/settings/api.
2. *Create App* (o usa una existente). Cualquier nombre y categoría.
3. **Authorization Callback Domain**: tu dominio (ej. `api.tudominio.com`). Strava necesita esto para permitir el redirect.
4. Copia:
   - **Client ID** → `STRAVA_CLIENT_ID`.
   - **Client Secret** → `STRAVA_CLIENT_SECRET` (click en el ojo para revelar).

#### intervals.icu — `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`
1. Login en https://intervals.icu.
2. Menú usuario (arriba derecha) → *Settings* → *Developer*.
3. **API key**: revela y copia → `INTERVALS_API_KEY`.
4. **Athlete ID**: misma página; algo tipo `i12345`. Usa la cadena entera con la `i` inicial → `INTERVALS_ATHLETE_ID`.

#### Garmin Connect — `GARMIN_USERNAME`, `GARMIN_PASSWORD`
Tu email y contraseña de Garmin Connect. El `garmin_cli` gestiona el MFA en el bootstrap.

> Si Garmin te tiene activado el MFA por email (default en cuentas nuevas), ten ese email a mano: hace falta durante el bootstrap.

#### Telegram — `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_CHAT_ID`
1. Entra en https://my.telegram.org con tu teléfono.
2. *API development tools*.
3. Crea aplicación nueva (cualquier nombre; plataforma "Desktop"). Obtienes:
   - **App api_id** → `TELEGRAM_API_ID`.
   - **App api_hash** → `TELEGRAM_API_HASH`.
4. `TELEGRAM_CHAT_ID`: déjalo como placeholder ahora. Tras el bootstrap listarás los grupos y eliges los IDs.

### Instala el unit de systemd

```bash
sudo cp server/systemd/runsync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable runsync.service
sudo systemctl start runsync.service
sudo systemctl status runsync.service
```

El servicio no responde desde fuera todavía (bindea `127.0.0.1:8000`), pero `curl http://127.0.0.1:8000/health` desde el propio servidor debe devolver `{"ok":true,"service":"runsync"}`.

---

## 5. Bootstrap de sesiones

### 5.1 Strava OAuth

1. Construye la URL de authorize (sustituye `CLIENT_ID` y `TU_DOMINIO`):
   ```
   https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=https://TU_DOMINIO/strava/callback&scope=read,activity:write,activity:read_all&approval_prompt=auto
   ```
2. Ábrela en el navegador. Login en Strava si hace falta y *Authorize*.
3. Strava te redirige a `https://TU_DOMINIO/strava/callback?code=...`. El servidor intercambia el code por tokens y los guarda en `/opt/runsync/sessions/strava.json`.
4. Verás la página de éxito en el navegador.

Para verificar:
```bash
sudo head -1 /opt/runsync/sessions/strava.json
# debería contener access_token, refresh_token, expires_at, athlete.id, ...
```

Los tokens se refrescan automáticamente al usar la API.

### 5.2 Garmin Connect con MFA

```bash
# 1. Dispara el MFA — Garmin te envía un código por email
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli send-code

# 2. Cuando llegue el código (reemplaza 123456):
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli sign-in 123456

# 3. Verifica
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli whoami
```

UUIDs del gear de Garmin (para `gear_map.py`):
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli list-gear
```

### 5.3 Sesión de Telegram

```bash
# 1. Pide a Telegram el código (teléfono en formato +paísnúmero)
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli send-code +34600111222

# 2. Llega un código por la app de Telegram — pégalo
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli sign-in 12345

# 3. Si tienes 2FA activado en Telegram:
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli password 'tu-2fa'

# 4. Verifica
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli whoami
```

Lista grupos/canales en los que estás:
```bash
sudo -u runsync /opt/runsync/venv/bin/python server/scripts/list_dialogs.py
```

Salida:
```
supergroup    -1001234567890  Mi grupo de running
group           -432167890    Amigos
...
```

Mete los IDs en `TELEGRAM_CHAT_ID` separados por coma:
```bash
sudo nano /etc/runsync.env
# TELEGRAM_CHAT_ID=-1001234567890,-432167890
sudo systemctl restart runsync.service
```

### 5.4 Reemplaza los placeholders del gear

Edita `server/app/gear_map.py` (local, luego despliegas con `scripts/deploy.sh`) y reemplaza las zapatillas de ejemplo:

```python
GEAR: dict[str, GearEntry] = {
    "Adidas Boston 13": {
        "canonical": "Adidas Boston 13",
        "garmin_uuid": "<UUID-de-garmin_cli-list-gear>",
        "intervals_id": "<id-de-la-URL-de-equipment-en-intervals>",
        "strava_id": "g<id-de-la-URL-de-gear-en-strava>",
    },
    ...
}
```

Despliega:
```bash
INSTANCE_ID=i-xxxxxxxxx AWS_PROFILE=miprofile scripts/deploy.sh gear_map.py
```

O simplemente scp + restart si no usas SSM.

---

## 6. nginx + TLS

Server block mínimo inicial:

```nginx
server {
    listen 80;
    server_name api.tudominio.com;
    location / { return 404; }
}
```

A `/etc/nginx/sites-available/api.tudominio.com`, enlaza y recarga:

```bash
sudo ln -s /etc/nginx/sites-available/api.tudominio.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Certificado:

```bash
sudo certbot --nginx -d api.tudominio.com
```

Sustituye el `location /` que deja certbot por el bloque proxy completo:

```nginx
server {
    listen 443 ssl http2;
    server_name api.tudominio.com;
    ssl_certificate     /etc/letsencrypt/live/api.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.tudominio.com/privkey.pem;

    # Imágenes en base64 pesan — sube el límite
    client_max_body_size 20M;

    # Recomendado: rate limit en /sync-workout
    location = /sync-workout {
        limit_req zone=runsync burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Y en `/etc/nginx/nginx.conf`, dentro del bloque `http {}`, una sola vez:

```nginx
limit_req_zone $binary_remote_addr zone=runsync:10m rate=10r/m;
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. Verificar

```bash
curl https://api.tudominio.com/health
# {"ok":true,"service":"runsync"}

RUNSYNC_URL=https://api.tudominio.com scripts/check-debug-form.sh
# Debe devolver JSON con content_type=multipart/...; fields={name, shoes, tags, image}
```

Si ambos funcionan, el backend está listo. Construye ahora el Atajo iOS — ver [atajo-setup.es.md](atajo-setup.es.md).

---

## 8. Actualizar código

### Opción A: AWS SSM (sin SSH)

Si tu servidor es EC2 con SSM agent:

```bash
INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=miprofile \
  scripts/deploy.sh main.py                   # un fichero
INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=miprofile \
  scripts/deploy.sh main.py connectors.py     # varios
```

El script:
1. Base64 local del fichero.
2. Sube vía SSM, backup `*.bak.<epoch>`.
3. Escribe a `/tmp` y `mv` atómico.
4. Valida sintaxis con `ast.parse`.
5. Restart `runsync.service` y `is-active`.

### Opción B: SSH normal

```bash
scp server/app/main.py tu-servidor:/tmp/main.py.new
ssh tu-servidor '
  sudo cp /opt/runsync/app/main.py /opt/runsync/app/main.py.bak.$(date +%s)
  sudo chown runsync:runsync /tmp/main.py.new
  sudo mv /tmp/main.py.new /opt/runsync/app/main.py
  sudo -u runsync /opt/runsync/venv/bin/python -c "import ast; ast.parse(open(\"/opt/runsync/app/main.py\").read())"
  sudo systemctl restart runsync.service
  sleep 2 && sudo systemctl is-active runsync.service
'
```

---

## 9. Backups

| Fichero | Qué contiene | ¿Backup? |
|---|---|---|
| `/etc/runsync.env` | Todas las credenciales + chat IDs | SÍ (¡cifrado!) |
| `/opt/runsync/sessions/strava.json` | OAuth tokens (auto-refresh) | Opcional — fácil rehacer |
| `/opt/runsync/sessions/garmin/` | Tokenstore Garmin | Opcional |
| `/opt/runsync/sessions/me.session` | Sesión Telethon | Recomendado — re-bootstrap requiere SMS |

Sugerencia: `/etc/runsync.env` y `me.session` en gestor de contraseñas o backup cifrado.

---

## 10. Checklist de hardening

- [ ] `/etc/runsync.env` con `chmod 600` y propiedad `runsync:runsync`.
- [ ] `/opt/runsync/sessions/` con `chmod 700` y propiedad `runsync:runsync`.
- [ ] systemd unit usa `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=true` (el incluido sí).
- [ ] `RUNSYNC_TOKEN` es hex aleatorio fresco, no reutilizado.
- [ ] TLS obligatorio (redirect HTTP→HTTPS; certbot lo añade por defecto).
- [ ] nginx con rate limiting en `/sync-workout`.
- [ ] Firewall: solo 22 (o tu puerto SSH) y 443 abiertos inbound. 80 solo si usas redirect.
- [ ] Ningún `.shortcut` en git (el `.gitignore` los excluye).
- [ ] Ningún `.env` ni sessions en git.
- [ ] Servidor con actualizaciones de seguridad automáticas (`sudo apt install unattended-upgrades`).
- [ ] Tienes forma de rotar el Bearer token (cambiar `RUNSYNC_TOKEN` + restart servicio + actualizar Atajo en iPhone = 2 minutos).

## Rollback

`.bak.<epoch>` están en el mismo directorio:

```bash
ls -lt /opt/runsync/app/main.py.bak.* | head -3
sudo cp /opt/runsync/app/main.py.bak.<epoch> /opt/runsync/app/main.py
sudo systemctl restart runsync.service
```
