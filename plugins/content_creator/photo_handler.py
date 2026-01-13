"""
Handler לטיפול בתמונות
"""
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

import config
from core import is_authorized_user
from services.user_states import state_manager, UserState
from services.rate_limiter import rate_limit
from plugins.start import get_main_keyboard

logger = logging.getLogger(__name__)


@Client.on_message(filters.photo & filters.private)
@rate_limit(max_requests=10, window=60)
async def handle_photo(client: Client, message: Message):
    """מטפל בקבלת תמונה"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized photo from user {user.id}")
        return
    
    logger.info(f"🖼️ User {user.id} sent a photo")
    
    # קבלת סשן המשתמש
    session = state_manager.get_session(user.id)
    
    try:
        # הורדת התמונה
        status_msg = await message.reply_text("📥 מוריד תמונה...")
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        # יצירת שם קובץ ייחודי
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{user.id}_{timestamp}.jpg"
        file_path = config.DOWNLOADS_PATH / filename
        
        downloaded_path = await message.download(file_name=str(file_path))
        
        # שמירת המידע בסשן
        session.image_file_id = message.photo.file_id
        session.image_path = downloaded_path
        session.add_file_for_cleanup(downloaded_path)
        session.update_state(UserState.WAITING_MP3)
        
        await status_msg.edit_text(
            "✅ **תמונה התקבלה!**\n\n"
            "📁 **שלב הבא:** שלח קובץ MP3"
        )
        
        logger.info(f"✅ Photo saved: {downloaded_path}")
        
    except Exception as e:
        logger.error(f"❌ Error handling photo: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בשמירת התמונה\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )
