"""
Telegram Fallback Delivery

Handles sending failed WhatsApp files back to users via Telegram.
"""
import logging
import asyncio
import os

from pyrogram import Client
from pyrogram.types import Message
from services.media.ffmpeg_utils import get_video_duration

logger = logging.getLogger(__name__)


async def send_failed_file_to_telegram(
    client: Client,
    user_id: int,
    file_path: str,
    template_text: str,
    failure_summary: str,
    session=None
) -> bool:
    """
    Send a file that failed WhatsApp delivery back to the user via Telegram
    
    Args:
        client: Pyrogram client
        user_id: Telegram user ID
        file_path Path to the file
        template_text: Template text for caption
        failure_summary: Summary of why it failed
        session: User session (optional, for metadata)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"📨 [TELEGRAM FALLBACK] Sending failed file to user {user_id}")
        logger.info(f"   File: {os.path.basename(file_path)}")
        logger.info(f"   Reason: {failure_summary}")
        
        # זיהוי סוג הקובץ
        ext = os.path.splitext(file_path)[1].lower()
        
        # יצירת הודעת שגיאה
        error_msg = f"⚠️ **העלאה לוואטסאפ נכשלה**\n\n{failure_summary}\n\n{template_text}"
        
        # שליחה למשתמש בטלגרם
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            await client.send_photo(user_id, file_path, caption=error_msg)
        elif ext in ['.mp3', '.m4a', '.wav']:
            # הוספת title ו-performer להצגה יפה בטלגרם
            audio_params = {
                'chat_id': user_id,
                'audio': file_path,
                'caption': error_msg,
                'title': session.song_name if session and hasattr(session, 'song_name') else None,
                'performer': session.artist_name if session and hasattr(session, 'artist_name') else None
            }
            
            # הוספת משך זמן אם אפשר
            try:
                audio_duration = await get_video_duration(file_path)
                if audio_duration:
                    audio_params['duration'] = int(audio_duration)
            except:
                pass  # אם נכשל, ממשיכים בלי duration
            
            await client.send_audio(**audio_params)
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            await client.send_video(user_id, file_path, caption=error_msg)
        else:
            await client.send_document(user_id, file_path, caption=error_msg)
        
        logger.info(f"✅ [TELEGRAM FALLBACK] File sent successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ [TELEGRAM FALLBACK] Error: {e}", exc_info=True)
        return False


def create_telegram_fallback_callback(client: Client, session):
    """
    Create a Telegram fallback callback function for WhatsApp delivery failures
    
    Args:
        client: Pyrogram client
        session: User session
    
    Returns:
        Callback function
    """
    def telegram_fallback_callback(user_id: int, file_path: str, template_text: str, failure_summary: str) -> bool:
        """
        Callback function for sending failed WhatsApp files back to user via Telegram
        """
        try:
            # הרצה אסינכרונית - נריץ ב-event loop הקיים
            result = asyncio.run_coroutine_threadsafe(
                send_failed_file_to_telegram(
                    client=client,
                    user_id=user_id,
                    file_path=file_path,
                    template_text=template_text,
                    failure_summary=failure_summary,
                    session=session
                ),
                asyncio.get_event_loop()
            )
            return result.result(timeout=30)
            
        except Exception as e:
            logger.error(f"❌ [TELEGRAM FALLBACK] Callback error: {e}", exc_info=True)
            return False
    
    return telegram_fallback_callback


async def send_failed_whatsapp_files_to_user(
    client: Client,
    message: Message,
    session,
    upload_status: dict,
    credits_text: str,
    mp3_thumb_path: str = None,
    mp3_duration: int = None,
    video_thumb_path: str = None,
    video_width: int = None,
    video_height: int = None
):
    """
    Send files that failed WhatsApp delivery back to the user via Telegram
    
    Args:
        client: Pyrogram client
        message: Original user message
        session: User session
        upload_status: Upload status dictionary
        credits_text: Credits text for captions
        mp3_thumb_path: Path to MP3 thumbnail (optional)
        mp3_duration: MP3 duration in seconds (optional)
        video_thumb_path: Path to video thumbnail (optional)
        video_width: Video width (optional)
        video_height: Video height (optional)
    """
    failed_whatsapp = []
    
    # בדיקה מה נכשל
    if not upload_status['whatsapp']['image']:
        failed_whatsapp.append('image')
    if not upload_status['whatsapp']['audio']:
        failed_whatsapp.append('audio')
    if session.need_video and not upload_status['whatsapp']['video']:
        failed_whatsapp.append('video')
    
    if not failed_whatsapp:
        logger.info("ℹ️ [TELEGRAM → USER] כל הקבצים נשלחו בהצלחה לוואטסאפ - אין צורך לשלוח למשתמש")
        return
    
    logger.info(f"📤 [TELEGRAM → USER] שולח קבצים שנכשלו בוואטסאפ למשתמש: {', '.join(failed_whatsapp)}")
    
    try:
        # תמונה
        if 'image' in failed_whatsapp and session.processed_image_path and os.path.exists(session.processed_image_path):
            image_caption = template_manager.render(
                "whatsapp_image",
                song_name=session.song_name,
                artist_name=session.artist_name,
                year=session.year,
                composer=session.composer,
                arranger=session.arranger,
                mixer=session.mixer,
                credits=credits_text,
                youtube_url=session.youtube_url
            )
            await message.reply_photo(
                session.processed_image_path,
                caption=f"⚠️ **תמונה לא נשלחה לוואטסאפ**\n\n{image_caption}"
            )
            logger.info("✅ [TELEGRAM → USER] תמונה נשלחה למשתמש")
        
        # MP3
        if 'audio' in failed_whatsapp and session.processed_mp3_path and os.path.exists(session.processed_mp3_path):
            audio_caption = template_manager.render(
                "whatsapp_audio",
                song_name=session.song_name,
                artist_name=session.artist_name,
                year=session.year,
                composer=session.composer,
                arranger=session.arranger,
                mixer=session.mixer,
                credits=credits_text,
                youtube_url=session.youtube_url
            )
            
            mp3_thumb_path_user = None
            if mp3_thumb_path and os.path.exists(mp3_thumb_path):
                mp3_thumb_path_user = mp3_thumb_path
            
            audio_params = {
                'audio': session.processed_mp3_path,
                'thumb': mp3_thumb_path_user,
                'caption': f"⚠️ **MP3 לא נשלח לוואטסאפ** (גדול מדי - {os.path.getsize(session.processed_mp3_path) / (1024*1024):.1f} MB)\n\n{audio_caption}",
                'title': session.song_name,
                'performer': session.artist_name
            }
            
            if mp3_duration:
                audio_params['duration'] = int(mp3_duration)
            
            await message.reply_audio(**audio_params)
            logger.info("✅ [TELEGRAM → USER] MP3 נשלח למשתמש")
        
        # וידאו
        if 'video' in failed_whatsapp and hasattr(session, 'upload_video_path') and session.upload_video_path and os.path.exists(session.upload_video_path):
            video_caption = template_manager.render(
                "whatsapp_video",
                song_name=session.song_name,
                artist_name=session.artist_name,
                year=session.year,
                composer=session.composer,
                arranger=session.arranger,
                mixer=session.mixer,
                credits=credits_text,
                youtube_url=session.youtube_url
            )
            
            video_thumb_for_user = None
            if video_thumb_path and os.path.exists(video_thumb_path):
                video_thumb_for_user = video_thumb_path
            
            await message.reply_video(
                session.upload_video_path,
                thumb=video_thumb_for_user,
                width=video_width if video_width else None,
                height=video_height if video_height else None,
                caption=f"⚠️ **וידאו לא נשלח לוואטסאפ** (גדול מדי - {os.path.getsize(session.upload_video_path) / (1024*1024):.1f} MB)\n\n{video_caption}"
            )
            logger.info("✅ [TELEGRAM → USER] וידאו נשלח למשתמש")
        
    except Exception as e:
        logger.error(f"❌ [TELEGRAM → USER] שגיאה בשליחה למשתמש: {e}", exc_info=True)
