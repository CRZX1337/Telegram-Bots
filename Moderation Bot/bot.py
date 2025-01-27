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
DEFAULT_MUTE_DURATION = 5  # Hours

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

# Moderation functions
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, reason: str = None):
    user_id = str(user.id)
    chat_id = str(update.effective_chat.id)
    
    warnings = load_data(WARN_FILE, {})
    chat_warnings = warnings.setdefault(chat_id, {})
    user_warnings = chat_warnings.setdefault(user_id, {"count": 0, "reasons": []})
    
    user_warnings["count"] += 1
    if reason:
        user_warnings["reasons"].append(reason)
    
    save_data(WARN_FILE, warnings)
    
    warn_count = user_warnings["count"]
    await update.effective_message.reply_text(
        f"⚠️ {user.mention_html()} warned! (Warnings: {warn_count}/3)",
        parse_mode="HTML"
    )
    
    if warn_count >= 3:
        await mute_user(update, context, user)
        user_warnings["count"] = 0
        save_data(WARN_FILE, warnings)

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    try:
        settings = load_data(SETTINGS_FILE, {})
        mute_hours = settings.get("mute_duration", DEFAULT_MUTE_DURATION)
        until_date = datetime.now(timezone.utc) + timedelta(hours=mute_hours)
        
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
        await update.effective_message.reply_text(
            f"🔇 {user.mention_html()} muted for {mute_hours} hours!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Mute error: {e}")
        await update.effective_message.reply_text(f"⚠️ Mute failed: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
        )
        await update.effective_message.reply_text(
            f"🔊 {user.mention_html()} has been unmuted!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Unmute error: {e}")
        await update.effective_message.reply_text(f"⚠️ Unmute failed: {e}")

# Welcome handler
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new member events"""
    try:
        if update.chat_member.new_chat_member.status not in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ]:
            return

        settings = load_data(SETTINGS_FILE, {})
        if not settings.get("welcome_enabled", True):
            return

        user = update.chat_member.new_chat_member.user
        welcome_msg = settings.get(
            "welcome_message",
            "👋 Welcome {name}! Please read the rules."
        )
        await update.effective_chat.send_message(
            welcome_msg.format(name=user.mention_html()),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Welcome error: {e}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    if update.effective_chat.id == GROUP_ID:
        await update.message.reply_text("🤖 Bot is ready! Use /admin")

@admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel with inline buttons"""
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

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to get user from reply or user_id argument"""
    if context.args and context.args[0].isdigit():
        try:
            user_id = int(context.args[0])
            chat_member = await update.effective_chat.get_member(user_id)
            return chat_member.user
        except Exception as e:
            logger.error(f"User lookup error: {e}")
            return None
    elif update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

@admin_required
async def handle_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn user handler"""
    user = await get_target_user(update, context)
    if not user:
        await update.effective_message.reply_text("❌ Please reply to a user or provide a user_id")
        return
    
    # Extract reason (skip first argument if it's a user_id)
    reason = " ".join(context.args[1:]) if context.args and context.args[0].isdigit() else " ".join(context.args)
    await warn_user(update, context, user, reason or None)

@admin_required
async def handle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user handler"""
    user = await get_target_user(update, context)
    if not user:
        await update.effective_message.reply_text("❌ Please reply to a user or provide a user_id")
        return
    
    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id
        )
        await update.effective_message.reply_text(
            f"🔨 {user.mention_html()} has been banned!",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Ban failed: {e}")

@admin_required
async def handle_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user handler"""
    user = await get_target_user(update, context)
    if not user:
        await update.effective_message.reply_text("❌ Please reply to a user or provide a user_id")
        return
    
    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user.id
        )
        await update.effective_message.reply_text(
            f"✅ {user.mention_html()} has been unbanned!",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Unban failed: {e}")

@admin_required
async def handle_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute user handler"""
    user = await get_target_user(update, context)
    if not user:
        await update.effective_message.reply_text("❌ Please reply to a user or provide a user_id")
        return
    await unmute_user(update, context, user)

# Callback handler
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(update):
        return

    try:
        if query.data == "ban":
            await query.message.reply_text("ℹ️ Reply to a message with /ban")
        elif query.data == "delete":
            await query.message.reply_text("ℹ️ Reply to a message with /delete")
        elif query.data == "unban":
            await query.message.reply_text("ℹ️ Reply to a message with /unban")
        elif query.data == "warn":
            await query.message.reply_text("ℹ️ Reply to a message with /warn")
        elif query.data == "settings":
            await settings_page(update, context)
    except Exception as e:
        logger.error(f"Button error: {str(e)}")

async def settings_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu"""
    await update.callback_query.message.reply_text("⚙️ Settings menu under construction!")

# Auto-moderation
async def auto_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-moderate messages"""
    if await is_admin(update):
        return
    
    settings = load_data(SETTINGS_FILE, {})
    if not settings.get("auto_moderation", False):
        return
    
    text = update.message.text or update.message.caption
    if not text:
        return
    
    banned_patterns = settings.get("banned_patterns", [])
    for pattern in banned_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            try:
                await update.message.delete()
                await warn_user(
                    update, 
                    context,
                    update.effective_user,
                    reason=f"Banned pattern: {pattern}"
                )
            except Exception as e:
                logger.error(f"Auto-mod failed: {e}")

def main():
    """Main application setup"""
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    group_filter = filters.Chat(chat_id=GROUP_ID)
    
    # Handlers
    handlers = [
        CommandHandler("start", start, filters=group_filter),
        CommandHandler("admin", admin_panel, filters=group_filter),
        CommandHandler("warn", handle_warn, filters=group_filter),
        CommandHandler("ban", handle_ban, filters=group_filter),
        CommandHandler("unban", handle_unban, filters=group_filter),
        CommandHandler("unmute", handle_unmute, filters=group_filter),
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