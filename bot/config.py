"""Load and validate configuration from environment."""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None or value == "":
        raise ValueError(f"Missing required env: {key}")
    return value.strip()


def _get_admin_ids() -> List[int]:
    raw = os.getenv("ADMIN_IDS", "")
    if not raw:
        raise ValueError("ADMIN_IDS is required (comma-separated integers)")
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                raise ValueError(f"Invalid ADMIN_IDS value: {part}")
    return ids


# Required
BOT_TOKEN: str = _get_env("BOT_TOKEN")
ADMIN_IDS: List[int] = _get_admin_ids()
CHANNEL_ID: int = int(_get_env("CHANNEL_ID"))
DATABASE_URL: str = _get_env("DATABASE_URL")
REDIS_URL: str = _get_env("REDIS_URL")
WEBHOOK_URL: str = _get_env("WEBHOOK_URL").rstrip("/")

# Optional
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "webhook").strip()
WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip()
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))

# Broadcast rate limit (messages per second)
BROADCAST_RATE_LIMIT: int = 25

# Log file
LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")
