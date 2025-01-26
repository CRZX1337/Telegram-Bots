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

# === KONFIGURATION ===
BOT_TOKEN = "7457097413:AAF0eKMO6rJUmp7OIbVxqd2Mt0Em84TqsG4"
GROUP_ID = -1002270622838  # MIT @RawDataBot ÜBERPRÜFEN!
ADMIN_IDS = {5685799208, 136817688, 1087968824}  # DEINE ADMIN-ID
SETTINGS_FILE = "group_settings.json"

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === HELFERFUNKTIONEN ===
def debug_info(update: Update):
    """Loggt kritische Debug-Informationen"""
    try:
        logger.info("=== DEBUG INFORMATION ===")
        logger.info(f"User ID: {update.effective_user.id}")
        logger.info(f"Chat ID: {update.effective_chat.id}")
        logger.info(f"Chat Type: {update.effective_chat.type}")
        logger.info(f"Is Admin: {update.effective_user.id in ADMIN_IDS}")
        logger.info(f"Correct Group: {update.effective_chat.id == GROUP_ID}")
    except Exception as e:
        logger.error(f"Debug failed: {str(e)}")

async def is_admin(update: Update) -> bool:
    """Überprüft Admin-Rechte mit detailliertem Logging"""
    try:
        correct_group = update.effective_chat.id == GROUP_ID
        is_admin_user = update.effective_user.id in ADMIN_IDS
        logger.info(f"Admin Check - Group: {correct_group}, User: {is_admin_user}")
        
        if not correct_group:
            logger.warning(f"Falsche Gruppe! Erwartet: {GROUP_ID}, Bekommen: {update.effective_chat.id}")
            
        if not is_admin_user:
            logger.warning(f"Unberechtigter User: {update.effective_user.id}")
            
        return correct_group and is_admin_user
    except Exception as e:
        logger.error(f"Admin Check Error: {str(e)}")
        return False

# === BOT-FUNKTIONEN ===
async def start(update: Update, context: CallbackContext):
    """Startbefehl mit Gruppencheck"""
    debug_info(update)
    if update.effective_chat.id == GROUP_ID:
        await update.message.reply_text("🤖 Bot online! Nutze /admin")
    else:
        await update.message.reply_text("❌ Dieser Bot funktioniert nur in der Gruppe!")

async def admin_panel(update: Update, context: CallbackContext):
    """Admin-Panel mit doppeltem Check"""
    debug_info(update)
    
    if not await is_admin(update):
        await update.message.reply_text("🚫 Zugriff verweigert!")
        return

    # Erzwinge Gruppencheck
    if update.effective_chat.id != GROUP_ID:
        await update.message.reply_text("❌ Nur in der Hauptgruppe verfügbar!")
        return

    try:
        keyboard = [
            [InlineKeyboardButton("🚫 Nutzer sperren", callback_data="ban_user")],
            [InlineKeyboardButton("🗑️ Nachricht löschen", callback_data="delete_msg")]
        ]
        await update.message.reply_text(
            "🔧 ADMIN-PANEL:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Panel Error: {str(e)}")

async def handle_ban(update: Update, context: CallbackContext):
    """Ban-Befehl mit vollständiger Fehlerbehandlung"""
    debug_info(update)
    
    if not await is_admin(update):
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Antworte auf eine Nachricht des Nutzers!")
        return

    try:
        target_user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(
            chat_id=GROUP_ID,
            user_id=target_user.id
        )
        await update.message.reply_text(f"⛔ {target_user.mention_html()} wurde gesperrt!", parse_mode="HTML")
        logger.info(f"Erfolgreich gebannt: {target_user.id}")
    except Exception as e:
        error_msg = f"⚠️ Bann fehlgeschlagen: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(error_msg)

async def handle_delete(update: Update, context: CallbackContext):
    """Nachrichtenlöschung mit Bestätigung"""
    debug_info(update)
    
    if not await is_admin(update):
        return

    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
        logger.info("Nachricht erfolgreich gelöscht")
    except Exception as e:
        error_msg = f"⚠️ Löschung fehlgeschlagen: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(error_msg)

async def button_handler(update: Update, context: CallbackContext):
    """Verarbeitung aller Inline-Buttons"""
    query = update.callback_query
    await query.answer()
    
    debug_info(update)
    
    if not await is_admin(update):
        return

    try:
        if query.data == "ban_user":
            await query.message.reply_text("ℹ️ Nutze /ban als Antwort auf eine Nachricht")
        elif query.data == "delete_msg":
            await query.message.reply_text("ℹ️ Nutze /delete als Antwort auf eine Nachricht")
        
        await query.message.delete()
    except Exception as e:
        logger.error(f"Button Error: {str(e)}")

# === HAUPTPROGRAMM ===
def main():
    # Initialisiere Application mit Timeout-Einstellungen
    application = ApplicationBuilder()\
        .token(BOT_TOKEN)\
        .connect_timeout(30)\
        .read_timeout(30)\
        .pool_timeout(30)\
        .build()

    # Registriere Handler mit expliziten Filtern
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    application.add_handler(CommandHandler("start", start, group_filter))
    application.add_handler(CommandHandler("admin", admin_panel, group_filter))
    application.add_handler(CommandHandler("ban", handle_ban, group_filter))
    application.add_handler(CommandHandler("delete", handle_delete, group_filter))
    application.add_handler(CallbackQueryHandler(button_handler, group_filter))

    # Starte den Bot
    logger.info("=== BOT STARTET ===")
    application.run_polling()

if __name__ == "__main__":
    main()