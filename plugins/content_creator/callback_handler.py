"""
Handler לטיפול ב-callbacks (כפתורי Inline)
"""
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from core import is_authorized_user
from services.user_states import state_manager
from services.rate_limiter import rate_limit
from .cleanup import cleanup_session_files

logger = logging.getLogger(__name__)


@Client.on_callback_query(filters.regex("^mp3_done_"))
@rate_limit(max_requests=10, window=60)
async def handle_mp3_done_callback(client: Client, callback_query: CallbackQuery):
    """מטפל בלחיצה על כפתור 'סיום' - מוחק את הקבצים שהורידו"""
    user = callback_query.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        await callback_query.answer("⛔ אין לך הרשאה להשתמש בזה", show_alert=True)
        return
    
    try:
        # קבלת סשן המשתמש
        session = state_manager.get_session(user.id)
        
        # ניקוי הקבצים
        await cleanup_session_files(session)
        
        # עדכון ההודעה
        await callback_query.answer("✅ הקבצים נמחקו בהצלחה!", show_alert=False)
        await callback_query.message.edit_reply_markup(reply_markup=None)
        
        # הוספת הודעה על סיום
        await callback_query.message.reply_text(
            "✅ **סיום**\n\n"
            "🗑️ כל הקבצים שהורדו נמחקו.\n"
            "💡 אתה יכול להתחיל תהליך חדש."
        )
        
        logger.info(f"✅ User {user.id} completed MP3 metadata view and cleaned up files")
        
    except Exception as e:
        logger.error(f"❌ Error handling MP3 done callback: {e}", exc_info=True)
        await callback_query.answer("❌ שגיאה במחיקת הקבצים", show_alert=True)
