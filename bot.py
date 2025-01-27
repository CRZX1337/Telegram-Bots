import os
import json
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
    MessageHandler
)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Store your bot token as an environment variable
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
    """Check if the user is an admin."""
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
    """Load settings from a JSON file."""
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"{SETTINGS_FILE} not found. Initializing default settings.")
        save_settings({
            "welcome_message": True,
            "auto_moderation": False,
            "banned_words": ["spam", "fake"],
        })
        return load_settings()
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        return {}

def save_settings(settings):
    """Save settings to a JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving settings: {e}")

# Commands
async def start(update: Update, context: CallbackContext):
    """Start command."""
    if update.effective_chat.id == GROUP_ID:
        await update.message.reply_text("🤖 Bot bereit! Nutze /admin")

@admin_required
async def admin_panel(update: Update, context: CallbackContext):
    """Admin panel with inline buttons."""
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

# Moderation Actions
@admin_required
async def handle_ban(update: Update, context: CallbackContext):
    """Ban a user."""
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
    """Unban a user."""
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
    """Delete a message."""
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

# Auto Moderation
async def auto_moderation(update: Update, context: CallbackContext):
    """Check messages for banned words if auto-moderation is enabled."""
    settings = load_settings()
    if settings.get("auto_moderation", False):
        banned_words = settings.get("banned_words", [])
        if any(word in update.message.text.lower() for word in banned_words):
            try:
                await update.message.delete()
                logger.info(f"Deleted message from {update.effective_user.id} containing banned words.")
            except Exception as e:
                logger.error(f"Failed to delete message: {str(e)}")

# Settings Page
async def settings_page(update: Update, context: CallbackContext):
    """Display the settings page."""
    query = update.callback_query
    await query.answer()

    if not await is_admin(update):
        return

    settings = load_settings()
    keyboard = [
        [
            InlineKeyboardButton(
                f"Begrüßung: {'An' if settings.get('welcome_message', False) else 'Aus'}",
                callback_data="toggle_welcome_message"
            )
        ],
        [
            InlineKeyboardButton(
                f"Auto-Moderation: {'An' if settings.get('auto_moderation', False) else 'Aus'}",
                callback_data="toggle_auto_moderation"
            )
        ],
        [
            InlineKeyboardButton("🔙 Zurück", callback_data="back_to_admin")
        ]
    ]
    await query.edit_message_text(
        "⚙️ Einstellungen:\n\n"
        "- Begrüßung: Automatische Willkommensnachrichten senden.\n"
        "- Auto-Moderation: Nachrichten automatisch auf verbotene Wörter prüfen.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Toggle Functions
async def toggle_welcome_message(update: Update, context: CallbackContext):
    """Toggle the welcome message setting."""
    query = update.callback_query
    await query.answer()

    settings = load_settings()
    settings["welcome_message"] = not settings.get("welcome_message", False)
    save_settings(settings)

    await settings_page(update, context)

async def toggle_auto_moderation(update: Update, context: CallbackContext):
    """Toggle the auto-moderation setting."""
    query = update.callback_query
    await query.answer()

    settings = load_settings()
    settings["auto_moderation"] = not settings.get("auto_moderation", False)
    save_settings(settings)

    await settings_page(update, context)

# Callback Handlers
async def handle_button(update: Update, context: CallbackContext):
    """Handle inline button clicks."""
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
        elif query.data == "settings":
            await settings_page(update, context)
        elif query.data == "toggle_welcome_message":
            await toggle_welcome_message(update, context)
        elif query.data == "toggle_auto_moderation":
            await toggle_auto_moderation(update, context)
        elif query.data == "back_to_admin":
            await admin_panel(update, context)
    except Exception as e:
        logger.error(f"Button error: {str(e)}")

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
        CallbackQueryHandler(handle_button),
        MessageHandler(filters.TEXT & group_filter, auto_moderation)
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    logger.info("Bot started.")
    application.run_polling()

if __name__ == "__main__":
    main()