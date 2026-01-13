"""
Settings Menu Plugin
Menu handlers for the /settings command and navigation
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.channels import channels_manager
from services.rate_limiter import rate_limit
from core import is_authorized_user
import logging

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("settings") & filters.private)
@rate_limit(max_requests=30, window=60)
async def settings_menu(client: Client, message: Message):
    """תפריט הגדרות ראשי"""
    # בדיקת הרשאה
    if not is_authorized_user(message.from_user.id):
        logger.warning(f"⛔ Unauthorized settings access by user {message.from_user.id}")
        return
    
    logger.info(f"📋 User {message.from_user.id} opened settings menu")
    
    # קבלת רשימת ערוצים/קבוצות קיימים
    telegram_channels = channels_manager.get_repository("telegram")
    whatsapp_groups = channels_manager.get_repository("whatsapp")
    logger.debug(f"📊 Repository status: {len(telegram_channels)} Telegram channels, {len(whatsapp_groups)} WhatsApp groups")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ערוך תבניות", callback_data="templates")],
        [InlineKeyboardButton("🍪 עדכן cookies", callback_data="update_cookies")],
        [InlineKeyboardButton("➕ הוספת ערוצים/קבוצות", callback_data="add_channels")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    # בניית טקסט עם מידע על ערוצים/קבוצות
    text = "⚙️ **הגדרות בוט**\n\n"
    text += "**מאגר ערוצים/קבוצות:**\n"
    text += f"📱 טלגרם: {len(telegram_channels)} ערוצים\n"
    text += f"💬 וואטסאפ: {len(whatsapp_groups)} קבוצות\n\n"
    text += "בחר פעולה:"
    
    await message.reply_text(text, reply_markup=keyboard)
    logger.info(f"✅ Settings menu displayed to user {message.from_user.id}")


@Client.on_callback_query(filters.regex("^back_to_settings$"))
@rate_limit(max_requests=50, window=60)
async def back_to_settings(client: Client, query: CallbackQuery):
    """חזרה לתפריט הגדרות"""
    logger.info(f"🔙 User {query.from_user.id} returning to settings menu")
    
    # קבלת רשימת ערוצים/קבוצות קיימים
    telegram_channels = channels_manager.get_repository("telegram")
    whatsapp_groups = channels_manager.get_repository("whatsapp")
    logger.debug(f"📊 Repository status: {len(telegram_channels)} Telegram channels, {len(whatsapp_groups)} WhatsApp groups")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ערוך תבניות", callback_data="templates")],
        [InlineKeyboardButton("🍪 עדכן cookies", callback_data="update_cookies")],
        [InlineKeyboardButton("➕ הוספת ערוצים/קבוצות", callback_data="add_channels")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    # בניית טקסט עם מידע על ערוצים/קבוצות
    text = "⚙️ **הגדרות בוט**\n\n"
    text += "**מאגר ערוצים/קבוצות:**\n"
    text += f"📱 טלגרם: {len(telegram_channels)} ערוצים\n"
    text += f"💬 וואטסאפ: {len(whatsapp_groups)} קבוצות\n\n"
    text += "בחר פעולה:"
    
    await query.message.edit_text(text, reply_markup=keyboard)
    await query.answer()
    logger.debug(f"✅ Settings menu refreshed for user {query.from_user.id}")


@Client.on_callback_query(filters.regex("^close$"))
@rate_limit(max_requests=50, window=60)
async def close_settings(client: Client, query: CallbackQuery):
    """סגירת תפריט הגדרות"""
    await query.message.delete()
    await query.answer()


logger.info("✅ Settings menu handlers loaded")
