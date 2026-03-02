"""Entry point: webhook server, uvloop, pool, redis, handlers."""
import asyncio
import time
import sys

# Prefer uvloop on non-Windows
if sys.platform != "win32":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass

from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest

from bot import config
from bot.database import init_pool, close_pool, ensure_tables
from bot.redis_client import init_redis, close_redis
from bot.handlers import register_handlers
from bot.handlers.broadcast import broadcast_worker
from bot.utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


async def post_init(app: Application) -> None:
    """After application init: DB, Redis, tables, broadcast worker."""
    await init_pool()
    await init_redis()
    await ensure_tables()
    app.bot_data["start_time"] = time.time()
    asyncio.create_task(broadcast_worker(app.bot))
    logger.info("Bot initialized; pool, redis, broadcast worker started.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler: log and optionally notify."""
    logger.exception("Update %s caused error: %s", update, context.error)
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "An error occurred. Please try again or contact the admin."
            )
        except Exception:
            pass


def main() -> None:
    setup_logging()

    # Python 3.12+ no longer auto-creates an event loop in the main thread; run_webhook
    # needs one. Set it explicitly (uvloop policy already installed above on non-Windows).
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    # HTTP client with timeouts
    request = HTTPXRequest(connection_pool_size=8, read_timeout=30, write_timeout=30)

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .request(request)
        .build()
    )

    register_handlers(app)
    app.add_error_handler(error_handler)

    # Run webhook
    app.run_webhook(
        listen=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        url_path=config.WEBHOOK_PATH,
        webhook_url=f"{config.WEBHOOK_URL}/{config.WEBHOOK_PATH}",
    )


if __name__ == "__main__":
    main()
