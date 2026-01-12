"""
Queue Management Commands
פקודות לניהול תור העיבוד
"""
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import is_authorized_user

from services.processing_queue import processing_queue

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("queue_status") & filters.private)
async def queue_status_command(client: Client, message: Message):
    """פקודה לבדיקת מצב התור"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized queue_status request by user {user.id}")
        return
    
    logger.info(f"📊 User {user.id} requested queue status")
    
    try:
        status = processing_queue.get_queue_status(user.id)
        
        # בניית הודעת סטטוס
        status_message = "📊 **מצב התור**\n\n"
        
        # מספר אנשים בתור
        status_message += f"👥 **סה\"כ בתור:** {status['queue_size']} משתמשים\n"
        
        # האם מישהו מעובד כרגע
        if status['is_processing']:
            status_message += "⚙️ **סטטוס:** מעבד משתמש כעת\n"
        else:
            status_message += "✅ **סטטוס:** התור פנוי\n"
        
        status_message += "\n"
        
        # מצב המשתמש עצמו
        if status['current_user_id'] == user.id:
            status_message += "🎯 **אתה:** בעיבוד כעת!\n"
        elif status['user_in_queue']:
            status_message += f"📍 **המיקום שלך:** {status['user_position']}\n"
            status_message += f"⏱️ **זמן משוער:** ~{status['estimated_wait_minutes']} דקות\n"
        else:
            status_message += "ℹ️ **אתה לא בתור כרגע**\n"
        
        from plugins.start import get_main_keyboard
        await message.reply_text(status_message, reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"❌ Error in queue_status command: {e}", exc_info=True)
        from plugins.start import get_main_keyboard
        await message.reply_text("❌ שגיאה בבדיקת מצב התור", reply_markup=get_main_keyboard())


@Client.on_message(filters.command("cancel_queue") & filters.private)
async def cancel_queue_command(client: Client, message: Message):
    """פקודה לביטול מקום בתור"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized cancel_queue request by user {user.id}")
        return
    
    logger.info(f"🚫 User {user.id} requested to cancel queue")
    
    try:
        from plugins.start import get_main_keyboard
        
        # בדיקה אם המשתמש מעובד כרגע
        if processing_queue.current_user_id == user.id:
            await message.reply_text(
                "⚠️ **לא ניתן לבטל!**\n\n"
                "התוכן שלך כבר בעיבוד.\n"
                "אי אפשר לעצור תהליך שכבר התחיל.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # ביטול התור
        cancelled = await processing_queue.cancel_queue(user.id)
        
        if cancelled:
            await message.reply_text(
                "✅ **התור בוטל בהצלחה!**\n\n"
                "המיקום שלך בתור הוסר.\n"
                "תוכל להתחיל תהליך חדש מתי שתרצה.",
                reply_markup=get_main_keyboard()
            )
            logger.info(f"✅ User {user.id} cancelled their queue successfully")
        else:
            await message.reply_text(
                "ℹ️ **אין לך מקום בתור**\n\n"
                "לא מצאתי אותך ברשימת ההמתנה.",
                reply_markup=get_main_keyboard()
            )
            
    except Exception as e:
        logger.error(f"❌ Error in cancel_queue command: {e}", exc_info=True)
        from plugins.start import get_main_keyboard
        await message.reply_text("❌ שגיאה בביטול התור", reply_markup=get_main_keyboard())


logger.info("✅ Queue commands plugin loaded")
