"""Admin panel inline keyboards."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Set Welcome Video", callback_data="admin:set_video")],
        [InlineKeyboardButton("📦 Set Welcome APK", callback_data="admin:set_apk")],
        [InlineKeyboardButton("🔍 Preview Welcome", callback_data="admin:preview_welcome")],
        [InlineKeyboardButton("📊 User Stats", callback_data="admin:stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙ Bot Configuration", callback_data="admin:config")],
        [InlineKeyboardButton("📜 View Logs", callback_data="admin:logs")],
    ])


def confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast:cancel"),
        ],
    ])


def back_to_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back to Admin", callback_data="admin:main")],
    ])
