# Deploy

Cómo desplegar runsync en una EC2 desde cero, y cómo aplicar cambios después.

## Requisitos previos

- EC2 con Amazon Linux 2023 / Ubuntu 22.04+. Acceso por **SSM** (sin SSH).
- Python 3.12.
- nginx 1.22+ con certbot.
- Dominio apuntando a la IP pública de la EC2.
- Cuentas con OAuth/credenciales en: Strava, intervals.icu, Garmin Connect, Telegram (API ID + HASH desde my.telegram.org).

## Layout del filesystem

```
/opt/runsync/
├── app/                    ← código (este repo, carpeta server/app/)
├── venv/                   ← virtualenv
├── sessions/               ← tokens persistentes (no commitear)
├── requirements.txt
└── Sincronizar_Entreno.shortcut  ← opcional, servido vía /shortcut

/etc/runsync.env            ← variables, mode 600 owned by runsync
/etc/systemd/system/runsync.service
/etc/nginx/sites-enabled/api.sahuquillo.org
```

## Bootstrap inicial

### 1. Sistema

```bash
sudo useradd --system --shell /usr/sbin/nologin --home-dir /opt/runsync runsync
sudo mkdir -p /opt/runsync
sudo chown runsync:runsync /opt/runsync
sudo apt install python3.12 python3.12-venv nginx
sudo -u runsync python3.12 -m venv /opt/runsync/venv
```

### 2. Código

Copia `server/app/` a `/opt/runsync/app/`, `server/requirements.txt` a `/opt/runsync/`, e instala:

```bash
sudo -u runsync /opt/runsync/venv/bin/pip install -r /opt/runsync/requirements.txt
```

### 3. Configuración

```bash
sudo cp server/systemd/runsync.service /etc/systemd/system/
sudo cp runsync.env.example /etc/runsync.env
sudo chmod 600 /etc/runsync.env
sudo chown runsync:runsync /etc/runsync.env
# Editar /etc/runsync.env con los valores reales
sudo systemctl daemon-reload
sudo systemctl enable --now runsync.service
```

### 4. Nginx + TLS

Ejemplo mínimo:

```nginx
server {
    listen 443 ssl http2;
    server_name api.sahuquillo.org;
    ssl_certificate     /etc/letsencrypt/live/api.sahuquillo.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.sahuquillo.org/privkey.pem;
    client_max_body_size 20M;   # ¡imagen base64 pesa!

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Y obtén el cert con `certbot --nginx -d api.sahuquillo.org`.

### 5. Bootstrap de sesiones

#### Strava
1. En Strava, configura la app OAuth y pon como callback `https://api.sahuquillo.org/strava/callback`.
2. Visita la URL de authorize con scopes `read,activity:write,activity:read_all`.
3. El callback intercambia el code por tokens y los guarda en `/opt/runsync/sessions/strava.json`.

#### Garmin (MFA email)
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli send-code
# Garmin te envía un email con un código
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli sign-in 123456
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli whoami
```

#### Telegram (Telethon)
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli send-code +34XXXXXXXXX
# Telegram te envía un código por SMS o por la app
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli sign-in 12345
# Si hay 2FA:
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli password 'tu_2fa'
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli whoami
```

Para localizar los chat IDs:
```bash
sudo -u runsync /opt/runsync/venv/bin/python server/scripts/list_dialogs.py
```

Añade los chat IDs (separados por coma) a `TELEGRAM_CHAT_ID` en `/etc/runsync.env` y reinicia.

## Cambios posteriores

El acceso al servidor en este setup es **SSM-only**. Patrón típico:

```bash
# Desde el Mac, con AWS_PROFILE=entrenandoany
B64=$(base64 -i server/app/main.py | tr -d '\n')
AWS_PROFILE=entrenandoany aws ssm send-command \
    --region eu-west-3 \
    --instance-ids i-0b7f4135fd87a0a80 \
    --document-name AWS-RunShellScript \
    --parameters commands="[\"
        set -e
        cp /opt/runsync/app/main.py /opt/runsync/app/main.py.bak.\$(date +%s)
        echo '$B64' | base64 -d > /tmp/main.py.new
        chown runsync:runsync /tmp/main.py.new
        mv /tmp/main.py.new /opt/runsync/app/main.py
        /opt/runsync/venv/bin/python -c 'import ast; ast.parse(open(\\\"/opt/runsync/app/main.py\\\").read())'
        systemctl restart runsync.service
        sleep 2
        systemctl is-active runsync.service
    \"]"
```

Patrón explicado:
1. Base64 local del fichero a subir.
2. Backup del actual en el servidor.
3. Escribe a `/tmp` primero y mueve atómicamente (evita estado parcial).
4. `ast.parse` para validar sintaxis antes de tocar el servicio.
5. Restart + check `is-active`.

## Logs

```bash
sudo journalctl -u runsync.service -n 100 --no-pager
sudo journalctl -u runsync.service -f               # tail
```

## Salud

```bash
curl https://api.sahuquillo.org/health
# {"ok":true,"service":"runsync"}
```

## Rollback rápido

Los `.bak.<epoch>` están en el mismo directorio:

```bash
ls -lt /opt/runsync/app/main.py.bak.* | head -3
sudo cp /opt/runsync/app/main.py.bak.<epoch> /opt/runsync/app/main.py
sudo systemctl restart runsync.service
```
