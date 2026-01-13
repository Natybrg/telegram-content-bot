"""
Handler לטיפול בקבצים אחרים (לא תמונה/MP3)
"""
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

import config
from core import is_authorized_user
from services.user_states import state_manager, UserState
from services.media import sanitize_filename
from services.media.audio import extract_mp3_metadata
from services.rate_limiter import rate_limit
from plugins.start import get_main_keyboard
from .helpers import format_mp3_metadata_message
from .audio_handler import _handle_mp3_file

logger = logging.getLogger(__name__)


@Client.on_message((filters.document | filters.video | filters.sticker | filters.animation) & filters.private)
@rate_limit(max_requests=10, window=60)
async def handle_other_files(client: Client, message: Message):
    """מטפל בקבצים אחרים - מבקש את הקובץ הנכון"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        return
    
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עריכת תבנית
    if session.state == UserState.EDITING_TEMPLATE:
        return
    
    # בדיקה אם זה MP3 שנשלח כ-document
    if message.document:
        file_name = message.document.file_name or ""
        mime_type = message.document.mime_type or ""
        
        # זיהוי MP3 לפי שם קובץ או MIME type
        is_mp3 = (
            file_name.lower().endswith('.mp3') or
            mime_type in ['audio/mpeg', 'audio/mp3', 'audio/x-mpeg-3']
        )
        
        if is_mp3:
            # טיפול ב-MP3 שנשלח כ-document
            logger.info(f"🎵 User {user.id} sent an MP3 file as document")
            await _handle_mp3_file(
                client=client,
                message=message,
                file_name=file_name,
                mime_type=mime_type,
                file_id=message.document.file_id,
                is_document=True
            )
            return
    
    # זיהוי סוג הקובץ
    file_type = "קובץ"
    if message.document:
        file_type = "מסמך"
    elif message.video:
        file_type = "וידאו"
    elif message.sticker:
        file_type = "סטיקר"
    elif message.animation:
        file_type = "GIF"
    
    # הודעה לפי המצב
    if session.state == UserState.IDLE or not session.image_path:
        await message.reply_text(
            f"⚠️ **{file_type} לא נתמך!**\n\n"
            f"📝 **התהליך הנכון:**\n"
            f"1️⃣ שלח תמונה (עטיפת אלבום)\n"
            f"2️⃣ שלח קובץ MP3\n"
            f"3️⃣ שלח 8 שורות פרטים\n\n"
            f"שלח /cancel כדי להתחיל מחדש"
        )
    elif session.state == UserState.WAITING_MP3:
        await message.reply_text(
            f"⚠️ **{file_type} לא נתמך!**\n\n"
            f"📁 **שלב הבא:** שלח קובץ **MP3**\n\n"
            f"שלח /cancel כדי להתחיל מחדש"
        )
    else:
        await message.reply_text(
            f"⚠️ **{file_type} לא נתמך!**\n\n"
            f"הבוט תומך רק בתמונות וקבצי MP3.\n"
            f"שלח /cancel כדי להתחיל מחדש"
        )
