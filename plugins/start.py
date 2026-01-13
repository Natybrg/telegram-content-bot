"""
Start Command Plugin
Handles /start command for the bot
"""
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from core import is_authorized_user, DOWNLOADS_PATH, MAX_FILE_SIZE_MB

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
            f"📁 תיקיית הורדות: {DOWNLOADS_PATH}\n"
            f"📊 גודל קובץ מקסימלי: {MAX_FILE_SIZE_MB}MB\n\n"
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
        from core.context import get_context
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
            
            from core import WHATSAPP_DRY_RUN
            whatsapp = WhatsAppDelivery(dry_run=WHATSAPP_DRY_RUN)
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


@Client.on_message(filters.command("diagnose_channel") & filters.private)
async def diagnose_channel_command(client: Client, message: Message):
    """
    בדיקה מקיפה של ערוץ - מבצע את כל 6 הניסיונות לאבחון בעיות
    שימוש: /diagnose_channel <channel_id או שם ערוץ>
    """
    user = message.from_user
    logger.info(f"🔍 User {user.id} triggered /diagnose_channel command")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized access attempt by user {user.id}")
        return
    
    try:
        from core.context import get_context
        from services.channels import channels_manager
        from pyrogram.errors import PeerIdInvalid, ChatAdminRequired
        from pyrogram.types import ChatType
        
        # קבלת userbot
        context = get_context()
        userbot = context.get_userbot()
        
        if not userbot:
            await message.reply_text(
                "❌ **Userbot לא זמין!**",
                reply_markup=get_main_keyboard()
            )
            return
        
        # קבלת פרמטר (ID או שם ערוץ)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text(
                "📋 **שימוש:** `/diagnose_channel <channel_id או שם ערוץ>`\n\n"
                "**דוגמה:**\n"
                "• `/diagnose_channel -1002332752977`\n"
                "• `/diagnose_channel העלאת קליפים`",
                reply_markup=get_main_keyboard()
            )
            return
        
        channel_input = parts[1].strip()
        
        # ניסיון להמיר ל-ID אם זה מספר
        target_id = None
        if channel_input.lstrip('-').isdigit():
            try:
                target_id = int(channel_input)
            except ValueError:
                pass
        
        # הודעה ראשונית
        status_msg = await message.reply_text("⏳ **מבצע בדיקה מקיפה של הערוץ...**\n\nזה עשוי לקחת כמה שניות...")
        
        results = []
        issues_found = []
        solutions = []
        
        # ========== ניסיון 1: אימות ID מתוך dialogs ==========
        results.append("🔍 **ניסיון 1: אימות ID מתוך dialogs**")
        results.append("=" * 50)
        
        channel_from_dialogs = None
        channels_by_name = []
        
        try:
            async for dialog in userbot.get_dialogs():
                if dialog.chat.type in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
                    chat = dialog.chat
                    
                    # בדיקה לפי שם
                    if chat.title and channel_input.lower() in chat.title.lower():
                        channels_by_name.append({
                            'title': chat.title,
                            'id': chat.id,
                            'type': 'channel' if chat.type == ChatType.CHANNEL else 'supergroup',
                            'username': chat.username if hasattr(chat, 'username') else None,
                            'access_hash': getattr(chat, 'access_hash', None)
                        })
                    
                    # בדיקה לפי ID
                    if str(chat.id) == channel_input or (target_id and chat.id == target_id):
                        channel_from_dialogs = {
                            'title': chat.title,
                            'id': chat.id,
                            'type': 'channel' if chat.type == ChatType.CHANNEL else 'supergroup',
                            'username': chat.username if hasattr(chat, 'username') else None,
                            'access_hash': getattr(chat, 'access_hash', None)
                        }
                        break
            
            if channel_from_dialogs:
                results.append(f"✅ **נמצא ערוץ ב-dialogs:**")
                results.append(f"   • **Title:** {channel_from_dialogs['title']}")
                results.append(f"   • **ID:** `{channel_from_dialogs['id']}`")
                results.append(f"   • **Type:** {channel_from_dialogs['type']}")
                if channel_from_dialogs['username']:
                    results.append(f"   • **Username:** @{channel_from_dialogs['username']}")
                if channel_from_dialogs['access_hash']:
                    results.append(f"   • **Access Hash:** `{channel_from_dialogs['access_hash']}`")
                
                # השוואת ID
                expected_id = int(channel_input) if channel_input.lstrip('-').isdigit() else None
                if expected_id and channel_from_dialogs['id'] != expected_id:
                    issues_found.append(f"❌ **ID לא תואם!**")
                    issues_found.append(f"   • ID שהזנת: `{expected_id}`")
                    issues_found.append(f"   • ID אמיתי: `{channel_from_dialogs['id']}`")
                    solutions.append("💡 **פתרון:** עדכן את ה-ID במאגר הערוצים")
                else:
                    results.append(f"✅ **ID תואם:** `{channel_from_dialogs['id']}`")
            else:
                results.append(f"⚠️ **לא נמצא ערוץ ב-dialogs לפי ID:** `{channel_input}`")
                
                # בדיקה לפי שם
                if channels_by_name:
                    results.append(f"\n📋 **נמצאו {len(channels_by_name)} ערוצים עם שם דומה:**")
                    for ch in channels_by_name:
                        results.append(f"   • **{ch['title']}** - ID: `{ch['id']}` ({ch['type']})")
                    if len(channels_by_name) > 1:
                        issues_found.append("⚠️ **יש יותר מערוץ אחד עם שם דומה!**")
                        solutions.append("💡 **פתרון:** השתמש ב-ID המדויק במקום שם")
        except Exception as e:
            results.append(f"❌ **שגיאה בבדיקת dialogs:** {str(e)}")
            logger.error(f"Error in dialogs check: {e}", exc_info=True)
        
        # ========== ניסיון 2: אימות דרך הודעה אמיתית ==========
        results.append("\n🔍 **ניסיון 2: אימות דרך הודעה אמיתית**")
        results.append("=" * 50)
        
        results.append("💡 **הערה:** נדרש להעביר הודעה אמיתית מהערוץ (לא forwarded)")
        results.append("   שלח הודעה מהערוץ כדי לבצע בדיקה זו")
        
        # ========== ניסיון 3: ניקוי ובנייה מחדש של storage ==========
        results.append("\n🔍 **ניסיון 3: ניקוי ובנייה מחדש של storage**")
        results.append("=" * 50)
        
        if channel_from_dialogs:
            channel_id_str = str(channel_from_dialogs['id'])
            
            # בדיקה אם הערוץ במאגר
            is_in_repo = channels_manager.is_in_repository("telegram", channel_id_str)
            results.append(f"📋 **הערוץ במאגר:** {'כן' if is_in_repo else 'לא'}")
            
            if is_in_repo:
                results.append("🔄 **מסיר מהמאגר...**")
                channels_manager.remove_channel("telegram", channel_id_str)
                results.append("✅ **הוסר מהמאגר**")
            
            # בנייה מחדש מה-entity
            results.append("🔄 **מוסיף מחדש מה-entity...**")
            try:
                # שימוש ב-entity מהדיאלוגים
                chat_obj = await userbot.get_chat(channel_from_dialogs['id'])
                channels_manager.add_channel("telegram", str(chat_obj.id))
                results.append(f"✅ **נוסף מחדש:** ID `{chat_obj.id}`, Title: `{chat_obj.title}`")
            except Exception as e:
                results.append(f"❌ **שגיאה בהוספה מחדש:** {str(e)}")
                issues_found.append(f"❌ **לא ניתן להוסיף מחדש:** {str(e)}")
        else:
            results.append("⚠️ **דילוג - הערוץ לא נמצא ב-dialogs**")
        
        # ========== ניסיון 4: בדיקת התנגשויות שם ==========
        results.append("\n🔍 **ניסיון 4: בדיקת התנגשויות שם**")
        results.append("=" * 50)
        
        if channels_by_name:
            if len(channels_by_name) > 1:
                results.append(f"⚠️ **נמצאו {len(channels_by_name)} ערוצים עם שם דומה:**")
                for i, ch in enumerate(channels_by_name, 1):
                    results.append(f"   {i}. **{ch['title']}** - ID: `{ch['id']}` ({ch['type']})")
                issues_found.append("⚠️ **יש יותר מערוץ אחד עם שם דומה!**")
                solutions.append("💡 **פתרון:** השתמש ב-ID המדויק במקום שם")
            else:
                results.append(f"✅ **רק ערוץ אחד עם השם:** {channels_by_name[0]['title']}")
        else:
            results.append("ℹ️ **לא נמצאו ערוצים עם שם דומה**")
        
        # ========== ניסיון 5: בדיקת שימוש ב-client הנכון ==========
        results.append("\n🔍 **ניסיון 5: בדיקת שימוש ב-client הנכון**")
        results.append("=" * 50)
        
        results.append(f"✅ **משתמש ב-userbot client** (לא bot client)")
        results.append(f"   • Userbot ID: {userbot.me.id if userbot.me else 'N/A'}")
        results.append(f"   • Userbot Username: @{userbot.me.username if userbot.me and userbot.me.username else 'N/A'}")
        
        # ========== ניסיון 6: בדיקת טיפוס peer ==========
        results.append("\n🔍 **ניסיון 6: בדיקת טיפוס peer**")
        results.append("=" * 50)
        
        if channel_from_dialogs:
            try:
                # ניסיון עם object
                chat_obj = await userbot.get_chat(channel_from_dialogs['id'])
                results.append(f"✅ **עובד עם object:**")
                results.append(f"   • ID: `{chat_obj.id}`")
                results.append(f"   • Title: `{chat_obj.title}`")
                results.append(f"   • Type: `{chat_obj.type.name if hasattr(chat_obj.type, 'name') else chat_obj.type}`")
                
                # ניסיון עם ID כשורה
                try:
                    chat_by_id = await userbot.get_chat(int(channel_from_dialogs['id']))
                    results.append(f"✅ **עובד עם ID כשורה:** `{int(channel_from_dialogs['id'])}`")
                except Exception as e:
                    results.append(f"❌ **לא עובד עם ID כשורה:** {str(e)}")
                    issues_found.append(f"❌ **Peer לא נגיש דרך ID:** {str(e)}")
                    solutions.append("💡 **פתרון:** ודא שה-userbot חבר בערוץ ושלח הודעה לערוץ")
                
                # בדיקת access_hash
                if hasattr(chat_obj, 'access_hash') and chat_obj.access_hash:
                    results.append(f"✅ **Access Hash קיים:** `{chat_obj.access_hash}`")
                    results.append("💡 **הערה:** Pyrogram שומר access_hash ב-storage הפנימי שלו")
                else:
                    results.append("⚠️ **Access Hash לא זמין** (ייתכן שזה ערוץ ציבורי)")
            except Exception as e:
                results.append(f"❌ **שגיאה בבדיקת peer:** {str(e)}")
                issues_found.append(f"❌ **Peer לא נגיש:** {str(e)}")
        else:
            results.append("⚠️ **דילוג - הערוץ לא נמצא ב-dialogs**")
        
        # ========== סיכום ==========
        results.append("\n" + "=" * 50)
        results.append("📊 **סיכום**")
        results.append("=" * 50)
        
        if not issues_found:
            results.append("✅ **כל הבדיקות עברו בהצלחה!**")
        else:
            results.append(f"⚠️ **נמצאו {len(issues_found)} בעיות**")
        
        # בניית הודעה סופית
        report = "\n".join(results)
        
        if issues_found:
            report += "\n\n⚠️ **בעיות שנמצאו:**\n"
            report += "\n".join(issues_found)
        
        if solutions:
            report += "\n\n💡 **פתרונות מוצעים:**\n"
            report += "\n".join(solutions)
        
        # הוספת מידע טכני
        report += "\n\n" + "=" * 50
        report += "\n📋 **מידע טכני:**\n"
        report += "   • **Library:** Pyrogram\n"
        report += "   • **Storage:** Pyrogram שומר entities עם access_hash ב-storage הפנימי\n"
        report += "   • **Repository:** שומר רק ID (string) ב-JSON\n"
        if channel_from_dialogs and channel_from_dialogs.get('access_hash'):
            report += f"   • **Access Hash:** `{channel_from_dialogs['access_hash']}`\n"
        
        await status_msg.edit_text(report, reply_markup=get_main_keyboard())
        logger.info(f"✅ [DIAGNOSE_CHANNEL] בדיקה הושלמה עבור user {user.id}, channel: {channel_input}")
        
    except Exception as e:
        logger.error(f"❌ Error in diagnose_channel command: {e}", exc_info=True)
        await message.reply_text(
            f"❌ **שגיאה בבדיקה:**\n\n`{str(e)}`",
            reply_markup=get_main_keyboard()
        )


@Client.on_message(filters.command("test_channel") & filters.private)
async def test_channel_command(client: Client, message: Message):
    """
    בדיקת ערוץ ספציפי - בודק ומנסה לפתור בעיות
    שימוש: /test_channel -1002332752977
    """
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized access attempt by user {user.id}")
        return
    
    try:
        from core.context import get_context
        from pyrogram.errors import PeerIdInvalid, ChannelInvalid, UsernameInvalid, ChatAdminRequired
        
        # קבלת userbot
        context = get_context()
        userbot = context.get_userbot()
        
        if not userbot:
            await message.reply_text(
                "❌ **Userbot לא זמין!**\n\n"
                "אין אפשרות לבדוק ערוצים.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # קבלת ID הערוץ מהפקודה
        command_parts = message.text.split()
        if len(command_parts) < 2:
            await message.reply_text(
                "📋 **שימוש:** `/test_channel <channel_id>`\n\n"
                "**דוגמה:** `/test_channel -1002332752977`\n\n"
                "הפקודה בודקת את הערוץ ומנסה לפתור בעיות.",
                reply_markup=get_main_keyboard()
            )
            return
        
        channel_id = command_parts[1].strip()
        status_msg = await message.reply_text(f"🔍 **בודק ערוץ:** `{channel_id}`\n\n⏳ ממתין...")
        
        results = []
        issues_found = []
        solutions = []
        
        # בדיקה 1: האם הערוץ קיים ונגיש
        results.append("📋 **בדיקה 1:** קיום הערוץ")
        try:
            chat_obj = await userbot.get_chat(channel_id)
            results.append(f"✅ הערוץ קיים: **{chat_obj.title if hasattr(chat_obj, 'title') else 'N/A'}**")
            results.append(f"   - ID: `{chat_obj.id}`")
            results.append(f"   - סוג: {'ערוץ' if chat_obj.type.name == 'CHANNEL' else 'קבוצה'}")
        except PeerIdInvalid:
            issues_found.append("❌ **PeerIdInvalid** - הערוץ לא נטען ל-storage")
            solutions.append("💡 **פתרון:** שלח הודעה מה-userbot לערוץ כדי לטעון אותו ל-storage")
        except ChannelInvalid:
            issues_found.append("❌ **ChannelInvalid** - הערוץ לא קיים או נמחק")
            solutions.append("💡 **פתרון:** בדוק שה-ID נכון והערוץ קיים")
        except UsernameInvalid:
            issues_found.append("❌ **UsernameInvalid** - שם המשתמש לא תקין")
            solutions.append("💡 **פתרון:** בדוק שה-ID או שם המשתמש נכונים")
        except Exception as e:
            issues_found.append(f"❌ **שגיאה:** {str(e)}")
            solutions.append("💡 **פתרון:** בדוק את הלוגים לפרטים נוספים")
        
        # בדיקה 2: האם ה-userbot חבר בערוץ
        results.append("\n📋 **בדיקה 2:** חברות בערוץ")
        try:
            member = await userbot.get_chat_member(channel_id, "me")
            results.append(f"✅ ה-userbot חבר בערוץ")
            results.append(f"   - סטטוס: {member.status.name}")
            if member.status.name in ['ADMINISTRATOR', 'OWNER']:
                results.append(f"   - הרשאות: מנהל/בעלים")
            else:
                issues_found.append("⚠️ **ה-userbot לא מנהל** - ייתכן שאין הרשאות פרסום")
                solutions.append("💡 **פתרון:** הוסף את ה-userbot כמנהל בערוץ עם הרשאות פרסום")
        except Exception as e:
            issues_found.append(f"❌ **לא חבר בערוץ:** {str(e)}")
            solutions.append("💡 **פתרון:** הוסף את ה-userbot לערוץ")
        
        # בדיקה 3: ניסיון לטעון את הערוץ ל-storage
        results.append("\n📋 **בדיקה 3:** טעינה ל-storage")
        try:
            # ניסיון 1: get_chat
            chat_obj = await userbot.get_chat(channel_id)
            results.append("✅ הערוץ נטען ל-storage בהצלחה")
        except PeerIdInvalid:
            results.append("⚠️ הערוץ לא נטען ל-storage - מנסה לפתור...")
            try:
                # ניסיון 2: שליחת הודעה זמנית
                temp_msg = await userbot.send_message(channel_id, "🔧 בדיקה")
                await temp_msg.delete()
                results.append("✅ הערוץ נטען ל-storage על ידי שליחת הודעה")
                solutions.append("✅ **נפתר!** הערוץ נטען ל-storage בהצלחה")
            except ChatAdminRequired:
                issues_found.append("❌ **אין הרשאות פרסום** - ה-userbot לא יכול לפרסם בערוץ")
                solutions.append("💡 **פתרון:** הוסף את ה-userbot כמנהל בערוץ עם הרשאות פרסום")
            except Exception as e:
                issues_found.append(f"❌ **לא ניתן לטעון:** {str(e)}")
                solutions.append("💡 **פתרון:** ודא שה-userbot חבר בערוץ ובעל הרשאות פרסום")
        
        # בדיקה 4: ניסיון לשלוח הודעה
        results.append("\n📋 **בדיקה 4:** שליחת הודעה")
        try:
            test_msg = await userbot.send_message(channel_id, "🧪 **בדיקת ערוץ**\n\nאם אתה רואה את ההודעה הזו, הערוץ פעיל ומוכן!")
            await test_msg.delete()
            results.append("✅ שליחת הודעה הצליחה - הערוץ פעיל")
        except ChatAdminRequired:
            issues_found.append("❌ **אין הרשאות פרסום**")
            solutions.append("💡 **פתרון:** הוסף את ה-userbot כמנהל בערוץ עם הרשאות פרסום")
        except Exception as e:
            issues_found.append(f"❌ **שליחת הודעה נכשלה:** {str(e)}")
            solutions.append("💡 **פתרון:** ודא שה-userbot חבר בערוץ ובעל הרשאות פרסום")
        
        # בניית הודעה סופית
        report = f"📊 **דוח בדיקת ערוץ:** `{channel_id}`\n\n"
        report += "\n".join(results)
        
        if issues_found:
            report += "\n\n⚠️ **בעיות שנמצאו:**\n"
            report += "\n".join(issues_found)
        
        if solutions:
            report += "\n\n💡 **פתרונות מוצעים:**\n"
            report += "\n".join(solutions)
        
        if not issues_found:
            report += "\n\n✅ **הכל תקין!** הערוץ מוכן לשימוש."
        
        await status_msg.edit_text(report, reply_markup=get_main_keyboard())
        logger.info(f"✅ [TEST_CHANNEL] בדיקת ערוץ {channel_id} הושלמה עבור user {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in test_channel command: {e}", exc_info=True)
        await message.reply_text(
            f"❌ **שגיאה בבדיקת הערוץ:**\n\n`{str(e)}`",
            reply_markup=get_main_keyboard()
        )



