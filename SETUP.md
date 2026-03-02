# Telegram Bot – Setup Instructions

Production-grade Telegram bot with admin panel, welcome messages, broadcast, and webhook deployment.

## Requirements

- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- Public HTTPS URL for webhook (e.g. Nginx + SSL in front of the app)

## 1. Clone / project layout

Ensure you have this structure:

```
bot/
  main.py
  config.py
  redis_client.py
  database/
  handlers/
  keyboards/
  utils/
migrations/
  001_initial.sql
requirements.txt
.env.example
```

## 2. Virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Environment configuration

Copy the example env and fill in values:

```bash
cp .env.example .env
```

Edit `.env`:

| Variable       | Description |
|----------------|-------------|
| `BOT_TOKEN`    | From [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS`    | Comma-separated Telegram user IDs (e.g. `123456789,987654321`) |
| `CHANNEL_ID`   | Channel ID where join requests are handled (e.g. `-1001234567890`) |
| `DATABASE_URL` | PostgreSQL URL, e.g. `postgresql://user:password@localhost:5432/telegram_bot` |
| `REDIS_URL`    | Redis URL, e.g. `redis://localhost:6379/0` |
| `WEBHOOK_URL`  | Public HTTPS base URL (e.g. `https://yourdomain.com`) |
| `WEBHOOK_PATH` | Optional; default `webhook` → full URL `https://yourdomain.com/webhook` |
| `WEBHOOK_HOST` | Optional; default `0.0.0.0` |
| `WEBHOOK_PORT` | Optional; default `8080` |

## 5. Database migration

Create the database and run the initial migration:

```bash
psql -U your_user -d telegram_bot -f migrations/001_initial.sql
```

Or run the SQL manually. The bot also runs `ensure_tables()` on startup (creates tables if not exist).

## 6. Redis

Ensure Redis is running and reachable at `REDIS_URL` (e.g. `redis://localhost:6379/0`).

## 7. Webhook deployment

The bot uses **webhooks** (no polling). You need:

1. A public HTTPS URL (e.g. `https://yourdomain.com`).
2. A reverse proxy (e.g. Nginx) that forwards `POST /webhook` to the app.

### Nginx example

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

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

Then set in `.env`:

- `WEBHOOK_URL=https://yourdomain.com`
- `WEBHOOK_PATH=webhook`
- `WEBHOOK_PORT=8080` (app listens here; Nginx proxies to it)

## 8. Run the bot

From the project root (parent of `bot/`):

```bash
python -m bot.main
```

Or:

```bash
cd bot && python main.py
```

If you run from the repo root and `bot` is a package:

```bash
python -m bot.main
```

Make sure the working directory is the repo root so that `bot.config` and `bot.database` can be imported and `.env` is found (dotenv loads from current directory).

For production, use a process manager:

- **systemd** (Linux): create a unit that runs `python -m bot.main` with `WorkingDirectory=/path/to/repo`.
- **Docker**: run the same command in the container; expose `WEBHOOK_PORT` and point Nginx to it.

## 9. Verify

1. Open the bot in Telegram and send `/start`.
2. If your user ID is in `ADMIN_IDS`, you should see the admin panel (inline buttons).
3. Add a welcome message (e.g. text or photo), then use “Preview Welcome Messages”.
4. In the channel, enable “Join request” and set the bot as admin that can approve join requests. When someone requests to join, the bot sends the welcome messages and does **not** approve the request (per requirements).

## 10. Logs

- Log file: `bot.log` (or path set in `LOG_FILE`).
- Admin → “View Logs” shows the last 100 lines and sends the full log as a document.

## Performance (4 CPU, 8 GB RAM VPS)

- asyncpg connection pool (min 2, max 10).
- Async Redis client.
- uvloop on Linux for faster event loop.
- Webhook (no polling).
- Broadcast: Redis queue + background worker, 25 messages/sec, RetryAfter handling, skipped blocked users.
- All I/O is async; no blocking in the main loop.

## Database migration SQL (reference)

See `migrations/001_initial.sql` for the full schema:

- `welcome_messages` – type, file_id, text, caption, position, created_at
- `users` – user_id, first_seen, last_seen, total_join_requests
- `broadcast_history` – id, type, content, sent_at, success_count, failed_count

Indexes are included for `position`, `last_seen`, and `sent_at`.
