"""Admin panel inline keyboards."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Welcome Message", callback_data="admin:add_welcome")],
        [InlineKeyboardButton("📂 Manage Welcome Messages", callback_data="admin:manage_welcome")],
        [InlineKeyboardButton("🔍 Preview Welcome Messages", callback_data="admin:preview_welcome")],
        [InlineKeyboardButton("📊 User Stats", callback_data="admin:stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙ Bot Configuration", callback_data="admin:config")],
        [InlineKeyboardButton("📜 View Logs", callback_data="admin:logs")],
    ])


def welcome_manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back", callback_data="admin:main")],
    ])


def welcome_list_keyboard(messages: list) -> InlineKeyboardMarkup:
    """messages: list of dicts with id, type, position."""
    rows = []
    for i, m in enumerate(messages):
        row = [
            InlineKeyboardButton(
                f"#{m['position']+1} {m['type']}",
                callback_data=f"welcome:preview:{m['id']}",
            ),
            InlineKeyboardButton("⬆", callback_data=f"welcome:up:{m['id']}"),
            InlineKeyboardButton("⬇", callback_data=f"welcome:down:{m['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"welcome:del:{m['id']}"),
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="admin:manage_welcome")])
    return InlineKeyboardMarkup(rows)


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
