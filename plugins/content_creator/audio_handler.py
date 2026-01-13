"""
Handler לטיפול בקבצי אודיו (MP3)
"""
import logging
import os
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

logger = logging.getLogger(__name__)


async def _handle_mp3_file(
    client: Client,
    message: Message,
    file_name: str,
    mime_type: str,
    file_id: str,
    is_document: bool = False
):
    """
    מטפל בקובץ MP3 (נקרא מ-handle_audio או handle_other_files)
    
    Args:
        client: Pyrogram client
        message: ההודעה
        file_name: שם הקובץ
        mime_type: MIME type
        file_id: File ID
        is_document: האם זה document או audio
    """
    user = message.from_user
    session = state_manager.get_session(user.id)
    
    # בדיקה אם זה חלק מתהליך העלאת סינגל (יש תמונה) או רק צפייה במטא-דאטה
    is_upload_process = session.image_path and session.state != UserState.IDLE
    
    try:
        # הורדת הקובץ
        status_msg = await message.reply_text("📥 מוריד MP3...")
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)
        session.messages_to_delete.append(status_msg)
        
        # יצירת שם קובץ ייחודי
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_filename = file_name if file_name else f"audio_{timestamp}.mp3"
        
        # ניקוי שם הקובץ
        clean_filename = sanitize_filename(original_filename)
        if not clean_filename.endswith('.mp3'):
            clean_filename += '.mp3'
        
        filename = f"{user.id}_{timestamp}_{clean_filename}"
        file_path = config.DOWNLOADS_PATH / filename
        
        downloaded_path = await message.download(file_name=str(file_path))
        
        # שמירת שם הקובץ המקורי
        original_filename = file_name if file_name else clean_filename
        
        # חילוץ מטא-דאטה
        await status_msg.edit_text("📊 מנתח מטא-דאטה...")
        metadata = await extract_mp3_metadata(downloaded_path, original_filename=original_filename)
        
        if metadata:
            # בניית הודעת מטא-דאטה עם עיצוב
            info_text, keyboard = format_mp3_metadata_message(metadata, user_id=user.id)
            
            # שליחת הודעה עם תמונה (אם יש) או בלי
            if metadata.get('album_art') and os.path.exists(metadata['album_art']):
                try:
                    # מחיקת status_msg לפני שליחת התמונה
                    try:
                        await status_msg.delete()
                    except:
                        pass
                    
                    # שליחת תמונה עם caption קצר (מקסימום 1024 תווים לטלגרם)
                    short_caption = info_text[:1000] if len(info_text) > 1000 else info_text
                    if len(info_text) > 1000:
                        short_caption = short_caption[:997] + "..."
                    
                    photo_msg = await message.reply_photo(
                        photo=metadata['album_art'],
                        caption=short_caption,
                        reply_markup=keyboard
                    )
                    
                    # אם ההודעה קוצרה, שולחים הודעה נוספת עם כל הפרטים
                    if len(info_text) > 1000:
                        await photo_msg.reply_text(
                            info_text,
                            reply_markup=keyboard
                        )
                    
                    # מחיקת קובץ התמונה הזמני
                    try:
                        os.remove(metadata['album_art'])
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"⚠️ לא ניתן לשלוח תמונה: {e}")
                    try:
                        await status_msg.edit_text(info_text, reply_markup=keyboard)
                    except:
                        await message.reply_text(info_text, reply_markup=keyboard)
            else:
                try:
                    await status_msg.edit_text(info_text, reply_markup=keyboard)
                except:
                    await message.reply_text(info_text, reply_markup=keyboard)
        else:
            if is_upload_process:
                await status_msg.edit_text(
                    "✅ **MP3 התקבל!**\n\n"
                    "⚠️ לא ניתן לחלץ מטא-דאטה מהקובץ.\n\n"
                    "📝 **שלב הבא:** שלח 8 שורות פרטים:\n"
                    "1. שם שיר\n"
                    "2. שם זמר\n"
                    "3. שנה\n"
                    "4. שם מלחין\n"
                    "5. שם מעבד\n"
                    "6. שם מיקס\n"
                    "7. קישור ליוטיוב\n"
                    "8. כן/לא (האם להוריד וידאו)\n\n"
                    "💡 כל פרט בשורה נפרדת"
                )
            else:
                await status_msg.edit_text(
                    "❌ **שגיאה**\n\n"
                    "⚠️ לא ניתן לחלץ מטא-דאטה מהקובץ.\n"
                    "ייתכן שהקובץ פגום או לא בפורמט MP3 תקין."
                )
        
        # שמירת המידע בסשן רק אם זה חלק מתהליך העלאת סינגל
        if is_upload_process:
            if is_document:
                session.mp3_file_id = file_id
            else:
                session.mp3_file_id = message.audio.file_id
            session.mp3_path = downloaded_path
            session.add_file_for_cleanup(downloaded_path)
            session.update_state(UserState.WAITING_DETAILS)
        else:
            # רק לצפייה - מוסיף לניקוי אבל לא שומר בסשן
            session.add_file_for_cleanup(downloaded_path)
        
        logger.info(f"✅ MP3 saved: {downloaded_path}")
        
    except Exception as e:
        logger.error(f"❌ Error handling MP3: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בשמירת הקובץ\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )


@Client.on_message(filters.audio & filters.private)
@rate_limit(max_requests=10, window=60)
async def handle_audio(client: Client, message: Message):
    """מטפל בקבלת קובץ MP3"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized audio from user {user.id}")
        return
    
    logger.info(f"🎵 User {user.id} sent an audio file")
    
    file_name = message.audio.file_name if message.audio.file_name else None
    mime_type = "audio/mpeg"  # audio messages are always MP3
    file_id = message.audio.file_id
    
    await _handle_mp3_file(
        client=client,
        message=message,
        file_name=file_name,
        mime_type=mime_type,
        file_id=file_id,
        is_document=False
    )
