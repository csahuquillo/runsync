# Deployment guide

📖 **[Leer en español](deploy.es.md)**

This guide walks you through deploying runsync on a Linux VPS from scratch. Estimated time: 1-2 hours including the OAuth/MFA bootstraps.

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Server provisioning](#2-server-provisioning)
3. [Code & dependencies](#3-code--dependencies)
4. [Configuration](#4-configuration)
5. [Session bootstrap](#5-session-bootstrap)
6. [nginx + TLS](#6-nginx--tls)
7. [Verify](#7-verify)
8. [Updating code](#8-updating-code)
9. [Backups](#9-backups)
10. [Hardening checklist](#10-hardening-checklist)

---

## 1. Prerequisites

- A Linux server you control: Ubuntu 22.04+ or Debian 12 recommended. As little as 1 GB RAM is enough.
- A domain you own and can point at the server's IP.
- Python 3.12 available (most modern distros).
- Accounts on the services you want to sync to:
  - **Strava** with API access ([create app](https://www.strava.com/settings/api)).
  - **intervals.icu** (Settings → API).
  - **Garmin Connect** with your real email + password.
  - **Telegram** with API ID + Hash from [my.telegram.org](https://my.telegram.org).

---

## 2. Server provisioning

Create a dedicated, unprivileged user that will own everything:

```bash
sudo useradd --system --shell /usr/sbin/nologin --home-dir /opt/runsync runsync
sudo mkdir -p /opt/runsync
sudo chown runsync:runsync /opt/runsync
```

Install system packages:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv nginx certbot python3-certbot-nginx
```

Create the Python virtualenv:

```bash
sudo -u runsync python3.12 -m venv /opt/runsync/venv
sudo -u runsync /opt/runsync/venv/bin/pip install --upgrade pip
```

---

## 3. Code & dependencies

Copy the application code from this repo into `/opt/runsync/`. The easiest is via `scp`/`rsync` from your laptop, or `git clone` directly on the server:

```bash
# Option A: git clone on the server
cd /tmp
git clone https://github.com/csahuquillo/runsync.git
sudo cp -r runsync/server/app /opt/runsync/
sudo cp runsync/server/requirements.txt /opt/runsync/
sudo chown -R runsync:runsync /opt/runsync/app
sudo chown runsync:runsync /opt/runsync/requirements.txt

# Option B: scp from your laptop
scp -r server/app server/requirements.txt your-server:/tmp/
ssh your-server 'sudo mv /tmp/app /opt/runsync/ && sudo mv /tmp/requirements.txt /opt/runsync/ && sudo chown -R runsync:runsync /opt/runsync'
```

Install Python deps:

```bash
sudo -u runsync /opt/runsync/venv/bin/pip install -r /opt/runsync/requirements.txt
```

You should end up with:

```
/opt/runsync/
├── app/                ← Python package (main.py, connectors.py, gear_map.py, ...)
├── venv/               ← virtualenv
├── requirements.txt
└── sessions/           ← will be created by the bootstrap scripts later
```

Create the sessions dir now so the first bootstrap script can write to it:

```bash
sudo -u runsync mkdir -p /opt/runsync/sessions
sudo chmod 700 /opt/runsync/sessions
```

---

## 4. Configuration

### Generate a Bearer token

```bash
openssl rand -hex 32
```

Copy the output — that's your `RUNSYNC_TOKEN`. The iOS Shortcut will send it in the `Authorization: Bearer ...` header. Don't reuse a password.

### Write `/etc/runsync.env`

Use the template:

```bash
sudo cp runsync.env.example /etc/runsync.env
sudo chmod 600 /etc/runsync.env
sudo chown runsync:runsync /etc/runsync.env
sudo nano /etc/runsync.env   # or your editor of choice
```

Fill in each variable. Detailed instructions for each:

#### `RUNSYNC_TOKEN`
The hex string you just generated.

#### Strava — `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
1. Visit https://www.strava.com/settings/api.
2. Click *Create App* (or use an existing one). Fill in any application name and category.
3. **Authorization Callback Domain**: set this to your domain (e.g. `api.your-domain.com`). Strava needs this to allow the OAuth redirect.
4. After creation, copy:
   - **Client ID** → `STRAVA_CLIENT_ID`.
   - **Client Secret** → `STRAVA_CLIENT_SECRET` (you have to click the eye icon to reveal it).

#### intervals.icu — `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`
1. Log in to https://intervals.icu.
2. Top-right user menu → *Settings* → *Developer*.
3. **API key**: click to reveal/copy → `INTERVALS_API_KEY`.
4. **Athlete ID**: same page; it looks like `i12345`. Use the *whole* thing including the leading `i` → `INTERVALS_ATHLETE_ID`.

#### Garmin Connect — `GARMIN_USERNAME`, `GARMIN_PASSWORD`
Just your normal login email and password. The `garmin_cli` script will handle 2FA the first time.

> If your Garmin account uses MFA via email (default for new accounts), keep the email account ready — you'll need it during the bootstrap.

#### Telegram — `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_CHAT_ID`
1. Visit https://my.telegram.org and log in with your phone number.
2. Click *API development tools*.
3. Create a new application (any name; platform "Desktop"). You get:
   - **App api_id** → `TELEGRAM_API_ID`
   - **App api_hash** → `TELEGRAM_API_HASH`
4. `TELEGRAM_CHAT_ID`: leave as a placeholder for now. After the session bootstrap below, you'll list your groups and pick the chat IDs.

### Install the systemd unit

```bash
sudo cp server/systemd/runsync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable runsync.service
sudo systemctl start runsync.service
sudo systemctl status runsync.service
```

The service won't be reachable from outside yet (it binds to `127.0.0.1:8000`), but `curl http://127.0.0.1:8000/health` on the server itself should return `{"ok":true,"service":"runsync"}`.

---

## 5. Session bootstrap

### 5.1 Strava OAuth

1. Build the authorize URL (replace `CLIENT_ID` and `YOUR_DOMAIN`):
   ```
   https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=https://YOUR_DOMAIN/strava/callback&scope=read,activity:write,activity:read_all&approval_prompt=auto
   ```
2. Open it in your browser. Log in to Strava if needed and click *Authorize*.
3. Strava redirects to `https://YOUR_DOMAIN/strava/callback?code=...`. The server exchanges the code for tokens and stores them at `/opt/runsync/sessions/strava.json`.
4. You should see a success page in the browser.

To test:
```bash
sudo cat /opt/runsync/sessions/strava.json | head -1
# should contain access_token, refresh_token, expires_at, athlete.id, ...
```

The tokens refresh automatically on use.

### 5.2 Garmin Connect with MFA

```bash
# 1. Trigger MFA — Garmin emails you a code
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli send-code

# 2. When the code arrives, paste it (replace 123456):
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli sign-in 123456

# 3. Verify
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli whoami
# should print your display name etc. in JSON
```

Get your Garmin gear UUIDs (needed for `gear_map.py`):
```bash
sudo -u runsync /opt/runsync/venv/bin/python -m app.garmin_cli list-gear
```

### 5.3 Telegram session

```bash
# 1. Send Telegram a code request (phone in +countryNumber format)
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli send-code +34600111222

# 2. A code arrives in the Telegram app — paste it
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli sign-in 12345

# 3. If you have 2FA enabled on Telegram:
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli password 'your-2fa-password'

# 4. Verify
sudo -u runsync /opt/runsync/venv/bin/python -m app.telegram_cli whoami
```

List all the groups/channels you're in to pick the chat IDs:
```bash
sudo -u runsync /opt/runsync/venv/bin/python server/scripts/list_dialogs.py
```

The output looks like:
```
supergroup    -1001234567890  My Running Group
group           -432167890    Friends only
...
```

Pick the IDs you want and put them in `TELEGRAM_CHAT_ID` separated by commas:
```bash
sudo nano /etc/runsync.env
# TELEGRAM_CHAT_ID=-1001234567890,-432167890
sudo systemctl restart runsync.service
```

### 5.4 Replace gear placeholders

Edit `server/app/gear_map.py` (locally, then deploy with `scripts/deploy.sh`) to replace the example shoes with your real ones:

```python
GEAR: dict[str, GearEntry] = {
    "Adidas Boston 13": {
        "canonical": "Adidas Boston 13",
        "garmin_uuid": "<UUID-from-garmin_cli-list-gear>",
        "intervals_id": "<id-from-intervals.icu-equipment-URL>",
        "strava_id": "g<id-from-strava-gear-URL>",
    },
    ...
}
```

Deploy:
```bash
# From your laptop (requires AWS SSM access — see "Updating code" below)
INSTANCE_ID=i-xxxxxxxxx AWS_PROFILE=myprofile scripts/deploy.sh gear_map.py
```

Or just scp + restart if you're not using SSM.

---

## 6. nginx + TLS

A minimal nginx server block:

```nginx
server {
    listen 80;
    server_name api.your-domain.com;

    # Let certbot handle the cert; this block will be rewritten by certbot.
    location / {
        return 404;
    }
}
```

Save to `/etc/nginx/sites-available/api.your-domain.com`, link, reload:

```bash
sudo ln -s /etc/nginx/sites-available/api.your-domain.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Get a cert with Let's Encrypt:

```bash
sudo certbot --nginx -d api.your-domain.com
```

Now make the final server block proxy to uvicorn. Replace the `location /` from certbot's edit with:

```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;
    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    # Base64-encoded images are large — bump the limit.
    client_max_body_size 20M;

    # Optional but recommended: rate limit /sync-workout
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

To enable the rate-limit zone, add this once near the top of `/etc/nginx/nginx.conf` inside the `http {}` block:

```nginx
limit_req_zone $binary_remote_addr zone=runsync:10m rate=10r/m;
```

Reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. Verify

```bash
curl https://api.your-domain.com/health
# {"ok":true,"service":"runsync"}

# Test /debug-form (no auth needed):
RUNSYNC_URL=https://api.your-domain.com scripts/check-debug-form.sh
# Should return a JSON with content_type=multipart/...; fields={name, shoes, tags, image}
```

If both work, the backend is ready. Now build the iOS Shortcut — see [atajo-setup.md](atajo-setup.md).

---

## 8. Updating code

### Option A: AWS SSM (no SSH needed)

If your server is on AWS EC2 with Systems Manager agent:

```bash
INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=myprofile \
  scripts/deploy.sh main.py                   # single file
INSTANCE_ID=i-0123456789abcdef0 AWS_PROFILE=myprofile \
  scripts/deploy.sh main.py connectors.py     # multiple files
```

The script:
1. Base64-encodes the file locally.
2. Uploads via SSM, backs up the current file as `*.bak.<epoch>`.
3. Writes atomically with `mv` (no half-written state).
4. Validates Python syntax with `ast.parse`.
5. Restarts `runsync.service` and checks `is-active`.

### Option B: Plain SSH

```bash
scp server/app/main.py your-server:/tmp/main.py.new
ssh your-server '
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

The files that matter for state:

| File | What it holds | Backup? |
|---|---|---|
| `/etc/runsync.env` | All credentials + chat IDs | YES (encrypted!) |
| `/opt/runsync/sessions/strava.json` | OAuth tokens (auto-refreshed) | Optional — easy to redo |
| `/opt/runsync/sessions/garmin/` | Garmin tokenstore | Optional |
| `/opt/runsync/sessions/me.session` | Telethon session | Recommended — re-bootstrap requires SMS |

Suggested: `/etc/runsync.env` and `me.session` in a password manager or encrypted backup.

---

## 10. Hardening checklist

- [ ] `/etc/runsync.env` is `chmod 600` and owned by `runsync:runsync`.
- [ ] `/opt/runsync/sessions/` is `chmod 700` and owned by `runsync:runsync`.
- [ ] systemd unit uses `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=true` (the shipped unit does).
- [ ] `RUNSYNC_TOKEN` is a fresh random hex string, not reused from anywhere.
- [ ] TLS is enforced (HTTP→HTTPS redirect; certbot adds this by default).
- [ ] nginx has rate limiting on `/sync-workout`.
- [ ] Firewall: only ports 22 (or your SSH port) and 443 (HTTPS) open inbound. 80 only if you use HTTP→HTTPS redirect.
- [ ] No `.shortcut` file committed to git (the `.gitignore` excludes them).
- [ ] No `.env` or sessions in git.
- [ ] Server has unattended security updates enabled (`sudo apt install unattended-upgrades`).
- [ ] You have a way to rotate the Bearer token (changing `RUNSYNC_TOKEN` + restarting the service + updating the Shortcut on the iPhone takes 2 minutes).

## Rollback

`.bak.<epoch>` files are kept in the same directory:

```bash
ls -lt /opt/runsync/app/main.py.bak.* | head -3
sudo cp /opt/runsync/app/main.py.bak.<epoch> /opt/runsync/app/main.py
sudo systemctl restart runsync.service
```
