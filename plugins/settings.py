"""
Settings Plugin
מאפשר עריכת תבניות דרך הבוט עם Inline Keyboard
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.templates import template_manager
from services.user_states import state_manager, UserState
from services.media.utils import update_cookies
from services.channels import channels_manager
from services.rate_limiter import rate_limit
from config import is_authorized_user, ROOT_DIR
import config
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


# מיפוי שמות תבניות לשמות תצוגה
TEMPLATE_NAMES = {
    "telegram_image": "📤 תמונה טלגרם",
    "telegram_audio": "🎵 MP3 טלגרם",
    "telegram_video": "🎬 וידאו טלגרם",
    "whatsapp_image": "📱 תמונה וואטסאפ",
    "whatsapp_audio": "🎵 MP3 וואטסאפ",
    "whatsapp_video": "🎬 וידאו וואטסאפ",
    "telegram_instagram": "📱 אינסטגרם טלגרם",
    "whatsapp_instagram": "📱 אינסטגרם וואטסאפ",
    "whatsapp_status": "📱 סטטוס וואטסאפ"
}


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


@Client.on_callback_query(filters.regex("^templates$"))
@rate_limit(max_requests=50, window=60)
async def templates_menu(client: Client, query: CallbackQuery):
    """תפריט בחירת תבנית לעריכה"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 אפס תבניות", callback_data="reset_templates")],
        [InlineKeyboardButton("📱 תמונה וואטסאפ", callback_data="template_view_whatsapp_image"),
         InlineKeyboardButton("📤 תמונה טלגרם", callback_data="template_view_telegram_image")],
        [InlineKeyboardButton("🎵 שיר וואטסאפ", callback_data="template_view_whatsapp_audio"),
         InlineKeyboardButton("🎵 שיר טלגרם", callback_data="template_view_telegram_audio")],
        [InlineKeyboardButton("🎬 קליפ וואטסאפ", callback_data="template_view_whatsapp_video"),
         InlineKeyboardButton("🎬 קליפ טלגרם", callback_data="template_view_telegram_video")],
        [InlineKeyboardButton("📱 אינסטגרם וואטסאפ", callback_data="template_view_whatsapp_instagram"),
         InlineKeyboardButton("📱 אינסטגרם טלגרם", callback_data="template_view_telegram_instagram")],
        [InlineKeyboardButton("📱 סטטוס וואטסאפ", callback_data="template_view_whatsapp_status")],
        [InlineKeyboardButton("🔙 חזור", callback_data="back_to_settings")]
    ])
    
    help_text = (
        "📝 **עריכת תבניות**\n\n"
        "בחר תבנית לעריכה.\n\n"
        "**משתנים זמינים:**\n"
        "• `{song_name}` - שם שיר\n"
        "• `{artist_name}` - שם זמר\n"
        "• `{year}` - שנה\n"
        "• `{composer}` - מלחין\n"
        "• `{arranger}` - מעבד\n"
        "• `{mixer}` - מיקס\n"
        "• `{credits}` - קרדיטים מלאים\n"
        "• `{youtube_url}` - קישור יוטיוב\n"
        "• `{text}` - טקסט (רק לתבניות אינסטגרם)\n\n"
        "**קישורים:**\n"
        "להוספת קישור: `[טקסט](URL)`"
    )
    
    await query.message.edit_text(help_text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex("^template_view_(.+)$"))
@rate_limit(max_requests=50, window=60)
async def template_view_menu(client: Client, query: CallbackQuery):
    """תפריט תבנית - תצוגה ועריכה"""
    # חילוץ שם התבנית מה-callback_data
    template_name = query.data.replace("template_view_", "")
    logger.info(f"📋 User {query.from_user.id} viewing template: {template_name}")
    
    if template_name not in TEMPLATE_NAMES:
        logger.warning(f"❌ User {query.from_user.id} tried to view unknown template: {template_name}")
        await query.answer("❌ תבנית לא קיימת", show_alert=True)
        return
    
    # קבלת התבנית הנוכחית
    current_template = template_manager.get(template_name)
    template_display_name = TEMPLATE_NAMES[template_name]
    
    # קבלת רשימת ערוצים/קבוצות פעילים
    platform = channels_manager.get_template_platform(template_name)
    active_channels = channels_manager.get_template_channels(template_name, platform)
    logger.debug(f"📊 Template {template_name} has {len(active_channels)} active {platform} channels/groups")
    
    # בניית רשימת ערוצים/קבוצות - עם שמות ערוצים
    channels_text = ""
    if active_channels:
        channel_names = []
        for ch_id in active_channels:
            try:
                # ניסיון לקבל את שם הערוץ מ-Telegram API
                if platform == "telegram":
                    chat_id = int(ch_id) if ch_id.lstrip('-').isdigit() else ch_id
                    chat = await client.get_chat(chat_id)
                    display_name = chat.title if chat.title else ch_id
                else:
                    display_name = ch_id  # WhatsApp - נשאר עם השם המקורי
                # קיצור אם ארוך מדי
                if len(display_name) > 50:
                    display_name = display_name[:50] + "..."
                channel_names.append(f"• {display_name}")
            except Exception as e:
                logger.debug(f"⚠️ Could not get channel name for {ch_id}: {e}")
                # אם נכשל, נשתמש ב-ID/קישור המקורי
                display_name = ch_id[:50] + "..." if len(ch_id) > 50 else ch_id
                channel_names.append(f"• {display_name}")
        channels_text = "\n".join(channel_names)
    else:
        channels_text = "אין ערוצים/קבוצות פעילים מהמאגר"
    
    # אין עוד ערוצים קבועים - הכל דרך המאגר
    fixed_channels_text = ""
    
    # לסטטוס אין ערוצים/קבוצות - זה תמיד "הסטטוס שלי"
    if template_name == "whatsapp_status":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ערוך תבנית", callback_data=f"edit_{template_name}")],
            [InlineKeyboardButton("🔙 חזור", callback_data="templates")]
        ])
        status_info = (
            "**מידע על תבנית הסטטוס:**\n"
            "תבנית זו תשמש לכל התוכן שנשלח לסטטוס וואטסאפ.\n"
            "כשתבחר \"הסטטוס שלי\" כקבוצה, התבנית הזו תשמש במקום התבניות הרגילות.\n\n"
        )
        await query.message.edit_text(
            f"📋 **{template_display_name}**\n\n"
            f"{status_info}"
            f"**תבנית נוכחית:**\n"
            f"```\n{current_template[:500]}{'...' if len(current_template) > 500 else ''}\n```",
            reply_markup=keyboard
        )
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ערוך תבנית", callback_data=f"edit_{template_name}")],
            [InlineKeyboardButton("📢 ערוך ערוצים/קבוצות", callback_data=f"edit_channels_{template_name}")],
            [InlineKeyboardButton("🔙 חזור", callback_data="templates")]
        ])
        
        await query.message.edit_text(
            f"📋 **{template_display_name}**\n\n"
            f"**תבנית נוכחית:**\n"
            f"```\n{current_template[:500]}{'...' if len(current_template) > 500 else ''}\n```\n\n"
            f"**ערוצים/קבוצות מהמאגר (פעילים):**\n"
            f"{channels_text}"
            f"{fixed_channels_text}",
            reply_markup=keyboard
        )
    await query.answer()


@Client.on_callback_query(filters.regex("^edit_(telegram_|whatsapp_)(image|audio|video|instagram|status)$"))
@rate_limit(max_requests=50, window=60)
async def edit_template(client: Client, query: CallbackQuery):
    """התחלת עריכת תבנית"""
    # חילוץ שם התבנית מה-callback_data
    template_name = query.data.replace("edit_", "")
    
    if template_name not in TEMPLATE_NAMES:
        await query.answer("❌ תבנית לא קיימת", show_alert=True)
        return
    
    # קבלת התבנית הנוכחית
    current_template = template_manager.get(template_name)
    template_display_name = TEMPLATE_NAMES[template_name]
    
    # עדכון מצב המשתמש
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.EDITING_TEMPLATE)
    session.editing_template_name = template_name
    
    logger.info(f"✏️ User {query.from_user.id} started editing template: {template_name}")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור", callback_data=f"template_view_{template_name}")]
    ])
    
    # הודעת עזרה מפורטת - משתנה לפי סוג התבנית
    if template_name in ["telegram_instagram", "whatsapp_instagram"]:
        help_text = (
            "**משתנים זמינים:**\n"
            "• `{text}` - הטקסט שהמשתמש שלח\n\n"
            "**קישורים:**\n"
            "להוספת קישור: `[טקסט](URL)`"
        )
    elif template_name == "whatsapp_status":
        help_text = (
            "**משתנים זמינים:**\n"
            "• `{song_name}` - שם שיר\n"
            "• `{artist_name}` - שם זמר\n"
            "• `{youtube_url}` - קישור יוטיוב\n\n"
            "**מידע:**\n"
            "תבנית זו תשמש לכל התוכן שנשלח לסטטוס וואטסאפ.\n"
            "כשתבחר \"הסטטוס שלי\" כקבוצה, התבנית הזו תשמש במקום התבניות הרגילות.\n\n"
            "**קישורים:**\n"
            "להוספת קישור: `[טקסט](URL)`"
        )
    else:
        help_text = (
            "**משתנים זמינים:**\n"
            "• `{song_name}` - שם שיר\n"
            "• `{artist_name}` - שם זמר\n"
            "• `{year}` - שנה\n"
            "• `{composer}` - מלחין\n"
            "• `{arranger}` - מעבד\n"
            "• `{mixer}` - מיקס\n"
            "• `{credits}` - קרדיטים מלאים\n"
            "• `{youtube_url}` - קישור יוטיוב\n\n"
            "**קישורים:**\n"
            "להוספת קישור: `[טקסט](URL)`"
        )
    
    await query.message.edit_text(
        f"✏️ **עריכת {template_display_name}**\n\n"
        f"**תבנית נוכחית:**\n"
        f"```\n{current_template}\n```\n\n"
        f"{help_text}\n\n"
        f"📤 **שלח את התבנית החדשה עכשיו:**",
        reply_markup=keyboard
    )
    
    await query.answer("✅ מוכן לעריכה - שלח את הטקסט החדש")


@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue"]), group=-1)
async def handle_template_edit(client: Client, message: Message):
    """
    מטפל בטקסט חדש לתבנית
    group=-1 נותן עדיפות הכי גבוהה - רץ לפני כל handlers אחרים
    """
    user = message.from_user
    logger.debug(f"🔍 [TEMPLATE_EDIT] Handler triggered for user {user.id}, text: {message.text[:50] if message.text else 'None'}")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.debug(f"⛔ [TEMPLATE_EDIT] User {user.id} not authorized")
        return
    
    session = state_manager.get_session(user.id)
    logger.debug(f"📊 [TEMPLATE_EDIT] User {user.id} state: {session.state}")
    
    # בדיקה אם המשתמש במצב עריכת תבנית
    if session.state != UserState.EDITING_TEMPLATE:
        # לא במצב עריכת תבנית - לא לטפל כאן, לתת ל-handlers אחרים לטפל
        # אם המשתמש במצב ADDING_CHANNEL, ה-handler הבא יטפל
        logger.debug(f"🔍 [TEMPLATE_EDIT] User {user.id} not in EDITING_TEMPLATE state (current: {session.state}), passing to next handler")
        return
    
    if not hasattr(session, 'editing_template_name'):
        logger.warning(f"⚠️ User {user.id} in EDITING_TEMPLATE state but no editing_template_name attribute")
        # איפוס המצב אם יש בעיה
        session.update_state(UserState.IDLE)
        await message.reply_text("❌ שגיאה: לא נמצא שם תבנית לעריכה. המצב אופס.")
        return
    
    template_name = session.editing_template_name
    
    if template_name not in TEMPLATE_NAMES:
        logger.error(f"❌ User {user.id} tried to edit unknown template: {template_name}")
        session.update_state(UserState.IDLE)
        if hasattr(session, 'editing_template_name'):
            delattr(session, 'editing_template_name')
        await message.reply_text("❌ שגיאה: תבנית לא ידועה. המצב אופס.")
        return
    
    logger.info(f"✏️ User {user.id} editing template: {template_name}")
    
    # קבלת הטקסט החדש (שומרים את כל הטקסט, כולל שורות ריקות)
    new_template = message.text
    
    # בדיקה שהטקסט לא ריק
    if not new_template or not new_template.strip():
        await message.reply_text(
            "⚠️ **הטקסט ריק!**\n\n"
            "אנא שלח תבנית תקינה.\n\n"
            "לבטול: לחץ על ❌ ביטול בתפריט"
        )
        return
    
    # הודעת טעינה
    loading_msg = await message.reply_text("💾 **שומר תבנית...**")
    
    # שמירת התבנית החדשה
    try:
        template_manager.set(template_name, new_template)
        logger.info(f"✅ Template '{template_name}' saved successfully")
    except Exception as e:
        logger.error(f"❌ Error saving template '{template_name}': {e}", exc_info=True)
        await loading_msg.edit_text(f"❌ **שגיאה בשמירת התבנית:**\n\n{str(e)}")
        return
    
    # איפוס מצב
    session.update_state(UserState.IDLE)
    if hasattr(session, 'editing_template_name'):
        delattr(session, 'editing_template_name')
    
    template_display_name = TEMPLATE_NAMES[template_name]
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ערוך תבנית נוספת", callback_data="templates")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    # בדיקה אם זה תבנית אינסטגרם
    if template_name in ["telegram_instagram", "whatsapp_instagram"]:
        # דוגמה לרינדור עם משתנה {text} בלבד
        example_vars = {
            "text": "זהו טקסט לדוגמה שהמשתמש ישלח"
        }
        
        # ניסיון לרנדר התבנית
        try:
            rendered = template_manager.render(template_name, **example_vars)
        except Exception as e:
            logger.warning(f"⚠️ Error rendering template preview: {e}")
            rendered = f"⚠️ שגיאה ברינדור התבנית: {str(e)}"
        
        # הצגת התוצאה
        response_text = (
            f"✅ **התבנית '{template_display_name}' עודכנה בהצלחה!**\n\n"
            f"**תבנית חדשה:**\n"
            f"```\n{new_template}\n```\n\n"
            f"**דוגמה לתוצאה (עם טקסט לדוגמה):**\n"
            f"{rendered}\n\n"
            f"💡 **הערה:** המשתנה `{{text}}` יוחלף בטקסט שהמשתמש ישלח בעת העלאה מאינסטגרם."
        )
    else:
        # דוגמה לרינדור עם משתנים אמיתיים (לתבניות רגילות)
        example_vars = {
            "song_name": "שיר לדוגמה",
            "artist_name": "זמר לדוגמה",
            "year": "2024",
            "composer": "מלחין לדוגמה",
            "arranger": "מעבד לדוגמה",
            "mixer": "מיקס לדוגמה",
            "credits": "🎵 שיר לדוגמה\n🎤 זמר לדוגמה\n📅 2024\n✍️ מלחין: מלחין לדוגמה\n🎼 מעבד: מעבד לדוגמה\n🎚️ מיקס: מיקס לדוגמה",
            "youtube_url": "https://youtube.com/watch?v=example"
        }
        
        # ניסיון לרנדר התבנית
        try:
            rendered = template_manager.render(template_name, **example_vars)
        except Exception as e:
            logger.warning(f"⚠️ Error rendering template preview: {e}")
            rendered = f"⚠️ שגיאה ברינדור התבנית: {str(e)}"
        
        # הצגת התוצאה
        response_text = (
            f"✅ **התבנית '{template_display_name}' עודכנה בהצלחה!**\n\n"
            f"**תבנית חדשה:**\n"
            f"```\n{new_template}\n```\n\n"
            f"**דוגמה לתוצאה:**\n"
            f"{rendered}"
        )
    
    await loading_msg.edit_text(response_text, reply_markup=keyboard)
    logger.info(f"✅ Template edit completed for user {user.id}")


@Client.on_callback_query(filters.regex("^cancel_edit$"))
@rate_limit(max_requests=50, window=60)
async def cancel_template_edit(client: Client, query: CallbackQuery):
    """ביטול עריכת תבנית - legacy handler, לא בשימוש יותר (השתמש ב-template_view)"""
    session = state_manager.get_session(query.from_user.id)
    if hasattr(session, 'editing_template_name'):
        template_name = session.editing_template_name
        session.update_state(UserState.IDLE)
        delattr(session, 'editing_template_name')
        # חזרה לתצוגת התבנית במקום ביטול
        fake_query = type('FakeQuery', (), {
            'data': f"template_view_{template_name}",
            'from_user': query.from_user,
            'message': query.message,
            'answer': query.answer
        })()
        await template_view_menu(client, fake_query)
        await query.answer()
        return
    
    session.update_state(UserState.IDLE)
    await query.message.edit_text("❌ העריכה בוטלה")
    await query.answer()


@Client.on_callback_query(filters.regex("^reset_templates$"))
@rate_limit(max_requests=50, window=60)
async def reset_templates_confirm(client: Client, query: CallbackQuery):
    """אישור איפוס תבניות"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ כן, אפס", callback_data="confirm_reset")],
        [InlineKeyboardButton("❌ ביטול", callback_data="back_to_settings")]
    ])
    
    await query.message.edit_text(
        "⚠️ **אתה בטוח?**\n\n"
        "פעולה זו תאפס את כל התבניות לברירות המחדל.",
        reply_markup=keyboard
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^confirm_reset$"))
@rate_limit(max_requests=50, window=60)
async def reset_templates(client: Client, query: CallbackQuery):
    """איפוס תבניות לברירות מחדל"""
    template_manager.reset_to_defaults()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ערוך תבניות", callback_data="templates")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    await query.message.edit_text(
        "✅ **התבניות אופסו לברירות מחדל**",
        reply_markup=keyboard
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^update_cookies$"))
@rate_limit(max_requests=50, window=60)
async def update_cookies_menu(client: Client, query: CallbackQuery):
    """תפריט עדכון cookies"""
    cookies_path = ROOT_DIR / "cookies.txt"
    cookies_exists = cookies_path.exists()
    
    help_text = (
        "🍪 **עדכון קובץ Cookies**\n\n"
        "קובץ cookies משמש להורדות מ-YouTube.\n\n"
        "**הוראות:**\n"
        "1. הורד את קובץ ה-cookies שלך מהדפדפן\n"
        "2. שלח את הקובץ כאן\n\n"
        "**פורמט:**\n"
        "• Netscape HTTP Cookie File\n"
        "• שם קובץ: `cookies.txt`\n\n"
    )
    
    if cookies_exists:
        file_size = cookies_path.stat().st_size
        help_text += f"**סטטוס:** ✅ קובץ קיים ({file_size} bytes)\n\n"
    else:
        help_text += "**סטטוס:** ⚠️ אין קובץ cookies\n\n"
    
    help_text += "📤 **שלח את קובץ cookies עכשיו:**"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור", callback_data="back_to_settings")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    # עדכון מצב המשתמש
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.UPDATING_COOKIES)
    
    await query.message.edit_text(help_text, reply_markup=keyboard)
    await query.answer()


@Client.on_message(filters.document & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue"]), group=0)
@rate_limit(max_requests=10, window=60)
async def handle_cookies_file(client: Client, message: Message):
    """מטפל בקבלת קובץ cookies"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        return
    
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עדכון cookies
    if session.state != UserState.UPDATING_COOKIES:
        return
    
    try:
        # בדיקה שהקובץ הוא cookies.txt או עם סיומת .txt
        file_name = message.document.file_name if message.document else None
        if not file_name or not file_name.endswith('.txt'):
            await message.reply_text(
                "⚠️ **קובץ לא תקין!**\n\n"
                "אנא שלח קובץ עם סיומת `.txt`\n"
                "שם הקובץ צריך להיות `cookies.txt`"
            )
            return
        
        # הורדת הקובץ
        downloads_dir = ROOT_DIR / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        temp_cookies_path = downloads_dir / f"temp_cookies_{user.id}.txt"
        
        downloaded_path = await message.download(file_name=str(temp_cookies_path))
        
        # עדכון cookies
        cookies_dest = ROOT_DIR / "cookies.txt"
        success = await update_cookies(str(downloaded_path), str(cookies_dest))
        
        # מחיקת קובץ זמני
        try:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except:
            pass
        
        if success:
            session.update_state(UserState.IDLE)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")],
                [InlineKeyboardButton("❌ סגור", callback_data="close")]
            ])
            await message.reply_text(
                "✅ **קובץ cookies עודכן בהצלחה!**\n\n"
                "הקובץ נשמר ונשתמש בו להורדות מ-YouTube.",
                reply_markup=keyboard
            )
            logger.info(f"✅ User {user.id} updated cookies file")
        else:
            await message.reply_text(
                "❌ **שגיאה בעדכון cookies!**\n\n"
                "הקובץ לא תקין או יש בעיה בשמירה.\n"
                "נסה שוב או שלח /cancel לביטול"
            )
    
    except Exception as e:
        logger.error(f"❌ Error handling cookies file: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בעיבוד הקובץ\n"
            "נסה שוב או שלח /cancel לביטול"
        )


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


# ========== ניהול ערוצים/קבוצות ==========

@Client.on_callback_query(filters.regex("^add_channels$"))
@rate_limit(max_requests=50, window=60)
async def add_channels_menu(client: Client, query: CallbackQuery):
    """תפריט הוספת ערוצים/קבוצות"""
    logger.info(f"📋 User {query.from_user.id} opened add channels menu")
    
    # קבלת רשימת ערוצים/קבוצות קיימים
    telegram_channels = channels_manager.get_repository("telegram")
    whatsapp_groups = channels_manager.get_repository("whatsapp")
    logger.debug(f"📊 Repository: {len(telegram_channels)} Telegram, {len(whatsapp_groups)} WhatsApp")
    
    keyboard = [
        [InlineKeyboardButton("📱 טלגרם", callback_data="add_channel_telegram")],
        [InlineKeyboardButton("💬 וואטסאפ", callback_data="add_channel_whatsapp")],
    ]
    
    # הוספת כפתורים לערוצים/קבוצות קיימים (להסרה)
    if telegram_channels:
        keyboard.append([InlineKeyboardButton("📋 ניהול ערוצי טלגרם", callback_data="manage_channels_telegram")])
    if whatsapp_groups:
        keyboard.append([InlineKeyboardButton("📋 ניהול קבוצות וואטסאפ", callback_data="manage_channels_whatsapp")])
    
    keyboard.append([InlineKeyboardButton("🔙 חזור", callback_data="back_to_settings")])
    
    text = "➕ **הוספת ערוצים/קבוצות**\n\n"
    text += f"**ערוצי טלגרם במאגר:** {len(telegram_channels)}\n"
    if telegram_channels:
        # קבלת שמות ערוצים
        channel_names = []
        for ch_id in telegram_channels[:5]:
            try:
                display_name = await get_channel_display_name(client, "telegram", ch_id)
                if len(display_name) > 30:
                    display_name = display_name[:30] + "..."
                channel_names.append(f"`{display_name}`")
            except Exception as e:
                logger.debug(f"⚠️ Could not get channel name for {ch_id}: {e}")
                display_name = ch_id[:30] + "..." if len(ch_id) > 30 else ch_id
                channel_names.append(f"`{display_name}`")
        text += "ערוצים: " + ", ".join(channel_names)
        if len(telegram_channels) > 5:
            text += f" +{len(telegram_channels) - 5} נוספים"
        text += "\n"
    text += f"\n**קבוצות וואטסאפ במאגר:** {len(whatsapp_groups)}\n"
    if whatsapp_groups:
        # WhatsApp - נשאר עם השם המקורי (כי זה כבר שם הקבוצה)
        text += "קבוצות: " + ", ".join([f"`{g[:30]}`" for g in whatsapp_groups[:5]])
        if len(whatsapp_groups) > 5:
            text += f" +{len(whatsapp_groups) - 5} נוספים"
        text += "\n"
    text += "\nבחר פעולה:"
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()
    logger.debug(f"✅ Add channels menu displayed to user {query.from_user.id}")


@Client.on_callback_query(filters.regex("^add_channel_(telegram|whatsapp)$"))
async def add_channel_prompt(client: Client, query: CallbackQuery):
    """הנחיה להוספת ערוץ/קבוצה"""
    platform = query.data.replace("add_channel_", "")
    logger.info(f"➕ User {query.from_user.id} starting to add {platform} channel/group")
    
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.ADDING_CHANNEL)
    session.adding_channel_platform = platform
    logger.debug(f"📝 User {query.from_user.id} state changed to ADDING_CHANNEL for {platform}")
    
    if platform == "telegram":
        help_text = (
            "📱 **הוספת ערוץ טלגרם**\n\n"
            "שלח את קישור הערוץ או ID שלו.\n\n"
            "**דוגמאות:**\n"
            "• `@channel_name`\n"
            "• `-1001234567890`\n"
            "• `https://t.me/channel_name`\n\n"
            "📤 **שלח את הקישור/ID עכשיו:**"
        )
    else:  # whatsapp
        help_text = (
            "💬 **הוספת קבוצת וואטסאפ**\n\n"
            "שלח את שם הקבוצה בדיוק כפי שהוא מופיע בוואטסאפ.\n\n"
            "**חשוב:**\n"
            "• שם הקבוצה חייב להתאים בדיוק\n"
            "• כולל אימוג'ים, מספרים ורווחים\n\n"
            "📤 **שלח את שם הקבוצה עכשיו:**"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור", callback_data="add_channels")]
    ])
    
    await query.message.edit_text(help_text, reply_markup=keyboard)
    await query.answer()


@Client.on_callback_query(filters.regex("^cancel_add_channel$"))
async def cancel_add_channel(client: Client, query: CallbackQuery):
    """ביטול הוספת ערוץ/קבוצה (legacy - לא בשימוש יותר, חזור משתמש ב-add_channels)"""
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.IDLE)
    if hasattr(session, 'adding_channel_platform'):
        delattr(session, 'adding_channel_platform')
    
    # חזרה לתפריט הוספת ערוצים/קבוצות
    await add_channels_menu(client, query)


@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test"]), group=-2)
@rate_limit(max_requests=50, window=60)
async def handle_add_channel(client: Client, message: Message):
    """מטפל בהוספת ערוץ/קבוצה - group=-2 נותן עדיפות גבוהה מאוד (לפני handle_template_edit)"""
    user = message.from_user
    logger.info(f"🔍 [ADD_CHANNEL] Handler triggered for user {user.id}, text: {message.text[:50]}")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.debug(f"⛔ User {user.id} not authorized, skipping")
        return
    
    session = state_manager.get_session(user.id)
    logger.info(f"📊 [ADD_CHANNEL] User {user.id} state: {session.state}")
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping add channel handler")
        return
    
    # בדיקה אם המשתמש במצב הוספת ערוץ/קבוצה
    if session.state != UserState.ADDING_CHANNEL:
        logger.debug(f"ℹ️ User {user.id} not in ADDING_CHANNEL state (current: {session.state}), skipping")
        return
    
    logger.info(f"✅ [ADD_CHANNEL] User {user.id} is in ADDING_CHANNEL state, processing...")
    
    if not hasattr(session, 'adding_channel_platform'):
        logger.warning(f"⚠️ User {user.id} in ADDING_CHANNEL state but no platform attribute")
        session.update_state(UserState.IDLE)
        await message.reply_text("❌ שגיאה: לא נמצאה פלטפורמה. המצב אופס.")
        return
    
    platform = session.adding_channel_platform
    channel_id = message.text.strip()
    logger.info(f"➕ User {user.id} adding {platform} channel/group: {channel_id[:50]}")
    
    # תגובה מיידית למשתמש
    processing_msg = await message.reply_text("⏳ **מעבד...**")
    
    try:
        # ניקוי קישור טלגרם אם צריך
        original_channel_id = channel_id
        if platform == "telegram":
            # הסרת https://t.me/ או @
            channel_id = channel_id.replace("https://t.me/", "").replace("@", "").strip()
            logger.debug(f"🧹 Cleaned Telegram channel ID: {original_channel_id} → {channel_id}")
        
        # בדיקה שהקלט לא ריק
        if not channel_id or not channel_id.strip():
            await processing_msg.edit_text(
                "⚠️ **הקלט ריק!**\n\n"
                "אנא שלח קישור, ID או שם ערוץ/קבוצה תקין.\n\n"
                "לבטול: שלח /cancel"
            )
            return
        
        # הוספה למאגר
        logger.debug(f"💾 Adding {platform} channel/group to repository: {channel_id}")
        channels_manager.add_channel(platform, channel_id)
        logger.info(f"✅ Successfully added {platform} channel/group: {channel_id}")
        
        # קבלת שם הערוץ מ-Telegram API (רק לטלגרם)
        channel_display_name = channel_id  # ברירת מחדל
        if platform == "telegram":
            try:
                # ניסיון לקבל את שם הערוץ מ-Telegram API
                chat_id = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
                chat = await client.get_chat(chat_id)
                if chat.title:
                    channel_display_name = chat.title
                    logger.info(f"✅ Got channel title: {channel_display_name}")
                else:
                    logger.warning(f"⚠️ Channel {channel_id} has no title, using ID")
            except Exception as e:
                logger.warning(f"⚠️ Could not get channel name for {channel_id}: {e}")
                # אם נכשל, נשתמש ב-ID/קישור המקורי
                channel_display_name = channel_id
        
        # איפוס מצב
        session.update_state(UserState.IDLE)
        if hasattr(session, 'adding_channel_platform'):
            delattr(session, 'adding_channel_platform')
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף עוד", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")]
        ])
        
        platform_name = "טלגרם" if platform == "telegram" else "וואטסאפ"
        await processing_msg.edit_text(
            f"✅ **ערוץ/קבוצה נוסף בהצלחה!**\n\n"
            f"**פלטפורמה:** {platform_name}\n"
            f"**שם:** {channel_display_name}\n\n"
            f"💾 **נשמר במאגר**\n\n"
            f"כעת תוכל לקשר אותו לתבניות דרך תפריט עריכת תבניות.",
            reply_markup=keyboard
        )
        logger.info(f"✅ User {user.id} added {platform} channel/group: {channel_display_name} ({channel_id})")
        
    except Exception as e:
        logger.error(f"❌ Error adding channel: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(
                f"❌ **שגיאה בהוספת ערוץ/קבוצה**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )
        except:
            await message.reply_text(
                f"❌ **שגיאה בהוספת ערוץ/קבוצה**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )


async def get_channel_display_name(client: Client, platform: str, channel_id: str) -> str:
    """
    מחזיר שם תצוגה לערוץ/קבוצה - שם הערוץ אם אפשר, אחרת ID/קישור
    
    Args:
        client: Pyrogram Client
        platform: 'telegram' או 'whatsapp'
        channel_id: מזהה הערוץ/קבוצה
    
    Returns:
        שם תצוגה (שם הערוץ או ID/קישור)
    """
    if platform == "telegram":
        try:
            # ניסיון לקבל את שם הערוץ מ-Telegram API
            chat_id = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
            chat = await client.get_chat(chat_id)
            # החזרת שם הערוץ (title) אם קיים
            if chat.title:
                return chat.title
        except Exception as e:
            logger.debug(f"⚠️ Could not get channel name for {channel_id}: {e}")
            # אם נכשל, נחזיר את ה-ID/קישור המקורי
            pass
    
    # אם זה WhatsApp או שנכשל לקבל שם, נחזיר את ה-ID/קישור המקורי
    return channel_id


@Client.on_callback_query(filters.regex("^edit_channels_(.+)$"))
async def edit_template_channels(client: Client, query: CallbackQuery):
    """תפריט עריכת ערוצים/קבוצות לתבנית"""
    template_name = query.data.replace("edit_channels_", "")
    logger.info(f"📢 User {query.from_user.id} editing channels for template: {template_name}")
    
    if template_name not in TEMPLATE_NAMES:
        logger.warning(f"❌ User {query.from_user.id} tried to edit channels for unknown template: {template_name}")
        await query.answer("❌ תבנית לא קיימת", show_alert=True)
        return
    
    platform = channels_manager.get_template_platform(template_name)
    template_display_name = TEMPLATE_NAMES[template_name]
    logger.debug(f"📊 Template {template_name} platform: {platform}")
    
    # קבלת כל הערוצים/קבוצות במאגר לפלטפורמה הזו
    repository = channels_manager.get_repository(platform)
    logger.debug(f"📋 Repository for {platform}: {len(repository)} items")
    
    if not repository:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף ערוצים/קבוצות", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור", callback_data=f"template_view_{template_name}")]
        ])
        await query.message.edit_text(
            f"📢 **עריכת ערוצים/קבוצות - {template_display_name}**\n\n"
            f"אין ערוצים/קבוצות במאגר עבור {platform}.\n"
            f"הוסף ערוצים/קבוצות תחילה.",
            reply_markup=keyboard
        )
        await query.answer()
        return
    
    # קבלת סטטוס כל הערוצים/קבוצות
    channels_status = channels_manager.get_all_template_channels_status(template_name, platform)
    logger.debug(f"📊 Channels status: {channels_status}")
    
    # בניית כפתורים - כל ערוץ/קבוצה עם X או V
    # שימוש ב-index במקום channel_id מלא כדי להימנע מ-callback_data גדול מדי
    buttons = []
    for index, channel_id in enumerate(repository):
        is_active = channels_status.get(channel_id, False)
        # קבלת שם תצוגה - שם הערוץ אם אפשר, אחרת ID/קישור
        display_name = await get_channel_display_name(client, platform, channel_id)
        # קיצור שם אם ארוך מדי
        if len(display_name) > 25:
            display_name = display_name[:25] + "..."
        button_text = f"{'✅' if is_active else '❌'} {display_name}"
        # שימוש ב-index במקום channel_id מלא (מוגבל ל-64 בתים)
        # קיצור template_name אם ארוך מדי
        short_template = template_name[:15] if len(template_name) > 15 else template_name
        callback_data = f"tg_{short_template}_{platform[0]}_{index}"  # platform[0] = 't' או 'w'
        # בדיקה שאורך callback_data לא עולה על 64 בתים
        callback_bytes = len(callback_data.encode('utf-8'))
        if callback_bytes > 64:
            logger.error(f"❌ Callback data too long: {callback_bytes} bytes")
            # קיצור נוסף
            short_template = template_name[:10] if len(template_name) > 10 else template_name
            callback_data = f"tg_{short_template}_{platform[0]}_{index}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton("🔙 חזור", callback_data=f"template_view_{template_name}")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    active_count = sum(1 for status in channels_status.values() if status)
    
    try:
        await query.message.edit_text(
            f"📢 **עריכת ערוצים/קבוצות - {template_display_name}**\n\n"
            f"**פעילים:** {active_count}/{len(repository)}\n\n"
            f"לחץ על ערוץ/קבוצה כדי להפעיל/לכבות:",
            reply_markup=keyboard
        )
        await query.answer()
    except Exception as e:
        logger.error(f"❌ Error displaying edit channels menu: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בתצוגת התפריט", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^tg_(.+)_(t|w)_([0-9]+)$"))
async def toggle_template_channel(client: Client, query: CallbackQuery):
    """החלפת סטטוס ערוץ/קבוצה עבור תבנית"""
    logger.info(f"🔄 User {query.from_user.id} toggling channel status")
    logger.debug(f"📊 Callback data: {query.data}")
    
    try:
        import re
        # הפורמט החדש: tg_{template_name}_{platform_letter}_{index}
        # דוגמה: tg_telegram_image_t_0 (t = telegram, w = whatsapp)
        match = re.match(r"^tg_(.+)_(t|w)_([0-9]+)$", query.data)
        if not match:
            raise ValueError(f"Invalid callback data format: {query.data}")
        
        short_template = match.group(1)
        platform_letter = match.group(2)
        index = int(match.group(3))
        
        # המרת platform_letter ל-platform מלא
        platform = "telegram" if platform_letter == "t" else "whatsapp"
        
        # מציאת template_name המלא - חיפוש לפי התחלה
        template_name = None
        for full_name in TEMPLATE_NAMES.keys():
            if full_name.startswith(short_template):
                template_name = full_name
                break
        
        if not template_name:
            # ניסיון נוסף - אולי short_template הוא שם מלא
            if short_template in TEMPLATE_NAMES:
                template_name = short_template
            else:
                logger.warning(f"❌ Could not find template matching: {short_template}")
                await query.answer("❌ תבנית לא נמצאה", show_alert=True)
                return
        
        logger.debug(f"📊 Parsed: short_template={short_template}, template={template_name}, platform={platform}, index={index}")
        
        # קבלת channel_id מה-index
        repository = channels_manager.get_repository(platform)
        if index >= len(repository):
            logger.error(f"❌ Index {index} out of range for {platform} repository (length: {len(repository)})")
            await query.answer("❌ שגיאה: ערוץ/קבוצה לא נמצא", show_alert=True)
            return
        
        channel_id = repository[index]
        logger.debug(f"📊 Channel ID from index {index}: {channel_id[:50]}")
        
        # החלפת סטטוס
        current_status = channels_manager.is_template_channel_active(template_name, platform, channel_id)
        new_status = not current_status
        logger.info(f"🔄 Toggling {platform} channel/group '{channel_id[:50]}' for template '{template_name}': {current_status} → {new_status}")
        
        channels_manager.set_template_channel_active(template_name, platform, channel_id, new_status)
        logger.info(f"✅ Successfully toggled channel status to {new_status}")
        
        # רענון התפריט - קריאה ישירה ל-edit_template_channels עם query מזויף
        class FakeQuery:
            def __init__(self, original_query, new_data):
                self.data = new_data
                self.from_user = original_query.from_user
                self.message = original_query.message
                self.answer = original_query.answer
        
        fake_query = FakeQuery(query, f"edit_channels_{template_name}")
        
        try:
            await edit_template_channels(client, fake_query)
            await query.answer(f"{'✅ הופעל' if new_status else '❌ בוטל'}")
        except Exception as e:
            logger.error(f"❌ Error refreshing menu after toggle: {e}", exc_info=True)
            await query.answer(f"{'✅ הופעל' if new_status else '❌ בוטל'} (תפריט לא עודכן)", show_alert=False)
        
    except Exception as e:
        logger.error(f"❌ Error toggling channel: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בהחלפת סטטוס", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^manage_channels_(telegram|whatsapp)$"))
async def manage_channels_menu(client: Client, query: CallbackQuery):
    """תפריט ניהול ערוצים/קבוצות במאגר"""
    platform = query.data.replace("manage_channels_", "")
    repository = channels_manager.get_repository(platform)
    
    if not repository:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף ערוצים/קבוצות", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור", callback_data="add_channels")]
        ])
        platform_name = "טלגרם" if platform == "telegram" else "וואטסאפ"
        await query.message.edit_text(
            f"📋 **ניהול ערוצים/קבוצות - {platform_name}**\n\n"
            f"אין ערוצים/קבוצות במאגר.",
            reply_markup=keyboard
        )
        await query.answer()
        return
    
    # בניית כפתורים - כל ערוץ/קבוצה עם כפתור הסרה
    # שימוש ב-index במקום channel_id מלא כדי להימנע מ-callback_data גדול מדי
    buttons = []
    for index, channel_id in enumerate(repository):
        # קבלת שם תצוגה - שם הערוץ אם אפשר, אחרת ID/קישור
        display_name = await get_channel_display_name(client, platform, channel_id)
        # קיצור שם אם ארוך מדי
        if len(display_name) > 40:
            display_name = display_name[:40] + "..."
        button_text = f"🗑️ {display_name}"
        # שימוש ב-index במקום channel_id מלא
        callback_data = f"remove_{platform}_{index}"
        # בדיקה שאורך callback_data לא עולה על 64 בתים
        if len(callback_data.encode('utf-8')) > 64:
            logger.error(f"❌ Callback data too long: {len(callback_data.encode('utf-8'))} bytes")
            callback_data = f"rm_{platform}_{index}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton("🔙 חזור", callback_data="add_channels")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    platform_name = "טלגרם" if platform == "telegram" else "וואטסאפ"
    
    try:
        await query.message.edit_text(
            f"📋 **ניהול ערוצים/קבוצות - {platform_name}**\n\n"
            f"**סה\"כ:** {len(repository)}\n\n"
            f"לחץ על ערוץ/קבוצה להסרה מהמאגר:",
            reply_markup=keyboard
        )
        await query.answer()
    except Exception as e:
        logger.error(f"❌ Error displaying manage channels menu: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בתצוגת התפריט", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^remove_(telegram|whatsapp)_([0-9]+)$"))
async def remove_channel(client: Client, query: CallbackQuery):
    """הסרת ערוץ/קבוצה מהמאגר"""
    try:
        import re
        # הפורמט: remove_{platform}_{index}
        match = re.match(r"^remove_(telegram|whatsapp)_([0-9]+)$", query.data)
        if not match:
            raise ValueError(f"Invalid callback data format: {query.data}")
        
        platform = match.group(1)
        index = int(match.group(2))
        
        logger.debug(f"📊 Parsed: platform={platform}, index={index}")
        
        # קבלת channel_id מה-index
        repository = channels_manager.get_repository(platform)
        if index >= len(repository):
            logger.error(f"❌ Index {index} out of range for {platform} repository (length: {len(repository)})")
            await query.answer("❌ שגיאה: ערוץ/קבוצה לא נמצא", show_alert=True)
            return
        
        channel_id = repository[index]
        logger.info(f"🗑️ Removing {platform} channel/group: {channel_id[:50]}")
        
        channels_manager.remove_channel(platform, channel_id)
        logger.info(f"✅ Removed {platform} channel/group: {channel_id[:50]}")
        
        # רענון התפריט - יצירת query מזויף
        class FakeQuery:
            def __init__(self, original_query, new_data):
                self.data = new_data
                self.from_user = original_query.from_user
                self.message = original_query.message
                self.answer = original_query.answer
        
        fake_query = FakeQuery(query, f"manage_channels_{platform}")
        
        try:
            await manage_channels_menu(client, fake_query)
            await query.answer(f"✅ הוסר: {channel_id[:30]}")
        except Exception as e:
            logger.error(f"❌ Error refreshing menu after remove: {e}", exc_info=True)
            await query.answer(f"✅ הוסר: {channel_id[:30]} (תפריט לא עודכן)", show_alert=False)
        
    except Exception as e:
        logger.error(f"❌ Error removing channel: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בהסרת ערוץ/קבוצה", show_alert=True)
        except:
            pass


# הוספת מצב חדש ל-UserState
# צריך לעדכן את services/user_states.py
# בינתיים נשתמש ב-state קיים או נוסיף בדיקה

logger.info("✅ Settings plugin loaded")
