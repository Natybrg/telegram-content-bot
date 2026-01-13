"""
Template Management Plugin
Handlers for viewing, editing, and managing content templates
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.templates import template_manager
from services.user_states import state_manager, UserState
from services.channels import channels_manager
from services.rate_limiter import rate_limit
from core import is_authorized_user
import logging

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


logger.info("✅ Templates handlers loaded")
