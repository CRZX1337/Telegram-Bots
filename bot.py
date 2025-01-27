import os
import json
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token should be stored as an environment variable
GROUP_ID = -1002270622838  # Replace with your group ID
ADMIN_IDS = {5685799208, 136817688, 1087968824}
SETTINGS_FILE = "group_settings.json"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Utility Functions
async def is_admin(update: Update) -> bool:
    try:
        return (
            update.effective_chat.id == GROUP_ID
            and update.effective_user.id in ADMIN_IDS
        )
    except Exception as e:
        logger.error(f"Admin check failed: {str(e)}")
        return False

def admin_required(func):
    """Decorator to restrict commands to admins."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if not await is_admin(update):
            await update.message.reply_text("⚠️ Zugriff verweigert: Nur Admins erlaubt.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"{SETTINGS_FILE} not found. Initializing default settings.")
        save_settings({})
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Commands
async def start(update: Update, context: CallbackContext):
    if update.effective_chat.id == GROUP_ID:
        await update.message.reply_text("🤖 Bot bereit! Nutze /admin")

@admin_required
async def admin_panel(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("🚫 Ban", callback_data="ban"),
            InlineKeyboardButton("🗑️ Delete", callback_data="delete")
        ],
        [
            InlineKeyboardButton("✅ Unban", callback_data="unban"),
            InlineKeyboardButton("⚙️ Einstellungen", callback_data="settings")
        ]
    ]
    await update.message.reply_text(
        "🔧 Admin-Menü:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Button Handler
async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if not await is_admin(update):
        return

    try:
        if query.data == "ban":
            await query.message.reply_text("ℹ️ Antworten Sie auf eine Nachricht mit /ban")
        elif query.data == "delete":
            await query.message.reply_text("ℹ️ Antworten Sie auf eine Nachricht mit /delete")
        elif query.data == "unban":
            await query.message.reply_text("ℹ️ Antworten Sie auf eine Nachricht mit /unban")
        
        await query.message.delete()
    except Exception as e:
        logger.error(f"Button error: {str(e)}")

# Moderation Functions
@admin_required
async def handle_ban(update: Update, context: CallbackContext):
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(
            chat_id=GROUP_ID,
            user_id=user.id
        )
        await update.message.reply_text(f"⛔ {user.mention_html()} wurde gebannt!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

@admin_required
async def handle_unban(update: Update, context: CallbackContext):
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.unban_chat_member(
            chat_id=GROUP_ID,
            user_id=user.id
        )
        await update.message.reply_text(f"✅ {user.mention_html()} wurde entbannt!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

@admin_required
async def handle_delete(update: Update, context: CallbackContext):
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

# Main Program
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    # Handlers
    handlers = [
        CommandHandler("start", start, group_filter),
        CommandHandler("admin", admin_panel, group_filter),
        CommandHandler("ban", handle_ban, group_filter),
        CommandHandler("unban", handle_unban, group_filter),
        CommandHandler("delete", handle_delete, group_filter),
        CallbackQueryHandler(handle_button)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    application.run_polling()

if __name__ == "__main__":
    main()