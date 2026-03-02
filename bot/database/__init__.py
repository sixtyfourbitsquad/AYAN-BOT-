"""Database package: pool and table access."""
from bot.database.pool import get_pool, init_pool, close_pool
from bot.database.queries import (
    ensure_tables,
    get_user,
    upsert_user,
    increment_join_requests,
    get_welcome_config,
    set_welcome_video,
    set_welcome_apk,
    DEFAULT_WELCOME_TEXT,
    get_user_stats,
    log_broadcast,
)

__all__ = [
    "get_pool",
    "init_pool",
    "close_pool",
    "ensure_tables",
    "get_user",
    "upsert_user",
    "increment_join_requests",
    "get_welcome_config",
    "set_welcome_video",
    "set_welcome_apk",
    "DEFAULT_WELCOME_TEXT",
    "get_user_stats",
    "log_broadcast",
]
