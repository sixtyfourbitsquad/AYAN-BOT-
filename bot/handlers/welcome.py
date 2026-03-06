"""Capture admin's welcome, premium, and channel setting (states: welcome:add, premium:add, channel:wait)."""
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.database import set_channel_id, add_welcome_message, add_premium_message
from bot.redis_client import get_admin_state, clear_admin_state
from bot.keyboards import admin_main_keyboard, back_to_admin_keyboard
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_message_content(msg) -> tuple:
    """Return (msg_type, file_id, text, caption) or (None, None, None, None) if invalid."""
    msg_type = "text"
    file_id = None
    text = None
    caption = None
    if msg.text and not (msg.photo or msg.video or msg.animation or msg.document or msg.audio or msg.voice):
        msg_type = "text"
        text = msg.text
        return (msg_type, file_id, text, caption)
    if msg.photo:
        msg_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        msg_type = "video"
        file_id = msg.video.file_id
    elif msg.animation:
        msg_type = "animation"
        file_id = msg.animation.file_id
    elif msg.document:
        msg_type = "document"
        file_id = msg.document.file_id
    elif msg.audio:
        msg_type = "audio"
        file_id = msg.audio.file_id
    elif msg.voice:
        msg_type = "voice"
        file_id = msg.voice.file_id
    else:
        return (None, None, None, None)
    caption = (msg.caption or "").strip()
    return (msg_type, file_id, text, caption)


async def capture_message_for_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When admin is in welcome:add, premium:add, or channel:wait, store the message or channel."""
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id not in config.ADMIN_IDS:
        return

    state = await get_admin_state(user_id)
    if not state:
        return
    if update.message and update.message.text:
        raw = update.message.text.strip().lower()
        if raw == "/cancel":
            await clear_admin_state(user_id)
            await update.message.reply_text("Cancelled.", reply_markup=admin_main_keyboard())
            return
        if raw == "/done":
            if state == "welcome:add":
                await clear_admin_state(user_id)
                await update.message.reply_text("Done adding welcome messages.", reply_markup=admin_main_keyboard())
            elif state == "premium:add":
                await clear_admin_state(user_id)
                await update.message.reply_text("Done adding premium messages.", reply_markup=admin_main_keyboard())
            else:
                return
            return
    if state == "channel:wait":
        msg = update.message
        if not msg:
            return
        channel_id = None
        # Forwarded channel message support across PTB versions:
        # - Older: Message.forward_from_chat
        # - Newer: Message.forward_origin.{chat|sender_chat}
        fwd_chat = getattr(msg, "forward_from_chat", None)
        if fwd_chat and getattr(fwd_chat, "type", None) == "channel":
            channel_id = getattr(fwd_chat, "id", None)
        if channel_id is None:
            origin = getattr(msg, "forward_origin", None)
            if origin:
                origin_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
                if origin_chat and getattr(origin_chat, "type", None) == "channel":
                    channel_id = getattr(origin_chat, "id", None)
        if channel_id is None and msg.text:
            text = msg.text.strip()
            try:
                channel_id = int(text)
            except ValueError:
                pass
        if channel_id is None:
            await msg.reply_text(
                "Send a forwarded message from your channel, or the channel ID (e.g. -1001234567890). /cancel to abort.",
                reply_markup=back_to_admin_keyboard(),
            )
            return
        try:
            await set_channel_id(channel_id)
            await clear_admin_state(user_id)
            await msg.reply_text(
                f"✅ Channel set to `{channel_id}`. Join requests from this channel will be handled.",
                reply_markup=admin_main_keyboard(),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.exception("set_channel_id: %s", e)
            await msg.reply_text(f"Error: {e}", reply_markup=back_to_admin_keyboard())
        return

    if state == "welcome:add":
        msg = update.message
        if not msg:
            return
        msg_type, file_id, text, caption = _parse_message_content(msg)
        if msg_type is None:
            await msg.reply_text("Send text or one media message (photo, video, GIF, document, audio, voice), or /cancel to abort.", reply_markup=back_to_admin_keyboard())
            return
        try:
            await add_welcome_message(msg_type, file_id, text or "", caption)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            done_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Done adding", callback_data="welcome:done")],
                [InlineKeyboardButton("◀️ Back to Admin", callback_data="admin:main")],
            ])
            await msg.reply_text(
                f"✅ Added ({msg_type}). Send another message to add more, or /done when finished.",
                reply_markup=done_kb,
            )
        except Exception as e:
            logger.exception("add_welcome_message: %s", e)
            await msg.reply_text(f"Error: {e}")
        return

    if state == "premium:add":
        msg = update.message
        if not msg:
            return
        msg_type, file_id, text, caption = _parse_message_content(msg)
        if msg_type is None:
            await msg.reply_text("Send text or one media message (photo, video, GIF, document, audio, voice), or /cancel to abort.", reply_markup=back_to_admin_keyboard())
            return
        try:
            await add_premium_message(msg_type, file_id, text or "", caption)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            done_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Done adding", callback_data="premium:done")],
                [InlineKeyboardButton("◀️ Back to Admin", callback_data="admin:main")],
            ])
            await msg.reply_text(
                f"✅ Premium added ({msg_type}). Send another to add more, or /done when finished.",
                reply_markup=done_kb,
            )
        except Exception as e:
            logger.exception("add_premium_message: %s", e)
            await msg.reply_text(f"Error: {e}")
        return


def register_welcome(app) -> None:
    from telegram.ext import MessageHandler, filters
    # Any media type plus TEXT (for /cancel) while in welcome:add or channel:wait.
    # Use group -2 so broadcast capture (group -1) can still see messages.
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & (
                filters.TEXT
                | filters.PHOTO
                | filters.VIDEO
                | filters.ANIMATION
                | filters.Document.ALL
                | filters.AUDIO
                | filters.VOICE
            ),
            capture_message_for_welcome,
        ),
        group=-2,
    )
