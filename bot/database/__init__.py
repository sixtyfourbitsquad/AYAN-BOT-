"""Database package: pool and table access."""
from bot.database.pool import get_pool, init_pool, close_pool
from bot.database.queries import (
    ensure_tables,
    get_user,
    upsert_user,
    increment_join_requests,
    get_welcome_messages_ordered,
    add_welcome_message,
    delete_welcome_message,
    reorder_welcome_message,
    get_welcome_message_by_id,
    get_welcome_count,
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
    "get_welcome_messages_ordered",
    "add_welcome_message",
    "delete_welcome_message",
    "reorder_welcome_message",
    "move_welcome_message_up",
    "move_welcome_message_down",
    "get_welcome_message_by_id",
    "get_welcome_count",
    "get_user_stats",
    "log_broadcast",
]
