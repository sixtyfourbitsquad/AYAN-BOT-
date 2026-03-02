"""Welcome message add/delete/preview callbacks and message handler for capturing content."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import config
from bot.database import (
    add_welcome_message,
    delete_welcome_message,
    get_welcome_message_by_id,
    get_welcome_messages_ordered,
    move_welcome_message_up,
    move_welcome_message_down,
)
from bot.redis_client import get_admin_state, set_admin_state, clear_admin_state
from bot.keyboards import admin_main_keyboard, welcome_manage_keyboard, welcome_list_keyboard, welcome_type_keyboard
from bot.handlers.admin import send_welcome_message
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    user_id = update.effective_user.id if update.effective_user else 0
    if not _is_admin(user_id):
        await query.answer("Access denied.", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data.startswith("welcome:type:"):
        msg_type = data.replace("welcome:type:", "")
        await set_admin_state(user_id, f"add_welcome:{msg_type}")
        await query.edit_message_text(
            f"Send the {msg_type} message now (photo/video/document/audio/voice/animation or text). "
            "Send /cancel to abort.",
        )
        return

    if data.startswith("welcome:del:"):
        try:
            msg_id = int(data.split(":")[-1])
        except ValueError:
            return
        ok = await delete_welcome_message(msg_id)
        if ok:
            await query.answer("Deleted.")
        else:
            await query.answer("Not found.", show_alert=True)
        messages = await get_welcome_messages_ordered()
        if not messages:
            await query.edit_message_text(
                "No welcome messages left.",
                reply_markup=welcome_manage_keyboard(),
            )
        else:
            await query.edit_message_text(
                "Manage welcome messages (⬆⬇ reorder, click preview, 🗑 delete):",
                reply_markup=welcome_list_keyboard(messages),
            )
        return

    if data.startswith("welcome:up:"):
        try:
            msg_id = int(data.split(":")[-1])
        except ValueError:
            return
        ok = await move_welcome_message_up(msg_id)
        await query.answer("Moved up." if ok else "Already first.")
        messages = await get_welcome_messages_ordered()
        await query.edit_message_text(
            "Manage welcome messages (⬆⬇ reorder, click preview, 🗑 delete):",
            reply_markup=welcome_list_keyboard(messages),
        )
        return

    if data.startswith("welcome:down:"):
        try:
            msg_id = int(data.split(":")[-1])
        except ValueError:
            return
        ok = await move_welcome_message_down(msg_id)
        await query.answer("Moved down." if ok else "Already last.")
        messages = await get_welcome_messages_ordered()
        await query.edit_message_text(
            "Manage welcome messages (⬆⬇ reorder, click preview, 🗑 delete):",
            reply_markup=welcome_list_keyboard(messages),
        )
        return

    if data.startswith("welcome:preview:"):
        try:
            msg_id = int(data.split(":")[-1])
        except ValueError:
            return
        m = await get_welcome_message_by_id(msg_id)
        if not m:
            await query.answer("Not found.", show_alert=True)
            return
        chat_id = query.message.chat_id if query.message else 0
        try:
            await send_welcome_message(context, chat_id, m)
            await query.answer("Preview sent.")
        except Exception as e:
            logger.exception("Preview: %s", e)
            await query.answer(f"Error: {e}", show_alert=True)
        return


async def capture_message_for_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle message when admin is in 'add_welcome:<type>' state."""
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id not in config.ADMIN_IDS:
        return

    state = await get_admin_state(user_id)
    if not state or not state.startswith("add_welcome:"):
        return

    if update.message and update.message.text and update.message.text.strip() == "/cancel":
        await clear_admin_state(user_id)
        await update.message.reply_text("Cancelled.", reply_markup=admin_main_keyboard())
        return

    parts = state.split(":", 1)
    msg_type = parts[1] if len(parts) > 1 else "text"

    file_id = None
    text = None
    caption = None

    if update.message:
        if update.message.text:
            text = update.message.text
            if msg_type != "text":
                caption = update.message.text
        if update.message.caption is not None:
            caption = update.message.caption
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.video:
            file_id = update.message.video.file_id
        elif update.message.animation:
            file_id = update.message.animation.file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        elif update.message.audio:
            file_id = update.message.audio.file_id
        elif update.message.voice:
            file_id = update.message.voice.file_id

    if msg_type == "text" and not text:
        text = "(empty)"
    if msg_type != "text" and not file_id:
        await update.message.reply_text("Send a media message (photo/video/etc.) or use /cancel.")
        return

    try:
        mid = await add_welcome_message(msg_type, file_id, text or "", caption)
        await clear_admin_state(user_id)
        await update.message.reply_text(
            f"✅ Welcome message added (id: {mid}).",
            reply_markup=admin_main_keyboard(),
        )
    except Exception as e:
        logger.exception("add_welcome_message: %s", e)
        await update.message.reply_text(f"Error: {e}")


def register_welcome(app) -> None:
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
    app.add_handler(CallbackQueryHandler(welcome_callback, pattern="^welcome:"))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL | filters.AUDIO | filters.VOICE),
            capture_message_for_welcome,
        )
    )
