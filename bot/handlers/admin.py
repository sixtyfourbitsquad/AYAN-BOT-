"""Admin panel callback handlers."""
import asyncio
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import config
from bot.database import (
    get_user_stats,
    get_welcome_count,
    get_welcome_messages_ordered,
    get_pool,
)
from bot.redis_client import get_redis, set_admin_state, get_admin_state, clear_admin_state
from bot.keyboards import (
    admin_main_keyboard,
    welcome_manage_keyboard,
    welcome_list_keyboard,
    welcome_type_keyboard,
    back_to_admin_keyboard,
)
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    user_id = update.effective_user.id if update.effective_user else 0
    if not _is_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return

    await query.answer()

    data = query.data
    if data == "admin:main":
        await query.edit_message_text(
            "👋 Admin panel. Choose an option:",
            reply_markup=admin_main_keyboard(),
        )
        await clear_admin_state(user_id)
        return

    if data == "admin:add_welcome":
        await set_admin_state(user_id, "add_welcome:choose_type")
        await query.edit_message_text(
            "Select the type of welcome message to add:",
            reply_markup=welcome_type_keyboard(),
        )
        return

    if data == "admin:manage_welcome":
        messages = await get_welcome_messages_ordered()
        if not messages:
            await query.edit_message_text(
                "No welcome messages yet. Add one from the main menu.",
                reply_markup=welcome_manage_keyboard(),
            )
            return
        await query.edit_message_text(
            "Manage welcome messages (click to preview, 🗑 to delete):",
            reply_markup=welcome_list_keyboard(messages),
        )
        return

    if data == "admin:preview_welcome":
        messages = await get_welcome_messages_ordered()
        if not messages:
            await query.edit_message_text(
                "No welcome messages to preview.",
                reply_markup=back_to_admin_keyboard(),
            )
            return
        await query.edit_message_text("Sending preview in order...")
        chat_id = query.message.chat_id if query.message else 0
        for m in messages:
            try:
                await send_welcome_message(context, chat_id, m)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.exception("Preview send error: %s", e)
                await context.bot.send_message(chat_id, f"⚠️ Failed to send item: {e}")
        await context.bot.send_message(
            chat_id,
            "✅ Preview done.",
            reply_markup=back_to_admin_keyboard(),
        )
        return

    if data == "admin:stats":
        stats = await get_user_stats()
        text = (
            f"📊 **User Stats**\n\n"
            f"Total users: {stats['total_users']}\n"
            f"Total join requests: {stats['total_join_requests']}\n"
            f"Join requests today: {stats['join_requests_today']}\n"
            f"Active users (7 days): {stats['active_users_7d']}"
        )
        await query.edit_message_text(
            text,
            reply_markup=back_to_admin_keyboard(),
            parse_mode="Markdown",
        )
        return

    if data == "admin:broadcast":
        await set_admin_state(user_id, "broadcast:wait_message")
        await query.edit_message_text(
            "📢 Send the message you want to broadcast (text or any media). "
            "It will be forwarded to all users. Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="broadcast:cancel")],
            ]),
        )
        return

    if data == "admin:config":
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "✅ Connected"
        except Exception as e:
            db_status = f"❌ {e!s}"
        try:
            r = get_redis()
            await r.ping()
            redis_status = "✅ Connected"
        except Exception as e:
            redis_status = f"❌ {e!s}"

        uptime = "N/A"
        if context.bot_data.get("start_time"):
            import time
            uptime = str(int(time.time() - context.bot_data["start_time"])) + "s"

        wc = await get_welcome_count()
        stats = await get_user_stats()
        text = (
            f"⚙ **Bot Configuration**\n\n"
            f"Uptime: {uptime}\n"
            f"Total users: {stats['total_users']}\n"
            f"Welcome messages: {wc}\n"
            f"Channel ID: `{config.CHANNEL_ID}`\n"
            f"Admin IDs: `{config.ADMIN_IDS}`\n\n"
            f"DB: {db_status}\n"
            f"Redis: {redis_status}"
        )
        await query.edit_message_text(
            text,
            reply_markup=back_to_admin_keyboard(),
            parse_mode="Markdown",
        )
        return

    if data == "admin:logs":
        await query.answer("Preparing logs...")
        log_path = Path(config.LOG_FILE)
        if not log_path.exists():
            await query.edit_message_text(
                "No log file found.",
                reply_markup=back_to_admin_keyboard(),
            )
            return
        lines = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        last_100 = "\n".join(lines[-100:]) if lines else "(empty)"
        if len(last_100) > 4000:
            last_100 = last_100[-4000:]
        await query.edit_message_text(
            f"📜 Last 100 lines:\n\n```\n{last_100}\n```",
            reply_markup=back_to_admin_keyboard(),
        )
        try:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=open(log_path, "rb"),
                filename="bot.log",
                caption="Full log file",
            )
        except Exception as e:
            logger.exception("Send log file: %s", e)
        return


async def send_welcome_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, m: dict) -> None:
    """Send one welcome message by type."""
    t = m.get("type", "text")
    file_id = m.get("file_id")
    text = m.get("text") or ""
    caption = m.get("caption") or ""
    bot = context.bot
    if t == "text":
        await bot.send_message(chat_id, text or "(empty text)")
    elif t == "photo":
        await bot.send_photo(chat_id, file_id, caption=caption or None)
    elif t == "video":
        await bot.send_video(chat_id, file_id, caption=caption or None)
    elif t == "animation":
        await bot.send_animation(chat_id, file_id, caption=caption or None)
    elif t == "document":
        await bot.send_document(chat_id, file_id, caption=caption or None)
    elif t == "audio":
        await bot.send_audio(chat_id, file_id, caption=caption or None)
    elif t == "voice":
        await bot.send_voice(chat_id, file_id, caption=caption or None)
    else:
        await bot.send_message(chat_id, text or "(unknown type)")


def register_admin(app) -> None:
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:"))
