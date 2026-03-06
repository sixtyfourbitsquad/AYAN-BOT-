# Production Deployment Guide: Two Bots on One VPS

This guide walks you through deploying **two separate Telegram bots** (one per client) on a **single VPS**. Each bot has its own code directory, config, database, Redis DB, port, domain/subdomain, and systemd service.

---

## Will everything work without thinking?

**Short answer:** If you follow the guide **step by step** and **replace every placeholder** with your real values, you will get very close. A few things still need a human check:

| You must do yourself | Why the guide can’t do it |
|----------------------|---------------------------|
| **Use your real values** | Replace passwords, `BOT_TOKEN`, `ADMIN_IDS`, etc. with your actual data. This guide uses `ayanbot1.duckdns.org` and `ayanbot2.duckdns.org` as webhook domains. Wrong token or typo = bot won’t work. |
| **Get tokens and IDs** | Create each bot in [@BotFather](https://t.me/BotFather), get the token. Get your Telegram user ID (e.g. [@userinfobot](https://t.me/userinfobot)) for `ADMIN_IDS`. |
| **Fix paths/user if different** | Guide uses user `adii` and `/home/adii/`. If your Linux user or project path is different, change `User`, `WorkingDirectory`, and `ExecStart` in the systemd service file. |
| **Wait for DNS** | After adding A records (or DuckDNS), wait until domains resolve. Run `ping ayanbot1.duckdns.org` (and ayanbot2) until they show your VPS IP. |
| **Check one thing if it fails** | If the bot doesn’t start or doesn’t reply, use Section 5 (troubleshooting): `systemctl status`, `journalctl`, and the table there. |

If you do the above, the rest is copy-paste and following the order. No coding or “brain” needed beyond reading and replacing placeholders.

**Before you start – have these ready:**

- [ ] VPS IP and SSH access (user + password or SSH key)
- [ ] Two webhook domains: `ayanbot1.duckdns.org` and `ayanbot2.duckdns.org` (DuckDNS or DNS pointed to your VPS IP)
- [ ] Bot 1 token from BotFather and Bot 2 token from BotFather (or create two bots)
- [ ] Your Telegram user ID (and any other admins) for `ADMIN_IDS`
- [ ] Two strong passwords for the two PostgreSQL users (Bot 1 and Bot 2)

---

## Table of contents

1. [Production readiness checklist](#1-production-readiness-checklist)
2. [Prerequisites (one-time VPS setup)](#2-prerequisites-one-time-vps-setup)
3. [Deploy Bot 1 (Client 1)](#3-deploy-bot-1-client-1)
4. [Deploy Bot 2 (Client 2)](#4-deploy-bot-2-client-2)
5. [Daily operations and troubleshooting](#5-daily-operations-and-troubleshooting)
6. [Security and maintenance](#6-security-and-maintenance)

---

## 1. Production readiness checklist

Before deploying, the bot codebase is production-ready with:

| Item | Status |
|------|--------|
| **Error handling** | Global error handler logs exceptions and replies to users; handlers use try/except and logging |
| **Empty welcome** | If no welcome messages are set, users get "Welcome! No messages configured yet." instead of nothing |
| **Config validation** | `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL`, `REDIS_URL`, `WEBHOOK_URL` required; `CHANNEL_ID` and `WEBHOOK_PORT` validated when set |
| **Graceful shutdown** | On stop (SIGTERM/SIGINT), DB pool and Redis are closed cleanly |
| **Log file** | Admin "View Logs" sends file via context manager (no leaked file handles) |
| **Admin panel** | Add/Manage welcome messages, Set Channel, Preview, Stats, Broadcast, Config, Logs |

---

## 2. Prerequisites (one-time VPS setup)

Do this **once** per VPS. If you already have a server with Nginx, PostgreSQL, Redis, and SSL, skip to Section 3.

### 2.1 Server and access

- **VPS**: Ubuntu 22.04 LTS (or 24.04). Minimum 2 vCPU, 4 GB RAM; recommended 4 vCPU, 8 GB RAM for two bots.
- **User**: Create a non-root user (e.g. `adii`) with sudo.
- **Firewall**: Allow SSH (22), HTTP (80), HTTPS (443).

Detailed steps (create VPS, SSH, create user, firewall): see **VPS_HOSTING_GUIDE.md** → Part A (Steps 1–7).

### 2.2 Install software (once per server)

As your user (e.g. `adii`) or root:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx postgresql redis-server
```

- **PostgreSQL**: One instance; we will create **two databases** (one per bot).
- **Redis**: One instance; we will use **two DB indexes** (0 and 1) for the two bots.
- **Nginx**: Reverse proxy and SSL.
- **Certbot**: SSL certificates for your domains.

See **VPS_HOSTING_GUIDE.md** → Part B (Steps 8–10) for PostgreSQL and Redis setup.

### 2.3 Domains for the two bots

You need **two webhook URLs** (Telegram requires a unique URL per bot):

| Bot   | Webhook domain           | Purpose                    |
|-------|--------------------------|----------------------------|
| Bot 1 | `ayanbot1.duckdns.org`   | Webhook for Client 1’s bot |
| Bot 2 | `ayanbot2.duckdns.org`   | Webhook for Client 2’s bot |

Point both hostnames to your **VPS IP** (e.g. DuckDNS “IP” field, or A records in your DNS). Wait until they resolve (e.g. `ping ayanbot1.duckdns.org`).

---

## 3. Deploy Bot 1 (Client 1)

### Step 3.1 Create database and Redis DB for Bot 1

**PostgreSQL** – create a dedicated database and user (optional: same user, different DB):

```bash
sudo -u postgres psql
```

In `psql`:

```sql
CREATE USER bot1user WITH PASSWORD 'StrongPasswordForBot1';
CREATE DATABASE telegram_bot_client1 OWNER bot1user;
\q
```

Test:

```bash
psql -h localhost -U bot1user -d telegram_bot_client1 -c "SELECT 1;"
```

**Connection string for Bot 1:**  
`postgresql://bot1user:StrongPasswordForBot1@localhost:5432/telegram_bot_client1`

**Redis** for Bot 1 uses default DB index **0**. URL: `redis://localhost:6379/0`.

---

### Step 3.2 Create project directory for Bot 1

```bash
cd ~
git clone https://github.com/sixtyfourbitsquad/AYAN-BOT-.git telegram-bot-client1
cd telegram-bot-client1
```

If you don’t use Git, upload the project (e.g. `scp -r ./bot ./migrations requirements.txt .env.example run.py adii@SERVER_IP:~/telegram-bot-client1/`).

---

### Step 3.3 Python venv and dependencies

```bash
cd ~/telegram-bot-client1
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 3.4 Create `.env` for Bot 1

```bash
cp .env.example .env
nano .env
```

Use **Client 1’s** values (one bot = one BotFather token, one admin list, one channel optional):

```env
# Client 1 bot token (from @BotFather)
BOT_TOKEN=1234567890:ABCdefGHI...
# Client 1 admin Telegram user IDs (comma-separated)
ADMIN_IDS=111111111,222222222
# Optional: set in bot via Admin → Set Channel if you leave this empty
# CHANNEL_ID=-1001234567890

DATABASE_URL=postgresql://bot1user:StrongPasswordForBot1@localhost:5432/telegram_bot_client1
REDIS_URL=redis://localhost:6379/0

WEBHOOK_URL=https://ayanbot1.duckdns.org
WEBHOOK_PATH=webhook
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8080
```

Save (Ctrl+O, Enter, Ctrl+X).

---

### Step 3.5 Run migrations for Bot 1 (optional)

The bot creates tables on first start. To run migrations manually:

```bash
cd ~/telegram-bot-client1
source venv/bin/activate
psql -h localhost -U bot1user -d telegram_bot_client1 -f migrations/001_initial.sql
psql -h localhost -U bot1user -d telegram_bot_client1 -f migrations/002_welcome_config.sql
psql -h localhost -U bot1user -d telegram_bot_client1 -f migrations/003_channel_id.sql
psql -h localhost -U bot1user -d telegram_bot_client1 -f migrations/004_premium_messages.sql
```

(Use the same password as in `DATABASE_URL`; you may set `PGPASSWORD=...` to avoid prompts.)

---

### Step 3.6 Nginx site for Bot 1

```bash
sudo nano /etc/nginx/sites-available/telegram-bot-client1
```

Paste:

```nginx
server {
    listen 80;
    server_name ayanbot1.duckdns.org;

    location /webhook {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and test:

```bash
sudo ln -sf /etc/nginx/sites-available/telegram-bot-client1 /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl reload nginx
```

---

### Step 3.7 SSL for Bot 1 domain

```bash
sudo certbot --nginx -d ayanbot1.duckdns.org
```

Choose redirect HTTP → HTTPS when asked.

---

### Step 3.8 Systemd service for Bot 1

```bash
sudo nano /etc/systemd/system/telegram-bot-client1.service
```

Paste (if your user is not `adii` or project is not in `~/telegram-bot-client1`, change `User`, `WorkingDirectory`, and `ExecStart` accordingly):

```ini
[Unit]
Description=Telegram Bot Client 1 (Webhook)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=adii
Group=adii
WorkingDirectory=/home/adii/telegram-bot-client1
Environment="PATH=/home/adii/telegram-bot-client1/venv/bin"
ExecStart=/home/adii/telegram-bot-client1/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-client1
sudo systemctl start telegram-bot-client1
sudo systemctl status telegram-bot-client1
```

Logs: `sudo journalctl -u telegram-bot-client1 -f`

---

### Step 3.9 Verify Bot 1

1. **Webhook:**  
   `curl "https://api.telegram.org/bot<BOT1_TOKEN>/getWebhookInfo"`  
   Should show `"url":"https://ayanbot1.duckdns.org/webhook"`.

2. **Telegram:** Open Client 1’s bot → `/start` → Admin panel (if your ID is in `ADMIN_IDS`).

3. **Admin → Bot Configuration:** DB and Redis should show connected.

Bot 1 deployment is complete.

---

## 4. Deploy Bot 2 (Client 2)

Repeat the same structure for the **second** bot, with different names, ports, DBs, and domain.

### Step 4.1 Database and Redis for Bot 2

**PostgreSQL:**

```bash
sudo -u postgres psql
```

```sql
CREATE USER bot2user WITH PASSWORD 'StrongPasswordForBot2';
CREATE DATABASE telegram_bot_client2 OWNER bot2user;
\q
```

**Connection string:**  
`postgresql://bot2user:StrongPasswordForBot2@localhost:5432/telegram_bot_client2`

**Redis** for Bot 2: use DB index **1** so it doesn’t share with Bot 1.  
URL: `redis://localhost:6379/1`

---

### Step 4.2 Project directory for Bot 2

```bash
cd ~
git clone https://github.com/sixtyfourbitsquad/AYAN-BOT-.git telegram-bot-client2
cd telegram-bot-client2
```

(Or copy from `telegram-bot-client1` and replace `.env`.)

---

### Step 4.3 Venv and dependencies

```bash
cd ~/telegram-bot-client2
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4.4 `.env` for Bot 2

Use **Client 2’s** token, admin IDs, and a **different port** (e.g. 8081):

```env
BOT_TOKEN=9876543210:XYZ...
ADMIN_IDS=333333333,444444444
# CHANNEL_ID=... optional, or set in bot

DATABASE_URL=postgresql://bot2user:StrongPasswordForBot2@localhost:5432/telegram_bot_client2
REDIS_URL=redis://localhost:6379/1

WEBHOOK_URL=https://ayanbot2.duckdns.org
WEBHOOK_PATH=webhook
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8081
```

Important: **WEBHOOK_PORT=8081** (different from Bot 1’s 8080).

---

### Step 4.5 Migrations for Bot 2

```bash
cd ~/telegram-bot-client2
source venv/bin/activate
psql -h localhost -U bot2user -d telegram_bot_client2 -f migrations/001_initial.sql
psql -h localhost -U bot2user -d telegram_bot_client2 -f migrations/002_welcome_config.sql
psql -h localhost -U bot2user -d telegram_bot_client2 -f migrations/003_channel_id.sql
psql -h localhost -U bot2user -d telegram_bot_client2 -f migrations/004_premium_messages.sql
```

---

### Step 4.6 Nginx site for Bot 2

```bash
sudo nano /etc/nginx/sites-available/telegram-bot-client2
```

```nginx
server {
    listen 80;
    server_name ayanbot2.duckdns.org;

    location /webhook {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/telegram-bot-client2 /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl reload nginx
```

---

### Step 4.7 SSL for Bot 2

```bash
sudo certbot --nginx -d ayanbot2.duckdns.org
```

---

### Step 4.8 Systemd service for Bot 2

```bash
sudo nano /etc/systemd/system/telegram-bot-client2.service
```

```ini
[Unit]
Description=Telegram Bot Client 2 (Webhook)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=adii
Group=adii
WorkingDirectory=/home/adii/telegram-bot-client2
Environment="PATH=/home/adii/telegram-bot-client2/venv/bin"
ExecStart=/home/adii/telegram-bot-client2/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start and enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-client2
sudo systemctl start telegram-bot-client2
sudo systemctl status telegram-bot-client2
```

---

### Step 4.9 Verify Bot 2

- Webhook: `curl "https://api.telegram.org/bot<BOT2_TOKEN>/getWebhookInfo"` → `https://ayanbot2.duckdns.org/webhook`
- Telegram: Client 2’s bot → `/start` → Admin panel and Config.

Both bots are now running independently on the same VPS.

---

## 5. Daily operations and troubleshooting

### Quick reference (two bots)

| Action        | Bot 1 (Client 1)                    | Bot 2 (Client 2)                    |
|---------------|-------------------------------------|-------------------------------------|
| Project dir   | `~/telegram-bot-client1`            | `~/telegram-bot-client2`            |
| Config        | `~/telegram-bot-client1/.env`        | `~/telegram-bot-client2/.env`        |
| Service name  | `telegram-bot-client1`              | `telegram-bot-client2`              |
| Port          | 8080                                | 8081                                |
| Start         | `sudo systemctl start telegram-bot-client1`   | `sudo systemctl start telegram-bot-client2`   |
| Stop          | `sudo systemctl stop telegram-bot-client1`    | `sudo systemctl stop telegram-bot-client2`   |
| Restart       | `sudo systemctl restart telegram-bot-client1`  | `sudo systemctl restart telegram-bot-client2` |
| Logs          | `sudo journalctl -u telegram-bot-client1 -f`  | `sudo journalctl -u telegram-bot-client2 -f`  |
| App log file  | `~/telegram-bot-client1/bot.log`     | `~/telegram-bot-client2/bot.log`    |

### Updating one bot (e.g. Client 1)

```bash
cd ~/telegram-bot-client1
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegram-bot-client1
```

Run any new migrations (e.g. new `migrations/00X_*.sql`) against that bot’s database before or after restart.

### Updating both bots

Run these on your VPS (as user `adii` or whoever owns the project dirs). Each bot has its own folder and service.

**Bot 1 (Client 1):**
```bash
cd ~/telegram-bot-client1
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegram-bot-client1
```

**Bot 2 (Client 2):**
```bash
cd ~/telegram-bot-client2
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegram-bot-client2
```

If there are new migration files (e.g. `migrations/004_premium_messages.sql`), run them for each database before or after restart:

```bash
# Bot 1 DB (use Bot 1’s DB user and database from .env)
psql -h localhost -U bot1user -d telegram_bot_client1 -f migrations/004_premium_messages.sql

# Bot 2 DB
psql -h localhost -U bot2user -d telegram_bot_client2 -f migrations/004_premium_messages.sql
```

### Common issues

| Symptom | What to check |
|--------|----------------|
| **502 Bad Gateway** | Bot not listening on its port. `sudo systemctl status telegram-bot-client1` (or client2). Confirm `.env` has correct `WEBHOOK_PORT` (8080 vs 8081). |
| **Bot doesn’t reply** | `getWebhookInfo` URL correct; Nginx running; bot service running; `journalctl -u telegram-bot-client1 -n 100`. |
| **DB/Redis error** | PostgreSQL and Redis running. In `.env`, correct `DATABASE_URL` and `REDIS_URL` (and Redis DB index 0 vs 1). |
| **Admin panel not shown** | Put your Telegram user ID in that bot’s `ADMIN_IDS` in `.env`, then restart that bot’s service. |
| **Join requests not handled** | In bot: Admin → Set Channel (or set `CHANNEL_ID` in `.env`). In channel: add bot as admin with “Approve join requests” permission. |

---

## 6. Security and maintenance

- **Secrets:** Never commit `.env`. Keep `BOT_TOKEN`, DB passwords, and Redis URLs only on the server.
- **Updates:** Regularly `apt update && apt upgrade`, and renew SSL with `sudo certbot renew` (often automated).
- **Backups:** Back up PostgreSQL (e.g. `pg_dump`) and optionally Redis for each client.
- **Log rotation:** Optionally configure logrotate for `bot.log` in each project directory.
- **Two clients:** Each client’s data (users, welcome messages, channel, broadcast) is isolated by separate database and Redis DB index.

---

You now have two production-ready bots on one VPS, one per client, with separate configs, databases, and domains.
