# Complete VPS Guide: New Server to Bot Deployment

End-to-end steps from a **brand new VPS** to **deployed Telegram bot**. All app and service steps use the OS user **adii**.

---

## Part A: Get and Access the VPS

### Step 1: Create a new VPS

1. Sign up / log in to a provider, e.g.:
   - [DigitalOcean](https://www.digitalocean.com/) → Create Droplet  
   - [Hetzner](https://www.hetzner.com/cloud) → Create Server  
   - [Vultr](https://www.vultr.com/) or [Linode](https://www.linode.com/)

2. When creating the server, set:
   - **Image / OS**: Ubuntu 22.04 LTS  
   - **Plan**: 4 vCPU, 8 GB RAM (or 2 vCPU / 4 GB for testing)  
   - **Region**: Choose one close to you or your users  
   - **Authentication**: Add your **SSH public key** (recommended) or use password  

3. Click **Create** and wait until the server is running.

4. **Write down**:
   - **Server IP** (e.g. `164.92.xxx.xxx`)  
   - Login: **root** (and password if you didn’t use SSH key)

---

### Step 2: Connect to the VPS (first time)

On your **local computer** (PowerShell, CMD, or terminal):

```bash
ssh root@YOUR_SERVER_IP
```

If you use an SSH key in a custom path:

```bash
ssh -i C:\Users\YourName\.ssh\id_ed25519 root@YOUR_SERVER_IP
```

- Replace `YOUR_SERVER_IP` with the IP from Step 1.  
- If asked “Are you sure you want to continue connecting?”, type **yes** and press Enter.  
- If you set a root password, enter it when prompted.

You should see a prompt like: `root@ubuntu-s-4vcpu-8gb:~#`

---

### Step 3: Update the server

Still as **root**, run:

```bash
apt update && apt upgrade -y
```

Wait until it finishes. This can take a few minutes.

---

### Step 4: Create the user **adii**

Run these commands **one by one** as root:

```bash
adduser adii
```

- Enter a **password** for adii (and confirm).  
- Full name and room number can be left empty (press Enter).

Then give adii sudo access:

```bash
usermod -aG sudo adii
```

Verify the user exists:

```bash
id adii
```

You should see something like: `uid=1000(adii) gid=1000(adii) groups=1000(adii),27(sudo)`.

---

### Step 5: Allow adii to log in with SSH (optional but recommended)

On your **local computer** (new terminal), copy your SSH key to adii:

```bash
ssh-copy-id adii@YOUR_SERVER_IP
```

Enter adii’s password once. After this you can log in as adii without a password.

**Optional (more secure):** disable root password login. As **root** on the server:

```bash
sed -i 's/^#?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### Step 6: Switch to user adii and stay as adii

As root, run:

```bash
su - adii
```

The prompt should change to something like: `adii@ubuntu-s-4vcpu-8gb:~$`.

From here on, **all commands are run as adii** unless the step says “as root”. If you see `sudo`, that’s still you (adii) running a command with elevated rights.

---

### Step 7: Configure the firewall

As **adii**:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

When asked “Proceed with operation?”, type **y** and Enter.

Check status:

```bash
sudo ufw status
```

You should see 22, 80, 443 allowed.

---

## Part B: Install Software on the VPS

### Step 8: Install Python, Git, Nginx, PostgreSQL, Redis, Certbot

As **adii**, run:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx postgresql redis-server
```

- On **Ubuntu 22.04** this gives Python 3.10; on **Ubuntu 24.04 (Noble)** it gives Python 3.12. Both work with the bot.  
- Confirm with **y** if asked. Wait until everything is installed.

Check Python:

```bash
python3 --version
```

You should see e.g. `Python 3.10.x` or `Python 3.12.x`.

---

### Step 9: Configure PostgreSQL (database for the bot)

**9.1** Switch to the system postgres user and open the database shell:

```bash
sudo -u postgres psql
```

You should see a prompt like: `postgres=#`.

**9.2** In the `psql` prompt, run these lines **one by one** (choose a strong password and replace `YourStrongPassword123`):

```sql
CREATE USER adii WITH PASSWORD 'YourStrongPassword123';
```

```sql
CREATE DATABASE telegram_bot OWNER adii;
```

```sql
\q
```

**9.3** Test that adii can connect (use the same password when asked):

```bash
psql -h localhost -U adii -d telegram_bot -c "SELECT 1;"
```

You should see a row with `1`. If it works, your connection string is:

```text
postgresql://adii:YourStrongPassword123@localhost:5432/telegram_bot
```

Keep this for the `.env` file later.

---

### Step 10: Configure Redis

As **adii**:

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

Test:

```bash
redis-cli ping
```

Expected output: **PONG**.  
Redis URL to use later: `redis://localhost:6379/0`.

---

## Part C: Domain and Webhook URL

### Step 11: Get a domain (or subdomain) and point it to the VPS

1. Use a domain you own (e.g. `yourdomain.com`) or buy one.  
2. In your domain’s DNS panel, add an **A** record:
   - **Name**: `bot` (so the hostname is `bot.yourdomain.com`) or leave blank for root domain.  
   - **Type**: **A**  
   - **Value**: **YOUR_SERVER_IP**  
   - **TTL**: 300 or 3600  

3. Save the DNS changes and wait 5–30 minutes (up to a few hours).  
4. From your **local** machine or the VPS, test:

```bash
ping bot.yourdomain.com
```

It should show your VPS IP. Then your webhook URL will be: **https://bot.yourdomain.com** (we’ll add `/webhook` in the app config).

---

## Part D: Deploy the Bot Code

### Step 12: Put the bot project on the VPS

**Option A – Using Git (if your project is in a repo):**

As **adii**:

```bash
cd ~
git clone https://github.com/sixtyfourbitsquad/AYAN-BOT-.git telegram-bot
cd telegram-bot
```

Replace the URL with your real repo. If the repo is private, use a personal access token or deploy key.

**Option B – Upload from your computer (no Git):**

On your **local** machine, from the folder that contains the `bot` folder and `requirements.txt`:

```bash
scp -r "c:\Work\RAM NEW BOT TG 02 March\*" adii@YOUR_SERVER_IP:~/telegram-bot/
```

Then on the VPS as **adii**:

```bash
cd ~/telegram-bot
ls
```

You should see `bot`, `requirements.txt`, `.env.example`, `migrations`, etc.

---

### Step 13: Create Python virtualenv and install dependencies

As **adii**, in the project directory:

```bash
cd ~/telegram-bot
python3 -m venv venv
source venv/bin/activate
```

The prompt should start with `(venv)`. Then:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Wait until all packages are installed. You can leave the venv activated for the next steps, or run `source venv/bin/activate` again when you come back to this directory.

---

### Step 14: Create the `.env` file

As **adii**:

```bash
cd ~/telegram-bot
cp .env.example .env
nano .env
```

In nano, fill in **your** values (replace placeholders):

```env
BOT_TOKEN=1234567890:ABCdefGHI...
ADMIN_IDS=123456789,987654321
CHANNEL_ID=-1001234567890
DATABASE_URL=postgresql://adii:YourStrongPassword123@localhost:5432/telegram_bot
REDIS_URL=redis://localhost:6379/0
WEBHOOK_URL=https://bot.yourdomain.com
WEBHOOK_PATH=webhook
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8080
```

- **BOT_TOKEN**: From [@BotFather](https://t.me/BotFather) in Telegram.  
- **ADMIN_IDS**: Your Telegram user ID (and others, comma-separated, no spaces).  
- **CHANNEL_ID**: Your channel ID (e.g. from [@userinfobot](https://t.me/userinfobot) or similar).  
- **DATABASE_URL**: Same as in Step 9 (user **adii**, password, database **telegram_bot**).  
- **REDIS_URL**: As in Step 10.  
- **WEBHOOK_URL**: Your domain with `https://` (no trailing slash).  
- **WEBHOOK_PATH**: Keep `webhook` unless you change it in code.  
- **WEBHOOK_HOST**: `127.0.0.1` so only Nginx can reach the bot.  
- **WEBHOOK_PORT**: `8080` (must match Nginx config later).

Save and exit: **Ctrl+O**, Enter, then **Ctrl+X**.

---

### Step 15: Run database migrations (optional)

The bot can create tables on first start. To create them manually now, as **adii**:

```bash
cd ~/telegram-bot
source venv/bin/activate
PGPASSWORD=YourStrongPassword123 psql -h localhost -U adii -d telegram_bot -f migrations/001_initial.sql
```

Use the same password as in `.env`. If the file path or name is different, adjust the command.

---

## Part E: Nginx and HTTPS (Webhook)

### Step 16: Create Nginx site config

As **adii**:

```bash
sudo nano /etc/nginx/sites-available/telegram-bot
```

Paste this (replace `bot.yourdomain.com` with your real domain):

```nginx
server {
    listen 80;
    server_name bot.yourdomain.com;

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

Save and exit: **Ctrl+O**, Enter, **Ctrl+X**.

---

### Step 17: Enable the site and test Nginx

```bash
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled
sudo nginx -t
```

You should see “syntax is ok” and “test is successful”. Then:

```bash
sudo systemctl reload nginx
```

---

### Step 18: Get SSL certificate (HTTPS)

```bash
sudo certbot --nginx -d bot.yourdomain.com
```

- Enter your email when asked.  
- Agree to terms (Y).  
- Choose whether to share email with EFF (optional).  
- When asked to redirect HTTP to HTTPS, choose **2** (Redirect).

After it finishes, `https://bot.yourdomain.com` should load (often “Not Found” in browser is OK; Telegram will use `https://bot.yourdomain.com/webhook`).

---

## Part F: Run the Bot as a Service

### Step 19: Create the systemd service file

As **adii**:

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Paste this (paths assume user **adii** and project in `/home/adii/telegram-bot`):

```ini
[Unit]
Description=Telegram Bot (Webhook)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=adii
Group=adii
WorkingDirectory=/home/adii/telegram-bot
Environment="PATH=/home/adii/telegram-bot/venv/bin"
ExecStart=/home/adii/telegram-bot/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save and exit: **Ctrl+O**, Enter, **Ctrl+X**.

---

### Step 20: Enable and start the bot

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

You should see **active (running)** in green. To follow logs:

```bash
sudo journalctl -u telegram-bot -f
```

You should see a line like “Bot initialized; pool, redis, broadcast worker started.” Press **Ctrl+C** to stop following logs.

---

### Step 21: Confirm webhook in Telegram

The bot sets the webhook on start. To check (replace `YOUR_BOT_TOKEN` with the real token):

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

In the JSON output you should see `"url":"https://bot.yourdomain.com/webhook"`.

---

## Part G: Verify the Bot

1. Open your bot in Telegram and send **/start**.  
2. If your user ID is in **ADMIN_IDS**, you should see the admin panel with buttons.  
3. In the bot: **⚙ Bot Configuration** → DB and Redis should show as connected.  
4. Add a welcome message and use **🔍 Preview Welcome Messages**.  
5. In your channel, turn on “Join request” and add the bot as admin; test a join request and confirm the bot sends the welcome messages.

---

## Quick reference (user: adii)

| What            | Command / path |
|-----------------|----------------|
| Login as adii   | `ssh adii@YOUR_SERVER_IP` |
| Project folder  | `/home/adii/telegram-bot` |
| Activate venv   | `cd ~/telegram-bot && source venv/bin/activate` |
| Config          | `/home/adii/telegram-bot/.env` |
| Start bot       | `sudo systemctl start telegram-bot` |
| Stop bot        | `sudo systemctl stop telegram-bot` |
| Restart bot     | `sudo systemctl restart telegram-bot` |
| Bot logs        | `sudo journalctl -u telegram-bot -f` |
| App log file    | `/home/adii/telegram-bot/bot.log` |
| Webhook URL     | `https://bot.yourdomain.com/webhook` |

---

## Troubleshooting

- **502 Bad Gateway**: Bot not listening on 8080. Check `sudo systemctl status telegram-bot` and that `.env` has `WEBHOOK_HOST=127.0.0.1` and `WEBHOOK_PORT=8080`.  
- **Bot doesn’t reply**: Check `getWebhookInfo` (Step 21), Nginx is running (`sudo systemctl status nginx`), and bot logs (`sudo journalctl -u telegram-bot -n 50`).  
- **Database/Redis error**: Ensure PostgreSQL and Redis are running (`sudo systemctl status postgresql redis-server`) and that `DATABASE_URL` and `REDIS_URL` in `.env` match (user **adii** for DB).  
- **Admin panel not shown**: Put your Telegram user ID in `ADMIN_IDS` in `.env`, then restart: `sudo systemctl restart telegram-bot`.

---

You now have a full path from a **new VPS** to a **running bot** with user **adii** and webhook deployment.
