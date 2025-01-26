import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)

# Konfiguration
BOT_TOKEN = "7457097413:AAF0eKMO6rJUmp7OIbVxqd2Mt0Em84TqsG4"
GROUP_ID = -1002270622838
ADMIN_IDS = {5685799208, 136817688}
SETTINGS_FILE = "group_settings.json"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Hilfsfunktionen
async def is_admin(update: Update) -> bool:
    try:
        return (
            update.effective_chat.id == GROUP_ID
            and update.effective_user.id in ADMIN_IDS
        )
    except Exception as e:
        logger.error(f"Admin-Check Fehler: {str(e)}")
        return False

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# Befehle
async def start(update: Update, context: CallbackContext):
    if update.effective_chat.id == GROUP_ID:
        await update.message.reply_text("🤖 Bot bereit! Nutze /admin")

async def admin_panel(update: Update, context: CallbackContext):
    if not await is_admin(update):
        return
    
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

# Button-Handler
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
        logger.error(f"Button-Fehler: {str(e)}")

# Moderationsfunktionen
async def handle_ban(update: Update, context: CallbackContext):
    if not await is_admin(update):
        return
    
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(
            chat_id=GROUP_ID,
            user_id=user.id
        )
        await update.message.reply_text(f"⛔ {user.mention_html()} wurde gebannt!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

async def handle_unban(update: Update, context: CallbackContext):
    if not await is_admin(update):
        return
    
    try:
        user = update.message.reply_to_message.from_user
        await context.bot.unban_chat_member(
            chat_id=GROUP_ID,
            user_id=user.id
        )
        await update.message.reply_text(f"✅ {user.mention_html()} wurde entbannt!", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

async def handle_delete(update: Update, context: CallbackContext):
    if not await is_admin(update):
        return
    
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"⚠️ Fehler: {str(e)}")

# Hauptprogramm
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    # Handler
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