import os
import json
import logging
import re
from functools import wraps
from datetime import datetime, timedelta, timezone
from telegram import (
    Update, 
    ChatPermissions,
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ChatMember
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
    MessageHandler,
    ChatMemberHandler
)
from telegram.constants import ChatMemberStatus

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = -1002270622838  # Replace with your actual group ID
ADMIN_IDS = {5685799208, 136817688, 1087968824}
SETTINGS_FILE = "group_settings.json"
WARN_FILE = "warnings.json"
DEFAULT_MUTE_DURATION = 1  # Hours

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Helper functions
async def is_admin(update: Update) -> bool:
    """Check if user is admin or bot owner"""
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return True
    
    try:
        chat_member = await update.effective_chat.get_member(user.id)
        return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f"Admin check failed: {e}")
        return False

def admin_required(func):
    """Decorator to restrict commands to admins"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not await is_admin(update):
            await update.effective_message.reply_text("⚠️ Access denied: Admins only")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# Data handling
def load_data(filename, default):
    try:
        with open(filename) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return default

def save_data(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False

async def get_target_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Extract target user ID from command args or replied message"""
    if context.args:
        try:
            return int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format")
            return None
    elif update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    else:
        await update.message.reply_text("❌ Reply to a message or provide user ID")
        return None

# Moderation functions
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, reason: str = None):
    chat_id = str(update.effective_chat.id)
    user_str = str(user_id)
    
    warnings = load_data(WARN_FILE, {})
    chat_warnings = warnings.setdefault(chat_id, {})
    user_warnings = chat_warnings.setdefault(user_str, {"count": 0, "reasons": []})
    
    user_warnings["count"] += 1
    if reason:
        user_warnings["reasons"].append(reason)
    
    save_data(WARN_FILE, warnings)
    
    warn_count = user_warnings["count"]
    await update.effective_message.reply_text(
        f"⚠️ User <code>{user_id}</code> warned! (Warnings: {warn_count}/3)",
        parse_mode="HTML"
    )
    
    if warn_count >= 3:
        await mute_user(update, context, user_id)
        user_warnings["count"] = 0
        save_data(WARN_FILE, warnings)

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        settings = load_data(SETTINGS_FILE, {})
        mute_hours = settings.get("mute_duration", DEFAULT_MUTE_DURATION)
        until_date = datetime.now(timezone.utc) + timedelta(hours=mute_hours)
        
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_add_web_page_previews=False,
                can_send_other_messages=False
            ),
            until_date=until_date
        )
        await update.effective_message.reply_text(
            f"🔇 User <code>{user_id}</code> muted for {mute_hours} hours!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Mute error: {e}")
        await update.effective_message.reply_text(f"⚠️ Mute failed: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.effective_message.reply_text(
            f"🔈 User <code>{user_id}</code> unmuted!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Unmute error: {e}")
        await update.effective_message.reply_text(f"⚠️ Unmute failed: {e}")

# Command handlers
@admin_required
async def handle_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn user handler"""
    user_id = await get_target_user_id(update, context)
    if user_id is None:
        return

    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else None
    await warn_user(update, context, user_id, reason)

@admin_required
async def handle_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute user handler"""
    user_id = await get_target_user_id(update, context)
    if user_id is None:
        return

    try:
        hours = int(context.args[1]) if context.args and len(context.args) > 1 else DEFAULT_MUTE_DURATION
        await mute_user(update, context, user_id)
    except ValueError:
        await update.message.reply_text("❌ Invalid mute duration")

@admin_required
async def handle_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute user handler"""
    user_id = await get_target_user_id(update, context)
    if user_id is None:
        return

    await unmute_user(update, context, user_id)

@admin_required
async def handle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user handler"""
    user_id = await get_target_user_id(update, context)
    if user_id is None:
        return
    
    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id
        )
        await update.effective_message.reply_text(
            f"🔨 User <code>{user_id}</code> banned!",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Ban failed: {e}")

@admin_required
async def handle_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user handler"""
    user_id = await get_target_user_id(update, context)
    if user_id is None:
        return
    
    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id
        )
        await update.effective_message.reply_text(
            f"✅ User <code>{user_id}</code> unbanned!",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Unban failed: {e}")

# ... [Keep other existing functions unchanged] ...

def main():
    """Main application setup"""
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    # Handlers
    handlers = [
        CommandHandler("start", start, filters=group_filter),
        CommandHandler("admin", admin_panel, filters=group_filter),
        CommandHandler("warn", handle_warn, filters=group_filter),
        CommandHandler("mute", handle_mute, filters=group_filter),
        CommandHandler("unmute", handle_unmute, filters=group_filter),
        CommandHandler("ban", handle_ban, filters=group_filter),
        CommandHandler("unban", handle_unban, filters=group_filter),
        CallbackQueryHandler(handle_button),
        MessageHandler(filters.TEXT & group_filter, auto_moderation),
        ChatMemberHandler(
            welcome_new_member,
            ChatMemberHandler.CHAT_MEMBER
        )
    ]
    
    for handler in handlers:
        application.add_handler(handler)

    logger.info("Bot started successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()