"""
Start Command Plugin
Handles /start command for the bot
"""
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import config
from config import is_authorized_user

logger = logging.getLogger(__name__)


# מקלדת קבועה עם כפתורי הגדרות וביטול
def get_main_keyboard():
    """מחזיר את המקלדת הקבועה עם כפתורי הגדרות וביטול"""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("⚙️ הגדרות"), KeyboardButton("❌ ביטול")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """
    Handles the /start command - רק למשתמשים מורשים
    """
    user = message.from_user
    logger.info(f"👤 User {user.id} (@{user.username}) tried to start the bot")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized access attempt by user {user.id}")
        # משתמש לא מורשה - לא מקבל תשובה
        return
    
    logger.info(f"✅ Authorized user {user.id} started the bot")
    
    # ניקוי קבצים ישנים אם יש
    from services.user_states import state_manager, UserState
    from plugins.content_creator import cleanup_session_files
    
    session = state_manager.get_session(user.id)
    if session.state != UserState.IDLE:
        # יש תהליך פעיל - מנקים קבצים
        await cleanup_session_files(session)
        state_manager.reset_session(user.id)
        logger.info(f"🧹 Cleaned up old files for user {user.id} on /start")
    
    welcome_text = (
        f"👋 שלום {user.first_name}!\n\n"
        f"🎵 **ברוך הבא לבוט יצירת תוכן מוזיקלי**\n\n"
        f"📝 **תהליך העבודה:**\n"
        f"1️⃣ שלח תמונה (עטיפת אלבום)\n"
        f"2️⃣ שלח קובץ MP3\n"
        f"3️⃣ שלח 8 שורות פרטים:\n"
        f"   • שם שיר\n"
        f"   • שם זמר\n"
        f"   • שנה\n"
        f"   • שם מלחין\n"
        f"   • שם מעבד\n"
        f"   • שם מיקס\n"
        f"   • קישור ליוטיוב\n"
        f"   • כן/לא (האם צריך גם וידאו)\n\n"
        f"⚡ הבוט יטפל בכל השאר אוטומטית!\n\n"
        f"💡 להתחלה - פשוט שלח תמונה"
    )
    
    await message.reply_text(welcome_text, reply_markup=get_main_keyboard())


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """
    Handles the /help command - רק למשתמשים מורשים
    """
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized help request by user {user.id}")
        return
    
    help_text = (
        "📚 **עזרה - בוט יצירת תוכן מוזיקלי**\n\n"
        "🎯 **תהליך העבודה:**\n\n"
        "**שלב 1 - תמונה:**\n"
        "שלח תמונת עטיפה לאלבום/שיר\n\n"
        "**שלב 2 - MP3:**\n"
        "שלח את קובץ ה-MP3 המקורי\n\n"
        "**שלב 3 - פרטים:**\n"
        "שלח הודעה עם 8 שורות (כל פרט בשורה נפרדת):\n"
        "1. שם השיר\n"
        "2. שם הזמר\n"
        "3. שנה\n"
        "4. שם המלחין\n"
        "5. שם המעבד\n"
        "6. שם המיקס\n"
        "7. קישור ליוטיוב\n"
        "8. כן/לא (האם להוריד וידאו)\n\n"
        "✨ **הבוט יבצע:**\n"
        "• הוספת הקרדיטים על התמונה\n"
        "• עדכון תגיות ה-MP3 + תמונה\n"
        "• הורדת וידאו מיוטיוב (אם צריך)\n"
        "• העלאת הכל אליך\n\n"
        "⏳ **ניהול תור:**\n"
        "• **/queue_status** - בדיקת מצב התור\n"
        "• **/cancel_queue** - ביטול מקום בתור\n\n"
        "🔧 **פקודות נוספות:**\n"
        "• **/settings** - הגדרות ועריכת תבניות\n"
        "• **/cancel** - ביטול תהליך נוכחי\n"
        "• **/status** - סטטוס הבוט"
    )
    
    await message.reply_text(help_text, reply_markup=get_main_keyboard())


@Client.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    """
    Handles the /status command - רק למשתמשים מורשים
    """
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized status request by user {user.id}")
        return
    
    status_text = (
        "✅ **סטטוס הבוט:**\n\n"
        f"🤖 Bot: פעיל\n"
        f"👤 Userbot: פעיל\n"
        f"📁 תיקיית הורדות: {config.DOWNLOADS_PATH}\n"
        f"📊 גודל קובץ מקסימלי: {config.MAX_FILE_SIZE_MB}MB\n\n"
        f"✅ הכל עובד תקין!"
    )
    
    await message.reply_text(status_text, reply_markup=get_main_keyboard())


@Client.on_message(filters.command("test") & filters.private)
async def test_command(client: Client, message: Message):
    """
    Handles the /test command - שולח הודעה לכל הערוצים/קבוצות הפעילים
    """
    user = message.from_user
    logger.info(f"🧪 User {user.id} (@{user.username}) triggered /test command")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized access attempt by user {user.id}")
        return
    
    try:
        from services.context import get_context
        from services.channels import channels_manager
        from pyrogram.errors import PeerIdInvalid
        
        # קבלת userbot
        context = get_context()
        userbot = context.get_userbot()
        
        if not userbot:
            await message.reply_text(
                "❌ **Userbot לא זמין!**\n\n"
                "אין אפשרות לשלוח הודעות לערוצים/קבוצות.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # הודעה ראשונית
        status_msg = await message.reply_text("⏳ **בודק ערוצים וקבוצות...**")
        
        # איסוף כל הערוצים/קבוצות הפעילים
        all_channels = []
        all_groups = []
        
        # ערוצי טלגרם פעילים
        templates_telegram = ["telegram_image", "telegram_video", "telegram_instagram"]
        for template in templates_telegram:
            channels = channels_manager.get_template_channels(template, "telegram")
            if channels:
                for ch in channels:
                    if ch not in all_channels:
                        all_channels.append(ch)
        
        # קבוצות וואטסאפ פעילות
        templates_whatsapp = ["whatsapp_image", "whatsapp_video", "whatsapp_instagram", "whatsapp_audio"]
        for template in templates_whatsapp:
            groups = channels_manager.get_template_channels(template, "whatsapp")
            if groups:
                for grp in groups:
                    if grp not in all_groups:
                        all_groups.append(grp)
        
        if not all_channels and not all_groups:
            await status_msg.edit_text(
                "ℹ️ **אין ערוצים/קבוצות פעילים!**\n\n"
                "הוסף ערוצים/קבוצות דרך ההגדרות וקשר אותם לתבניות.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # סטטיסטיקה
        total = len(all_channels) + len(all_groups)
        success_telegram = []
        failed_telegram = []
        success_whatsapp = []
        failed_whatsapp = []
        
        # שליחה לערוצי טלגרם
        if all_channels:
            await status_msg.edit_text(f"📤 **שולח הודעות ל-{len(all_channels)} ערוצי טלגרם...**")
            
            test_message = "🧪 **בדיקת ערוץ/קבוצה**\n\n" \
                          "אם אתה רואה את ההודעה הזו, הערוץ/הקבוצה פעיל ומוכן לקבל הודעות!"
            
            for channel_id in all_channels:
                try:
                    logger.info(f"🧪 [TEST] שולח הודעה לערוץ: {channel_id}")
                    
                    # טעינת הערוץ ל-storage לפני שליחה
                    try:
                        chat_obj = await userbot.get_chat(channel_id)
                        logger.info(f"✅ [TEST] ערוץ {channel_id} נטען: {chat_obj.title if hasattr(chat_obj, 'title') else 'N/A'}")
                    except PeerIdInvalid:
                        logger.error(f"❌ [TEST] ערוץ {channel_id} לא נגיש - PeerIdInvalid")
                        failed_telegram.append(f"{channel_id} (PeerIdInvalid - צריך לשלוח הודעה מה-userbot לערוץ)")
                        continue
                    except Exception as e:
                        logger.error(f"❌ [TEST] שגיאה בטעינת ערוץ {channel_id}: {e}")
                        failed_telegram.append(f"{channel_id} ({str(e)})")
                        continue
                    
                    # שליחת הודעה
                    await userbot.send_message(channel_id, test_message)
                    success_telegram.append(channel_id)
                    logger.info(f"✅ [TEST] הודעה נשלחה בהצלחה לערוץ: {channel_id}")
                    
                except Exception as e:
                    logger.error(f"❌ [TEST] שגיאה בשליחה לערוץ {channel_id}: {e}")
                    failed_telegram.append(f"{channel_id} ({str(e)})")
        
        # שליחה לקבוצות וואטסאפ
        if all_groups:
            await status_msg.edit_text(f"📱 **שולח הודעות ל-{len(all_groups)} קבוצות וואטסאפ...**")
            
            from services.whatsapp import WhatsAppDelivery
            
            whatsapp = WhatsAppDelivery(dry_run=config.WHATSAPP_DRY_RUN)
            try:
                test_message_whatsapp = "🧪 *בדיקת קבוצה*\n\n" \
                                       "אם אתה רואה את ההודעה הזו, הקבוצה פעילה ומוכנה לקבל הודעות!"
                
                for group_name in all_groups:
                    try:
                        logger.info(f"🧪 [TEST] שולח הודעה לקבוצת וואטסאפ: {group_name}")
                        result = whatsapp.send_text(group_name, test_message_whatsapp)
                        
                        if result.get('success'):
                            success_whatsapp.append(group_name)
                            logger.info(f"✅ [TEST] הודעה נשלחה בהצלחה לקבוצה: {group_name}")
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            failed_whatsapp.append(f"{group_name} ({error_msg})")
                            logger.error(f"❌ [TEST] שגיאה בשליחה לקבוצה {group_name}: {error_msg}")
                            
                    except Exception as e:
                        logger.error(f"❌ [TEST] שגיאה בשליחה לקבוצה {group_name}: {e}")
                        failed_whatsapp.append(f"{group_name} ({str(e)})")
            finally:
                whatsapp.close()
        
        # סיכום תוצאות
        total_success = len(success_telegram) + len(success_whatsapp)
        total_failed = len(failed_telegram) + len(failed_whatsapp)
        
        result_text = f"✅ **תוצאות בדיקה**\n\n"
        result_text += f"📊 **סה\"כ:** {total} ערוצים/קבוצות\n"
        result_text += f"✅ **הצליחו:** {total_success}\n"
        result_text += f"❌ **נכשלו:** {total_failed}\n\n"
        
        if success_telegram:
            result_text += f"📤 **טלגרם - הצליחו ({len(success_telegram)}):**\n"
            for ch in success_telegram:
                result_text += f"  ✅ {ch}\n"
            result_text += "\n"
        
        if failed_telegram:
            result_text += f"❌ **טלגרם - נכשלו ({len(failed_telegram)}):**\n"
            for ch in failed_telegram[:5]:  # רק 5 ראשונים
                result_text += f"  ❌ {ch}\n"
            if len(failed_telegram) > 5:
                result_text += f"  ... ועוד {len(failed_telegram) - 5}\n"
            result_text += "\n"
        
        if success_whatsapp:
            result_text += f"📱 **וואטסאפ - הצליחו ({len(success_whatsapp)}):**\n"
            for grp in success_whatsapp:
                result_text += f"  ✅ {grp}\n"
            result_text += "\n"
        
        if failed_whatsapp:
            result_text += f"❌ **וואטסאפ - נכשלו ({len(failed_whatsapp)}):**\n"
            for grp in failed_whatsapp[:5]:  # רק 5 ראשונים
                result_text += f"  ❌ {grp}\n"
            if len(failed_whatsapp) > 5:
                result_text += f"  ... ועוד {len(failed_whatsapp) - 5}\n"
        
        if failed_telegram:
            result_text += "\n💡 **טיפים לפתרון בעיות טלגרם:**\n"
            result_text += "• שלח הודעה מה-userbot לערוץ כדי לטעון אותו ל-storage\n"
            result_text += "• וודא שה-userbot חבר בערוץ\n"
            result_text += "• וודא שה-userbot בעל הרשאות פרסום בערוץ"
        
        await status_msg.edit_text(result_text, reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"❌ Error in /test command: {e}", exc_info=True)
        await message.reply_text(
            f"❌ **שגיאה בבדיקה!**\n\n"
            f"פרטי שגיאה: {str(e)}",
            reply_markup=get_main_keyboard()
        )


@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client: Client, message: Message):
    """
    ביטול תהליך נוכחי
    """
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        return
    
    from services.user_states import state_manager
    from plugins.content_creator import cleanup_session_files
    
    # ניקוי קבצים לפני איפוס הסשן
    session = state_manager.get_session(user.id)
    await cleanup_session_files(session)
    
    # איפוס הסשן
    state_manager.reset_session(user.id)
    
    await message.reply_text(
        "❌ **התהליך בוטל**\n\n"
        "כל הקבצים נמחקו.\n"
        "אתה יכול להתחיל מחדש על ידי שליחת תמונה",
        reply_markup=get_main_keyboard()
    )
    logger.info(f"🔄 User {user.id} cancelled the process")



