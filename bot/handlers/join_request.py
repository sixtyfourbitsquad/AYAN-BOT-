"""Chat join request: send default welcome (text + video + APK), do NOT approve, log, update stats."""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden

from bot import config
from bot.database import increment_join_requests
from bot.handlers.admin import send_welcome_flow
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On channel join request: send welcome (Hi {name} + video + APK), log, update stats. Do NOT approve."""
    req = update.chat_join_request
    if not req:
        return
    if req.chat.id != config.CHANNEL_ID:
        return

    user_id = req.from_user.id if req.from_user else 0
    name = (req.from_user.first_name or "User") if req.from_user else "User"
    try:
        await increment_join_requests(user_id)
    except Exception as e:
        logger.exception("increment_join_requests: %s", e)

    logger.info("Join request from user_id=%s", user_id)

    try:
        await send_welcome_flow(context, user_id, name=name)
    except Forbidden:
        logger.info("User %s has not started bot or blocked bot; skip sending", user_id)
    except Exception as e:
        logger.exception("Welcome send to %s: %s", user_id, e)

    # Do NOT call approve_chat_join_request


def register_join_request(app) -> None:
    from telegram.ext import ChatJoinRequestHandler
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
