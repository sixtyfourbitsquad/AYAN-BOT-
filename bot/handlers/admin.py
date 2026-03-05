"""Admin panel callback handlers."""
import asyncio
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import config
from bot.database import (
    get_user_stats,
    get_welcome_config,
    get_extra_messages,
    delete_extra_message,
    get_pool,
    DEFAULT_WELCOME_TEXT,
)
from bot.redis_client import get_redis, set_admin_state, get_admin_state, clear_admin_state
from bot.keyboards import admin_main_keyboard, back_to_admin_keyboard
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

    if data == "admin:set_video":
        await set_admin_state(user_id, "welcome:set_video")
        await query.edit_message_text(
            "📹 Send the welcome video now. You can add a caption to the video.",
            reply_markup=back_to_admin_keyboard(),
        )
        return

    if data == "admin:set_apk":
        await set_admin_state(user_id, "welcome:set_apk")
        await query.edit_message_text(
            "📦 Send the APK file now. You can add a caption.",
            reply_markup=back_to_admin_keyboard(),
        )
        return

    if data == "admin:add_extra":
        await set_admin_state(user_id, "extra:add")
        await query.edit_message_text(
            "➕ Send the extra welcome message now (text, photo, video, GIF, document, audio, or voice).\nSend /cancel to abort.",
            reply_markup=back_to_admin_keyboard(),
        )
        return

    if data == "admin:manage_extra":
        extras = await get_extra_messages()
        if not extras:
            await query.edit_message_text(
                "No extra welcome messages yet.",
                reply_markup=back_to_admin_keyboard(),
            )
            return
        await query.edit_message_text(
            "Extra welcome messages (tap 🗑 to delete):",
            reply_markup=extra_list_keyboard(extras),
        )
        return

    if data == "admin:preview_welcome":
        await query.edit_message_text("Sending preview...")
        chat_id = query.message.chat_id if query.message else 0
        try:
            await send_full_welcome(context, chat_id, name="Admin")
            await context.bot.send_message(
                chat_id,
                "✅ Preview done.",
                reply_markup=back_to_admin_keyboard(),
            )
        except Exception as e:
            logger.exception("Preview error: %s", e)
            await context.bot.send_message(
                chat_id,
                f"⚠️ Error: {e}",
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

        cfg = await get_welcome_config()
        video_set = "✅" if cfg.get("video_file_id") else "❌"
        apk_set = "✅" if cfg.get("apk_file_id") else "❌"
        stats = await get_user_stats()
        text = (
            f"⚙ **Bot Configuration**\n\n"
            f"Uptime: {uptime}\n"
            f"Total users: {stats['total_users']}\n"
            f"Welcome video: {video_set} | APK: {apk_set}\n"
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


def extra_list_keyboard(messages: list) -> InlineKeyboardMarkup:
    """Build keyboard to manage extra messages (delete only)."""
    rows = []
    for idx, m in enumerate(messages, start=1):
        label = f"#{idx} {m.get('type', 'text')}"
        rows.append(
            [
                InlineKeyboardButton(label, callback_data="noop"),
                InlineKeyboardButton("🗑", callback_data=f"extra:del:{m['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="admin:main")])
    return InlineKeyboardMarkup(rows)


async def send_welcome_flow(context: ContextTypes.DEFAULT_TYPE, chat_id: int, name: str) -> None:
    """Send default welcome: text (with name) + video (if set) + APK (if set)."""
    from bot.database import get_welcome_config, DEFAULT_WELCOME_TEXT
    bot = context.bot
    text = DEFAULT_WELCOME_TEXT.replace("{name}", name or "User")
    await bot.send_message(chat_id, text)
    cfg = await get_welcome_config()
    if cfg.get("video_file_id"):
        await asyncio.sleep(0.25)
        await bot.send_video(
            chat_id,
            cfg["video_file_id"],
            caption=cfg.get("video_caption") or None,
        )
    if cfg.get("apk_file_id"):
        await asyncio.sleep(0.25)
        await bot.send_document(
            chat_id,
            cfg["apk_file_id"],
            caption=cfg.get("apk_caption") or None,
        )


async def send_extra_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Send all extra welcome messages in order."""
    from bot.database import get_extra_messages

    bot = context.bot
    extras = await get_extra_messages()
    for m in extras:
        t = m.get("type", "text")
        file_id = m.get("file_id")
        text = m.get("text") or ""
        caption = m.get("caption") or ""
        try:
            if t == "text":
                await bot.send_message(chat_id, text or "(empty)")
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
        except Exception as e:
            logger.exception("send_extra_messages error: %s", e)
        await asyncio.sleep(0.25)


async def send_full_welcome(context: ContextTypes.DEFAULT_TYPE, chat_id: int, name: str) -> None:
    """Default text+video+APK plus extra messages."""
    await send_welcome_flow(context, chat_id, name=name)
    await send_extra_messages(context, chat_id)


async def handle_extra_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle extra:del:* callback buttons."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("extra:"):
        return
    user_id = update.effective_user.id if update.effective_user else 0
    if not _is_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return
    data = query.data
    if data.startswith("extra:del:"):
        try:
            msg_id = int(data.split(":")[-1])
        except ValueError:
            await query.answer("Invalid id.", show_alert=True)
            return
        ok = await delete_extra_message(msg_id)
        await query.answer("Deleted." if ok else "Not found.", show_alert=not ok)
        extras = await get_extra_messages()
        if not extras:
            await query.edit_message_text(
                "No extra welcome messages left.",
                reply_markup=back_to_admin_keyboard(),
            )
        else:
            await query.edit_message_text(
                "Extra welcome messages (tap 🗑 to delete):",
                reply_markup=extra_list_keyboard(extras),
            )


def register_admin(app) -> None:
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(handle_extra_callbacks, pattern="^extra:"))
