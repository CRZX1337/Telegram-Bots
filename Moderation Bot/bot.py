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

def parse_duration(duration: str) -> timedelta:
    """Parse duration string like '7d', '3h', '5m' into a timedelta object."""
    match = re.match(r"(\d+)([dhm])", duration)
    if not match:
        raise ValueError("Invalid duration format. Use formats like '7d', '3h', '5m'.")
    amount, unit = match.groups()
    amount = int(amount)
    if unit == "d":
        return timedelta(days=amount)
    elif unit == "h":
        return timedelta(hours=amount)
    elif unit == "m":
        return timedelta(minutes=amount)

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

# Moderation functions
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user, duration: timedelta):
    """Mute a user for a given duration."""
    try:
        until_date = datetime.now(timezone.utc) + duration
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_add_web_page_previews=False,
                can_send_other_messages=False
            ),
            until_date=until_date
        )
        mute_hours = duration.total_seconds() / 3600
        await update.effective_message.reply_text(
            f"🔇 {user.mention_html()} muted for {mute_hours:.1f} hours!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Mute error: {e}")
        await update.effective_message.reply_text(f"⚠️ Mute failed: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user, duration: timedelta = None):
    """Ban a user for a specific duration or permanently."""
    try:
        until_date = None
        if duration:
            until_date = datetime.now(timezone.utc) + duration
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            until_date=until_date
        )
        if duration:
            await update.effective_message.reply_text(
                f"🔨 {user.mention_html()} banned for {duration.total_seconds() // 3600:.1f} hours!",
                parse_mode="HTML"
            )
        else:
            await update.effective_message.reply_text(
                f"🔨 {user.mention_html()} has been permanently banned!",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ban error: {e}")
        await update.effective_message.reply_text(f"⚠️ Ban failed: {e}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text("🤖 Bot is online and ready to help!")

@admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel with inline buttons."""
    keyboard = [
        [
            InlineKeyboardButton("🚫 Ban", callback_data="ban"),
            InlineKeyboardButton("🗑️ Delete", callback_data="delete")
        ],
        [
            InlineKeyboardButton("✅ Unban", callback_data="unban"),
            InlineKeyboardButton("⚠️ Warn", callback_data="warn")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ]
    ]
    await update.message.reply_text(
        "🔧 Admin Menu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_required
async def handle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user handler."""
    user = None
    duration = None
    if context.args:
        try:
            user_id = int(context.args[0])
            user = await context.bot.get_chat(user_id)
            if len(context.args) > 1:
                duration = parse_duration(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or duration format!")
            return
    elif update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        if len(context.args) > 0:
            duration = parse_duration(context.args[0])
    else:
        await update.message.reply_text("❌ Specify a user ID or reply to a message!")
        return

    await ban_user(update, context, user, duration)

@admin_required
async def handle_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute user handler."""
    user = None
    duration = timedelta(hours=DEFAULT_MUTE_DURATION)  # Default mute duration
    if context.args:
        try:
            user_id = int(context.args[0])
            user = await context.bot.get_chat(user_id)
            if len(context.args) > 1:
                duration = parse_duration(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or duration format!")
            return
    elif update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        if len(context.args) > 0:
            duration = parse_duration(context.args[0])
    else:
        await update.message.reply_text("❌ Specify a user ID or reply to a message!")
        return

    await mute_user(update, context, user, duration)

# Main function
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", handle_ban, filters=group_filter))
    application.add_handler(CommandHandler("mute", handle_mute, filters=group_filter))
    
    logger.info("Bot started successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()