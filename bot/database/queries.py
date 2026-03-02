"""All database queries. Uses get_pool() for asyncpg."""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from bot.database.pool import get_pool

# --- Tables (run migration) ---
INIT_SQL = """
CREATE TABLE IF NOT EXISTS welcome_messages (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    file_id VARCHAR(255),
    text TEXT,
    caption TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_welcome_messages_position ON welcome_messages(position);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_join_requests INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);

CREATE TABLE IF NOT EXISTS broadcast_history (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    content TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_broadcast_history_sent_at ON broadcast_history(sent_at);
"""


async def ensure_tables() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(INIT_SQL)


# --- Users ---
async def get_user(user_id: int) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, first_seen, last_seen, total_join_requests FROM users WHERE user_id = $1",
            user_id,
        )
        if row is None:
            return None
        return dict(row)


async def upsert_user(user_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen, total_join_requests)
            VALUES ($1, NOW(), NOW(), 0)
            ON CONFLICT (user_id) DO UPDATE SET last_seen = NOW()
            """,
            user_id,
        )


async def increment_join_requests(user_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, first_seen, last_seen, total_join_requests)
            VALUES ($1, NOW(), NOW(), 1)
            ON CONFLICT (user_id) DO UPDATE SET
                last_seen = NOW(),
                total_join_requests = users.total_join_requests + 1
            """,
            user_id,
        )


async def get_user_stats() -> dict:
    """Returns total_users, total_join_requests, join_requests_today, active_7d."""
    pool = get_pool()
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_join = await conn.fetchval("SELECT COALESCE(SUM(total_join_requests), 0) FROM users")
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        join_today = await conn.fetchval(
            """
            SELECT COUNT(*) FROM users
            WHERE last_seen >= $1 AND total_join_requests > 0
            """,
            today_start,
        )
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_7d = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE last_seen >= $1",
            week_ago,
        )
    return {
        "total_users": total_users or 0,
        "total_join_requests": total_join or 0,
        "join_requests_today": join_today or 0,
        "active_users_7d": active_7d or 0,
    }


# --- Welcome messages ---
async def get_welcome_messages_ordered() -> List[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, type, file_id, text, caption, position, created_at FROM welcome_messages ORDER BY position, id"
        )
        return [dict(r) for r in rows]


async def get_welcome_message_by_id(msg_id: int) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, type, file_id, text, caption, position FROM welcome_messages WHERE id = $1",
            msg_id,
        )
        return dict(row) if row else None


async def get_welcome_count() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM welcome_messages") or 0


async def add_welcome_message(
    msg_type: str,
    file_id: Optional[str],
    text: Optional[str],
    caption: Optional[str],
) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        max_pos = await conn.fetchval("SELECT COALESCE(MAX(position), -1) FROM welcome_messages")
        new_pos = (max_pos or -1) + 1
        return await conn.fetchval(
            """
            INSERT INTO welcome_messages (type, file_id, text, caption, position)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            msg_type,
            file_id,
            text or "",
            caption or "",
            new_pos,
        )


async def delete_welcome_message(msg_id: int) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM welcome_messages WHERE id = $1", msg_id)
        return result == "DELETE 1"


async def reorder_welcome_message(msg_id: int, new_position: int) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE welcome_messages SET position = $1 WHERE id = $2", new_position, msg_id)
        return True


async def move_welcome_message_up(msg_id: int) -> bool:
    """Swap position with the message above. Returns True if moved."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, position FROM welcome_messages WHERE id = $1", msg_id)
        if not row:
            return False
        pos = row["position"]
        other = await conn.fetchrow("SELECT id, position FROM welcome_messages WHERE position < $1 ORDER BY position DESC LIMIT 1", pos)
        if not other:
            return False
        await conn.execute("UPDATE welcome_messages SET position = $1 WHERE id = $2", other["position"], msg_id)
        await conn.execute("UPDATE welcome_messages SET position = $1 WHERE id = $2", pos, other["id"])
        return True


async def move_welcome_message_down(msg_id: int) -> bool:
    """Swap position with the message below. Returns True if moved."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, position FROM welcome_messages WHERE id = $1", msg_id)
        if not row:
            return False
        pos = row["position"]
        other = await conn.fetchrow("SELECT id, position FROM welcome_messages WHERE position > $1 ORDER BY position ASC LIMIT 1", pos)
        if not other:
            return False
        await conn.execute("UPDATE welcome_messages SET position = $1 WHERE id = $2", other["position"], msg_id)
        await conn.execute("UPDATE welcome_messages SET position = $1 WHERE id = $2", pos, other["id"])
        return True


# --- Broadcast history ---
async def log_broadcast(msg_type: str, content: str, success_count: int, failed_count: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO broadcast_history (type, content, success_count, failed_count)
            VALUES ($1, $2, $3, $4)
            """,
            msg_type,
            content[:5000] if content else "",
            success_count,
            failed_count,
        )
