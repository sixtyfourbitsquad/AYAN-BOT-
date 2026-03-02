"""Capture admin's welcome video and APK when they send them (state: welcome:set_video / welcome:set_apk)."""
from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.database import set_welcome_video, set_welcome_apk
from bot.redis_client import get_admin_state, clear_admin_state
from bot.keyboards import admin_main_keyboard, back_to_admin_keyboard
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def capture_message_for_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When admin is in welcome:set_video or welcome:set_apk, store file_id and caption."""
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
