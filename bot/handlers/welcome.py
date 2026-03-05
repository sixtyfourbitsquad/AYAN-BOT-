"""Capture admin's welcome video and APK when they send them (state: welcome:set_video / welcome:set_apk)."""
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.database import set_welcome_video, set_welcome_apk, add_extra_message
from bot.redis_client import get_admin_state, clear_admin_state
from bot.keyboards import admin_main_keyboard, back_to_admin_keyboard
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def capture_message_for_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When admin is in welcome:set_video / welcome:set_apk / extra:add, store config or extra message."""
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id not in config.ADMIN_IDS:
        return

    state = await get_admin_state(user_id)
    if not state:
        return
    if update.message and update.message.text and update.message.text.strip() == "/cancel":
        await clear_admin_state(user_id)
        await update.message.reply_text("Cancelled.", reply_markup=admin_main_keyboard())
        return
    if state == "welcome:set_video":
        if not update.message or not update.message.video:
            await update.message.reply_text("Please send a video, or /cancel to cancel.", reply_markup=back_to_admin_keyboard())
            return
        file_id = update.message.video.file_id
        caption = (update.message.caption or "").strip()
        try:
            await set_welcome_video(file_id, caption or None)
            await clear_admin_state(user_id)
            await update.message.reply_text(
                "✅ Welcome video set. Caption saved." if caption else "✅ Welcome video set.",
                reply_markup=admin_main_keyboard(),
            )
        except Exception as e:
            logger.exception("set_welcome_video: %s", e)
            await update.message.reply_text(f"Error: {e}")
        return
    if state == "welcome:set_apk":
        if not update.message or not update.message.document:
            await update.message.reply_text("Please send the APK as a document, or /cancel to cancel.", reply_markup=back_to_admin_keyboard())
            return
        file_id = update.message.document.file_id
        caption = (update.message.caption or "").strip()
        try:
            await set_welcome_apk(file_id, caption or None)
            await clear_admin_state(user_id)
            await update.message.reply_text(
                "✅ Welcome APK set. Caption saved." if caption else "✅ Welcome APK set.",
                reply_markup=admin_main_keyboard(),
            )
        except Exception as e:
            logger.exception("set_welcome_apk: %s", e)
            await update.message.reply_text(f"Error: {e}")
        return
    if state == "extra:add":
        msg = update.message
        if not msg:
            return
        msg_type = "text"
        file_id = None
        text = None
        caption = None
        if msg.text and not (msg.photo or msg.video or msg.animation or msg.document or msg.audio or msg.voice):
            msg_type = "text"
            text = msg.text
        else:
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
            caption = (msg.caption or "").strip()
        if msg_type != "text" and not file_id:
            await msg.reply_text("Send text or one media message, or /cancel to abort.", reply_markup=back_to_admin_keyboard())
            return
        try:
            await add_extra_message(msg_type, file_id, text or "", caption)
            await clear_admin_state(user_id)
            await msg.reply_text(
                f"✅ Extra welcome message added ({msg_type}).",
                reply_markup=admin_main_keyboard(),
            )
        except Exception as e:
            logger.exception("add_extra_message: %s", e)
            await msg.reply_text(f"Error: {e}")
        return


def register_welcome(app) -> None:
    from telegram.ext import MessageHandler, filters
    # VIDEO, Document, or TEXT (for /cancel)
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.VIDEO | filters.Document.ALL | filters.TEXT),
            capture_message_for_welcome,
        ),
        group=-1,
    )
