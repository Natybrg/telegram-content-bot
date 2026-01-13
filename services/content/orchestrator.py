"""
Content Processing Orchestrator
מתאם עיבוד תוכן - מנהל את כל תהליך העיבוד וההעלאה
"""
import logging
import asyncio
import os
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid

from core import (
    WHATSAPP_ENABLED, WHATSAPP_CHAT_NAME, WHATSAPP_DRY_RUN,
    PUBLISH_TO_CHANNELS, AUDIO_CONTENT_CHANNEL_ID, VIDEO_CONTENT_CHANNEL_ID,
    executor_manager, DOWNLOADS_PATH, TELEGRAM_MAX_FILE_SIZE_MB,
    WHATSAPP_MAX_FILE_SIZE_BYTES
)
from services.user_states import UserState
from services.media import (
    update_mp3_tags,
    get_video_dimensions,
    fetch_youtube_thumbnail,
    prepare_telegram_thumbnail,
    prepare_mp3_thumbnail,
    build_target_filename,
    create_upload_copy
)
from services.media.ffmpeg_utils import get_video_duration
from services.media.downloaders.video_downloader import download_video_with_retry
from services.templates import template_manager
from core.context import get_context
from services.content.progress_tracker import ProgressTracker
from services.channels import channels_manager, send_to_telegram_channels, send_to_whatsapp_groups
from services.whatsapp.delivery import WhatsAppDelivery
# Import common functions
from .common import get_progress_stage, create_progress_bar, _import_cleanup

logger = logging.getLogger(__name__)


# ========== עיבוד התוכן ==========

async def process_content(client: Client, message: Message, session, status_msg: Message):
    """
    מעבד את כל התוכן:
    1. יוצר תמונה עם קרדיטים
    2. מעדכן תגיות MP3
    3. מתחיל הורדת וידאו מיוטיוב ברקע (אם נדרש)
    4. תוך כדי ההורדה: מעלה תמונה ו-MP3 לטלגרם ולוואטסאפ
    5. ממתין לסיום הורדת הווידאו ומעלה אותו
    6. מנקה קבצים
    """
    user_id = session.user_id
    
    # ========== Initialize Progress Tracker ==========
    tracker = ProgressTracker(session, status_msg)
    
    try:
        # ========== שלב 1: הכנת קרדיטים (ללא שינוי התמונה) ==========
        await tracker.update_status("הורדה של תמונה", 0, 0)
        logger.info(f"🖼️ Preparing credits for user {user_id}")
        
        # בדיקה שהתמונה קיימת
        if not session.image_path:
            error_msg = "תמונה לא נמצאה. נא לשלוח תמונה מחדש."
            logger.error(f"❌ {error_msg} (user {user_id})")
            raise Exception(error_msg)
        
        # בדיקה שהקובץ קיים בפועל
        if not os.path.exists(session.image_path):
            error_msg = f"קובץ התמונה לא נמצא: {session.image_path}. נא לשלוח תמונה מחדש."
            logger.error(f"❌ {error_msg} (user {user_id})")
            raise Exception(error_msg)
        
        # הכנת קרדיטים
        credits_text = session.get_credits_text()
        
        # בניית שמות קבצים לכל הקבצים לפני העלאה: {artist} - {song}.{ext}
        original_image_filename = os.path.basename(session.image_path) if session.image_path else "image.jpg"
        target_image_name = build_target_filename(
            artist_name=session.artist_name,
            song_name=session.song_name,
            original_filename=original_image_filename
        )
        
        # יצירת עותק של התמונה עם שם חדש להעלאה
        upload_image_path = create_upload_copy(
            original_path=session.image_path,
            new_filename=target_image_name
        )
        if not upload_image_path:
            raise Exception("Failed to create image copy for upload")
        
        session.processed_image_path = upload_image_path
        session.add_file_for_cleanup(upload_image_path)  # למחיקה אחרי העלאה
        logger.info(f"✅ Created image copy for upload: {target_image_name}")
        
        # ========== שלב 2: עיבוד MP3 ==========
        await tracker.update_status("הורדה של סינגל", 12, 1)
        logger.info(f"🎵 Updating MP3 tags for user {user_id}")
        
        metadata = {
            'title': session.song_name,
            'artist': session.artist_name,
            'year': session.year,
            'composer': session.composer,
            'arranger': session.arranger,
            'mixer': session.mixer,
            'album': 'סינגל'  # לפי הפרומפט
        }
        
        # בדיקה שה-MP3 קיים
        if not session.mp3_path:
            error_msg = "קובץ MP3 לא נמצא. נא לשלוח קובץ MP3 מחדש."
            logger.error(f"❌ {error_msg} (user {user_id})")
            raise Exception(error_msg)
        
        # בדיקה שהקובץ קיים בפועל
        if not os.path.exists(session.mp3_path):
            error_msg = f"קובץ ה-MP3 לא נמצא: {session.mp3_path}. נא לשלוח קובץ MP3 מחדש."
            logger.error(f"❌ {error_msg} (user {user_id})")
            raise Exception(error_msg)
        
        # בניית שם קובץ יעד לפני העלאה: {artist} - {song}.{ext}
        original_filename = os.path.basename(session.mp3_path) if session.mp3_path else "audio.mp3"
        target_mp3_name = build_target_filename(
            artist_name=session.artist_name,
            song_name=session.song_name,
            original_filename=original_filename
        )
        output_mp3_path = DOWNLOADS_PATH / target_mp3_name
        
        processed_mp3 = await update_mp3_tags(
            mp3_path=session.mp3_path,
            image_path=session.image_path,  # תמונה מקורית (לא המעובדת)
            metadata=metadata,
            output_path=str(output_mp3_path)
        )
        
        if not processed_mp3:
            raise Exception("Failed to update MP3 tags")
        
        session.processed_mp3_path = processed_mp3
        session.add_file_for_cleanup(processed_mp3)
        logger.info("✅ MP3 tags updated: {processed_mp3}")
        
        # ========== שלב 3: הורדת וידאו ברקע ==========
        video_download_task = None
        if session.need_video:
            await tracker.update_status("הורדה של קליפ לטלגרם (מיוטיוב)", 43, 0)
            logger.info(f"📥 Starting YouTube video download in background for user {user_id}")
            logger.info(f"  URL: {session.youtube_url}")
            
            # שימוש ב-video_downloader החדש
            async def download_video_task():
                """Task להורדת וידאו ברקע עם מנגנון retry"""
                # יצירת פונקציית update_status wrapper
                async def update_status_wrapper(operation_name, percent, emoji_index=0):
                    await tracker.update_status(operation_name, percent, emoji_index)
                
                return await download_video_with_retry(
                    session=session,
                    upload_progress=tracker.upload_progress,
                    update_status_func=update_status_wrapper,
                    errors=tracker.errors
                )
            
            # התחלת ההורדה ברקע
            video_download_task = asyncio.create_task(download_video_task())
            logger.info("✅ [BACKGROUND] הורדת וידאו התחילה ברקע - ממשיכים להעלאת תמונה ו-MP3")
        else:
            logger.info(f"ℹ️ [YOUTUBE] וידאו לא נדרש - דילוג")
        
        # ========== שלב 4: העלאה לטלגרם (תמונה ו-MP3) ==========
        await tracker.update_status("העלאת תמונה לטלגרם", 50, 0)
        logger.info(f"📤 [TELEGRAM] התחלת העלאת תמונה ו-MP3 לערוצים")
        
        # קבלת הבוט והיוזרבוט
        bot = client
        
        # נסיון למצוא את היוזרבוט (לקבצים גדולים)
        userbot = None
        try:
            # אם יש userbot פעיל, נשתמש בו לקבצים גדולים
            context = get_context()
            userbot = context.get_userbot()
            if userbot:
                logger.info("✅ [TELEGRAM] Userbot זמין לקבצים גדולים")
        except Exception as e:
            logger.warning(f"⚠️ [TELEGRAM] Could not access userbot: {e}")
        
        # וידוא שהקבצים קיימים
        image_to_send = session.processed_image_path or session.image_path
        if not image_to_send or not os.path.exists(image_to_send):
            logger.error(f"❌ [TELEGRAM] קובץ תמונה לא נמצא: {image_to_send}")
            raise Exception(f"Image file not found: {image_to_send}")
        
        mp3_to_send = session.processed_mp3_path
        if not mp3_to_send or not os.path.exists(mp3_to_send):
            logger.error(f"❌ [TELEGRAM] קובץ MP3 לא נמצא: {mp3_to_send}")
            raise Exception(f"MP3 file not found: {mp3_to_send}")
        
        mp3_size_mb = os.path.getsize(mp3_to_send) / (1024 * 1024)
        logger.info(f"ℹ️ [TELEGRAM] גודל MP3: {mp3_size_mb:.2f} MB")
        
        # בדיקת גודל מקסימלי ל-Telegram (2GB)
        if mp3_size_mb > TELEGRAM_MAX_FILE_SIZE_MB:
            raise Exception(f"MP3 גדול מדי ל-Telegram: {mp3_size_mb:.2f}MB > {TELEGRAM_MAX_FILE_SIZE_MB}MB")
        
        # הכנת thumbnail ל-MP3 (JPEG ≤320px, ממירה ומקטינה את התמונה המקורית)
        mp3_thumb_path = None
        try:
            logger.info("🎨 [TELEGRAM] מכין thumbnail ל-MP3...")
            mp3_thumb_path = await prepare_mp3_thumbnail(
                input_image_path=session.image_path  # תמונה מקורית
            )
            
            if mp3_thumb_path:
                session.add_file_for_cleanup(mp3_thumb_path)
                logger.info(f"✅ [TELEGRAM] MP3 thumbnail מוכן: {mp3_thumb_path}")
            else:
                logger.warning("⚠️ [TELEGRAM] הכנת MP3 thumbnail נכשלה")
        except Exception as e:
            logger.error(f"❌ [TELEGRAM] שגיאה בהכנת MP3 thumbnail: {e}", exc_info=True)
        
        # קבלת משך הזמן של ה-MP3 (לצורך הצגה בטלגרם)
        mp3_duration = None
        try:
            logger.info("⏱️ [TELEGRAM] מחלץ משך זמן של MP3...")
            mp3_duration = await get_video_duration(session.processed_mp3_path)
            if mp3_duration:
                logger.info(f"✅ [TELEGRAM] משך זמן MP3: {int(mp3_duration)} שניות ({int(mp3_duration//60)}:{int(mp3_duration%60):02d})")
            else:
                logger.warning("⚠️ [TELEGRAM] לא ניתן לחלץ משך זמן MP3")
        except Exception as e:
            logger.error(f"❌ [TELEGRAM] שגיאה בחילוץ משך זמן MP3: {e}", exc_info=True)
        
        # עדכון סטטוס - לא שולחים למשתמש, רק לערוצים
        tracker.upload_status['telegram']['image'] = True
        tracker.upload_status['telegram']['audio'] = True
        tracker.upload_progress['telegram']['image'] = 100
        tracker.upload_progress['telegram']['audio'] = 100
        await tracker.update_status("העלאת סינגל לטלגרם", 67, 0)
        
        # ========== העלאה לערוצי טלגרם (תמונה + MP3) ==========
        if PUBLISH_TO_CHANNELS:
            try:
                # ⚡ שימוש ב-Userbot לפרסום בערוצים
                channel_client = userbot if userbot else bot
                logger.info(f"ℹ️ [TELEGRAM → CHANNEL] משתמש ב-{'Userbot' if userbot else 'Bot'} לפרסום")
                
                # איסוף רשימת ערוצים: רק מהמאגר (המשתמש מוסיף בעצמו)
                telegram_channels = []
                
                # ערוצים מהמאגר (לפי תבנית telegram_image)
                template_channels = channels_manager.get_template_channels("telegram_image", "telegram")
                if template_channels:
                    telegram_channels.extend(template_channels)
                
                # הסרת כפילויות
                telegram_channels = list(dict.fromkeys(telegram_channels))
                
                # שליחה רק אם יש ערוצים מהמאגר
                if telegram_channels:
                    logger.info(f"📢 [TELEGRAM → CHANNEL] מעלה תוכן אודיו ל-{len(telegram_channels)} ערוצים")
                    logger.info(f"📋 [TELEGRAM → CHANNEL] רשימת ערוצים (peer_id_b64): {[ch[:20] + '...' if len(ch) > 20 else ch for ch in telegram_channels]}")
                    
                    # שליחת תמונה
                    logger.info("📤 [TELEGRAM → CHANNEL] שלב 1/2 - שולח תמונה")
                    channel_image_caption = template_manager.render(
                        "telegram_image",
                        song_name=session.song_name,
                        artist_name=session.artist_name,
                        year=session.year,
                        composer=session.composer,
                        arranger=session.arranger,
                        mixer=session.mixer,
                        credits=credits_text,
                        youtube_url=session.youtube_url
                    )
                    
                    image_result = await send_to_telegram_channels(
                        client=channel_client,
                        file_path=image_to_send,
                        file_type='photo',
                        caption=channel_image_caption,
                        channels=telegram_channels,
                        first_channel_peer_id_b64=None,
                        protected_channels=[]
                    )
                    
                    if image_result['success']:
                        logger.info(f"✅ [TELEGRAM → CHANNEL] תמונה נשלחה ל-{len(image_result['sent_to'])} ערוצים")
                    else:
                        logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בשליחת תמונה: {image_result.get('error')}")
                    
                    # שליחת MP3
                    logger.info("📤 [TELEGRAM → CHANNEL] שלב 2/2 - שולח MP3")
                    channel_audio_caption = template_manager.render(
                        "telegram_audio",
                        song_name=session.song_name,
                        artist_name=session.artist_name,
                        year=session.year,
                        composer=session.composer,
                        arranger=session.arranger,
                        mixer=session.mixer,
                        credits=credits_text,
                        youtube_url=session.youtube_url
                    )
                    
                    audio_kwargs = {
                        'title': session.song_name,
                        'performer': session.artist_name
                    }
                    
                    if mp3_thumb_path and os.path.exists(mp3_thumb_path):
                        audio_kwargs['thumb'] = mp3_thumb_path
                    
                    if mp3_duration:
                        audio_kwargs['duration'] = int(mp3_duration)
                    
                    audio_result = await send_to_telegram_channels(
                        client=channel_client,
                        file_path=session.processed_mp3_path,
                        file_type='audio',
                        caption=channel_audio_caption,
                        channels=telegram_channels,
                        first_channel_peer_id_b64=None,
                        protected_channels=[],
                        **audio_kwargs
                    )
                    
                    if audio_result['success']:
                        logger.info(f"✅ [TELEGRAM → CHANNEL] MP3 נשלח ל-{len(audio_result['sent_to'])} ערוצים")
                    else:
                        logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בשליחת MP3: {audio_result.get('error')}")
                else:
                    logger.info("ℹ️ [TELEGRAM → CHANNEL] אין ערוצים להעלאה")
                
            except Exception as e:
                logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בפרסום לערוצים: {e}", exc_info=True)
        else:
            logger.info("ℹ️ [TELEGRAM → CHANNEL] פרסום לערוצים מנוטרל")
        
        # ========== Telegram Fallback Callback ==========
        def telegram_fallback_callback(user_id: int, file_path: str, template_text: str, failure_summary: str) -> bool:
            """
            Callback function for sending failed WhatsApp files back to user via Telegram
            """
            try:
                logger.info(f"📨 [TELEGRAM FALLBACK] Sending failed file to user {user_id}")
                logger.info(f"   File: {os.path.basename(file_path)}")
                logger.info(f"   Reason: {failure_summary}")
                
                # זיהוי סוג הקובץ
                ext = os.path.splitext(file_path)[1].lower()
                
                # יצירת הודעת שגיאה
                error_msg = f"⚠️ **העלאה לוואטסאפ נכשלה**\n\n{failure_summary}\n\n{template_text}"
                
                # שליחה למשתמש בטלגרם (סינכרוני - נריץ בthread)
                async def send_to_telegram():
                    try:
                        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                            await client.send_photo(user_id, file_path, caption=error_msg)
                        elif ext in ['.mp3', '.m4a', '.wav']:
                            # הוספת title ו-performer להצגה יפה בטלגרם
                            audio_params = {
                                'chat_id': user_id,
                                'audio': file_path,
                                'caption': error_msg,
                                'title': session.song_name if hasattr(session, 'song_name') else None,  # שם השיר - יוצג בגדול
                                'performer': session.artist_name if hasattr(session, 'artist_name') else None  # שם האמנים - יוצג בקטן
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
                        return True
                    except Exception as e:
                        logger.error(f"❌ [TELEGRAM FALLBACK] Error: {e}", exc_info=True)
                        return False
                
                # הרצה אסינכרונית
                result = asyncio.run_coroutine_threadsafe(send_to_telegram(), asyncio.get_event_loop())
                return result.result(timeout=30)
                
            except Exception as e:
                logger.error(f"❌ [TELEGRAM FALLBACK] Callback error: {e}", exc_info=True)
                return False
        
        # ========== שלב 5: שליחה לוואטסאפ (תמונה ו-MP3) ==========
        whatsapp_success = True
        if WHATSAPP_ENABLED:
            try:
                await tracker.update_status("העלאת תמונה לוואטסאפ", 79, 0)
                
                # איסוף רשימת קבוצות: קבועה + מהמאגר
                whatsapp_groups = []
                
                # קבוצות מהמאגר (לפי תבנית whatsapp_image) - המשתמש מוסיף בעצמו
                template_groups = channels_manager.get_template_channels("whatsapp_image", "whatsapp")
                if template_groups:
                    whatsapp_groups.extend(template_groups)
                
                # הסרת כפילויות
                whatsapp_groups = list(dict.fromkeys(whatsapp_groups))
                
                # שליחה תמיד אם יש קבוצה קבועה, גם אם אין קבוצות ידניות
                if whatsapp_groups:
                    logger.info(f"📱 [WHATSAPP] התחלת שליחה ל-{len(whatsapp_groups)} קבוצות")
                    
                    executor = executor_manager.get_executor()
                    loop = asyncio.get_event_loop()
                    whatsapp = WhatsAppDelivery(dry_run=WHATSAPP_DRY_RUN)
                    
                    try:
                        # שליחת תמונה (שלב 1/2)
                        if session.processed_image_path and os.path.exists(session.processed_image_path):
                            logger.info("📤 [WHATSAPP] שלב 1/2 - שולח תמונה...")
                            
                            whatsapp_image_caption = template_manager.render(
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
                            
                            image_result = await send_to_whatsapp_groups(
                                whatsapp_delivery=whatsapp,
                                file_path=session.processed_image_path,
                                file_type='image',
                                caption=whatsapp_image_caption,
                                groups=whatsapp_groups,
                                telegram_user_id=user_id,
                                telegram_fallback_callback=telegram_fallback_callback,
                                session=session
                            )
                            
                            if image_result.get('success') and image_result.get('sent_to'):
                                logger.info(f"✅ [WHATSAPP] תמונה נשלחה ל-{len(image_result['sent_to'])} קבוצות")
                                tracker.upload_status['whatsapp']['image'] = True
                                tracker.upload_progress['whatsapp']['image'] = 100
                                tracker.upload_results['whatsapp']['image'] = {
                                    "success": True,
                                    "size_mb": round(os.path.getsize(session.processed_image_path) / (1024*1024), 1),
                                    "sent_to": len(image_result['sent_to'])
                                }
                                await tracker.update_status("העלאת תמונה לוואטסאפ", 80, 0)
                            else:
                                logger.warning(f"⚠️ [WHATSAPP] שליחת תמונה נכשלה: {image_result.get('errors', [])}")
                                tracker.errors.append({"platform": "whatsapp", "file_type": "image", "error": str(image_result.get('errors', []))})
                                whatsapp_success = False
                                await tracker.update_status("העלאת תמונה לוואטסאפ - נכשל", 80, 0)
                        else:
                            logger.warning("⚠️ [WHATSAPP] קובץ תמונה לא נמצא")
                        
                        # שליחת MP3 (שלב 2/2)
                        if session.processed_mp3_path and os.path.exists(session.processed_mp3_path):
                            mp3_size = os.path.getsize(session.processed_mp3_path)
                            logger.info(f"📤 [WHATSAPP] שלב 2/2 - שולח MP3 ({mp3_size / (1024*1024):.2f} MB)...")
                            
                            if mp3_size <= WHATSAPP_MAX_FILE_SIZE_BYTES:
                                whatsapp_audio_caption = template_manager.render(
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
                                
                                mp3_result = await send_to_whatsapp_groups(
                                    whatsapp_delivery=whatsapp,
                                    file_path=session.processed_mp3_path,
                                    file_type='audio',
                                    caption=whatsapp_audio_caption,
                                    groups=whatsapp_groups,
                                    telegram_user_id=user_id,
                                    telegram_fallback_callback=telegram_fallback_callback,
                                    session=session
                                )
                                
                                if mp3_result.get('success') and mp3_result.get('sent_to'):
                                    logger.info(f"✅ [WHATSAPP] MP3 נשלח ל-{len(mp3_result['sent_to'])} קבוצות")
                                    tracker.upload_status['whatsapp']['audio'] = True
                                    tracker.upload_progress['whatsapp']['audio'] = 100
                                    tracker.upload_results['whatsapp']['audio'] = {
                                        "success": True,
                                        "size_mb": round(mp3_size / (1024*1024), 1),
                                        "sent_to": len(mp3_result['sent_to'])
                                    }
                                    await tracker.update_status("העלאת סינגל לוואטסאפ", 85, 0)
                                else:
                                    logger.warning(f"⚠️ [WHATSAPP] שליחת MP3 נכשלה: {mp3_result.get('errors', [])}")
                                    tracker.errors.append({"platform": "whatsapp", "file_type": "audio", "error": str(mp3_result.get('errors', []))})
                                    whatsapp_success = False
                                    await tracker.update_status("העלאת סינגל לוואטסאפ - נכשל", 85, 0)
                            else:
                                logger.warning(f"⚠️ [WHATSAPP] MP3 גדול מדי ({mp3_size / (1024*1024):.2f} MB), דילוג")
                        else:
                            logger.warning("⚠️ [WHATSAPP] קובץ MP3 לא נמצא")
                    finally:
                        if 'whatsapp' in locals():
                            whatsapp.close()
                        logger.info("✅ [WHATSAPP] שליחה סדרתית הושלמה")
                else:
                    logger.info("ℹ️ [WHATSAPP] אין קבוצות לשליחה - לא נשלח תוכן לוואטסאפ (תמונה ו-MP3)")
                    
            except Exception as e:
                logger.error(f"❌ [WHATSAPP] שגיאה בשליחה: {e}", exc_info=True)
                whatsapp_success = False
                # לא נעצור את התהליך - רק נוודא שהשגיאה מתועדת
        else:
            logger.info("ℹ️ [WHATSAPP] שליחה לוואטסאפ מנוטרלת או לא הוגדרה")
        
        # ========== שלב 6: המתנה לסיום הורדת וידאו והעלאה ==========
        # הגדרת משתנים לוידאו לפני השימוש (למניעת NameError)
        video_thumb_path = None
        video_width = None
        video_height = None
        
        if video_download_task:
            await tracker.update_status("ממתין לסיום הורדת הווידאו", 85, 0)
            logger.info("⏳ [BACKGROUND] ממתין לסיום הורדת וידאו ברקע...")
            
            # ממתינים לסיום ההורדה
            video_success = await video_download_task
            
            if video_success and session.video_high_path and os.path.exists(session.video_high_path):
                logger.info("✅ [YOUTUBE] הורדת וידאו הושלמה, מתחיל העלאה!")
                await tracker.update_status("העלאת קליפ לטלגרם", 99, 0)
                
                # בניית שם קובץ וידאו לפני העלאה: {artist} - {song}.{ext}
                original_video_filename = os.path.basename(session.video_high_path)
                target_video_name = build_target_filename(
                    artist_name=session.artist_name,
                    song_name=session.song_name,
                    original_filename=original_video_filename
                )
                
                # יצירת עותק של הוידאו עם שם חדש להעלאה
                upload_video_path = create_upload_copy(
                    original_path=session.video_high_path,
                    new_filename=target_video_name
                )
                if not upload_video_path:
                    raise Exception("Failed to create video copy for upload")
                
                session.upload_video_path = upload_video_path
                session.add_file_for_cleanup(upload_video_path)  # למחיקה אחרי העלאה
                logger.info(f"✅ Created video copy for upload: {target_video_name}")
                
                # העלאת וידאו איכותי לטלגרם
                logger.info("📤 [TELEGRAM → USER] מעלה וידאו איכות גבוהה...")
                video_size_mb = os.path.getsize(upload_video_path) / (1024 * 1024)
                logger.info(f"ℹ️ [TELEGRAM] גודל וידאו: {video_size_mb:.2f} MB")
                
                # בדיקת גודל מקסימלי ל-Telegram (2GB)
                if video_size_mb > TELEGRAM_MAX_FILE_SIZE_MB:
                    raise Exception(f"וידאו גדול מדי ל-Telegram: {video_size_mb:.2f}MB > {TELEGRAM_MAX_FILE_SIZE_MB}MB")
                
                # ========== הכנת thumbnail ו-dimensions לוידאו ==========
                
                try:
                    # 1. חילוץ ממדי הוידאו (עם תמיכה ב-rotation)
                    logger.info("📐 [TELEGRAM] מחלץ ממדי וידאו...")
                    dimensions = await get_video_dimensions(session.video_high_path)
                    if dimensions:
                        video_width, video_height = dimensions
                        logger.info(f"✅ [TELEGRAM] ממדי וידאו: {video_width}x{video_height}")
                    else:
                        logger.warning("⚠️ [TELEGRAM] לא ניתן לחלץ ממדי וידאו")
                    
                    # 2. הורדת thumbnail מ-YouTube
                    logger.info("🖼️ [YOUTUBE] מוריד thumbnail...")
                    raw_thumbnail = await fetch_youtube_thumbnail(
                        url=session.youtube_url,
                        cookies_path="cookies.txt"
                    )
                    
                    if raw_thumbnail:
                        session.add_file_for_cleanup(raw_thumbnail)
                        logger.info(f"✅ [YOUTUBE] Thumbnail הורד: {raw_thumbnail}")
                        
                        # 3. הכנת thumbnail לדרישות Telegram
                        if video_width and video_height:
                            aspect_ratio = video_width / video_height
                            logger.info(f"🎨 [TELEGRAM] מכין thumbnail (aspect ratio: {aspect_ratio:.3f})...")
                            
                            video_thumb_path = await prepare_telegram_thumbnail(
                                input_image_path=raw_thumbnail,
                                video_aspect_ratio=aspect_ratio
                            )
                            
                            if video_thumb_path:
                                session.add_file_for_cleanup(video_thumb_path)
                                logger.info(f"✅ [TELEGRAM] Thumbnail מוכן: {video_thumb_path}")
                            else:
                                logger.warning("⚠️ [TELEGRAM] הכנת thumbnail נכשלה")
                        else:
                            logger.warning("⚠️ [TELEGRAM] לא ניתן להכין thumbnail ללא ממדי וידאו")
                    else:
                        logger.warning("⚠️ [YOUTUBE] הורדת thumbnail נכשלה")
                        
                except Exception as e:
                    logger.error(f"❌ [TELEGRAM] שגיאה בהכנת thumbnail/dimensions: {e}", exc_info=True)
                
                # עדכון סטטוס - וידאו מוכן לערוץ
                tracker.upload_status['telegram']['video'] = True
                tracker.upload_progress['telegram']['video'] = 100
                await tracker.update_status("העלאת קליפ לטלגרם", 100, 0)
                
                # ========== העלאה לערוצי טלגרם (וידאו) ==========
                if PUBLISH_TO_CHANNELS:
                    try:
                        # בדיקה ש-upload_video_path קיים
                        if not hasattr(session, 'upload_video_path') or not session.upload_video_path:
                            logger.error("❌ [TELEGRAM → CHANNEL] upload_video_path לא קיים - לא ניתן לשלוח לערוץ")
                        else:
                            # שימוש ב-Userbot לפרסום בערוצים (כמו שהיה מקודם)
                            channel_client = userbot if userbot else bot
                            client_type = "Userbot" if userbot else "Bot"
                            logger.info(f"ℹ️ [TELEGRAM → CHANNEL] משתמש ב-{client_type} לפרסום")
                            
                            # איסוף רשימת ערוצים: רק מהמאגר (המשתמש מוסיף בעצמו)
                            telegram_video_channels = []
                            
                            # ערוצים מהמאגר (לפי תבנית telegram_video)
                            template_channels = channels_manager.get_template_channels("telegram_video", "telegram")
                            if template_channels:
                                telegram_video_channels.extend(template_channels)
                            
                            # הסרת כפילויות
                            telegram_video_channels = list(dict.fromkeys(telegram_video_channels))
                            
                            # שליחה רק אם יש ערוצים מהמאגר
                            if telegram_video_channels:
                                logger.info(f"📢 [TELEGRAM → CHANNEL] מעלה וידאו ל-{len(telegram_video_channels)} ערוצים")
                                logger.info(f"📋 [TELEGRAM → CHANNEL] רשימת ערוצים: {telegram_video_channels}")
                                
                                logger.info(f"📋 [TELEGRAM → CHANNEL] רשימת ערוצים (peer_id_b64): {[ch[:20] + '...' if len(ch) > 20 else ch for ch in telegram_video_channels]}")
                                
                                channel_video_caption = template_manager.render(
                                    "telegram_video",
                                    song_name=session.song_name,
                                    artist_name=session.artist_name,
                                    year=session.year,
                                    composer=session.composer,
                                    arranger=session.arranger,
                                    mixer=session.mixer,
                                    credits=credits_text,
                                    youtube_url=session.youtube_url
                                )
                                
                                video_kwargs = {}
                                if video_width and video_height:
                                    video_kwargs['width'] = video_width
                                    video_kwargs['height'] = video_height
                                
                                if video_thumb_path and os.path.exists(video_thumb_path):
                                    video_kwargs['thumb'] = video_thumb_path
                                
                                logger.info(f"📤 [TELEGRAM → CHANNEL] מתחיל שליחה ל-{len(telegram_video_channels)} ערוצים...")
                                video_result = await send_to_telegram_channels(
                                    client=channel_client,
                                    file_path=session.upload_video_path,
                                    file_type='video',
                                    caption=channel_video_caption,
                                    channels=telegram_video_channels,
                                    first_channel_peer_id_b64=telegram_video_channels[0] if telegram_video_channels else None,
                                    protected_channels=[],
                                    **video_kwargs
                                )
                                
                                if video_result['success']:
                                    logger.info(f"✅ [TELEGRAM → CHANNEL] וידאו נשלח ל-{len(video_result['sent_to'])} ערוצים")
                                else:
                                    error_msg = video_result.get('error', 'Unknown error')
                                    logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בשליחת וידאו: {error_msg}")
                            else:
                                logger.info("ℹ️ [TELEGRAM → CHANNEL] אין ערוצים להעלאת וידאו")
                        
                    except Exception as e:
                        logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בפרסום וידאו לערוצים: {e}", exc_info=True)
                else:
                    logger.info("ℹ️ [TELEGRAM → CHANNEL] פרסום וידאו לערוצים מנוטרל")
                
                # העלאת וידאו לוואטסאפ
                if WHATSAPP_ENABLED:
                    try:
                        await tracker.update_status("עיבוד קליפ וואטסאפ", 80, 0)
                        logger.info(f"📱 [WHATSAPP] שלב 3/3 - שולח וידאו")
                        
                        # 🔧 בחירת הקובץ הקטן ביותר לוואטסאפ (עד 100MB)
                        # 1. אם יש video_medium_path (720-ish/≤70MB) - משתמשים בו
                        # 2. אם לא, משתמשים ב-upload_video_path (1080-ish)
                        # הערה: דחיסה ל-70MB תתבצע אוטומטית ב-WhatsApp service אם נדרש
                        
                        # בחירת קובץ התחלתי
                        initial_video_path = None
                        if session.video_medium_path and os.path.exists(session.video_medium_path):
                            initial_video_path = session.video_medium_path
                            logger.info(f"✅ [WHATSAPP] משתמש בגרסת 720-ish/100MB: {os.path.basename(initial_video_path)}")
                        elif hasattr(session, 'upload_video_path') and session.upload_video_path and os.path.exists(session.upload_video_path):
                            initial_video_path = session.upload_video_path
                            logger.info(f"ℹ️ [WHATSAPP] משתמש בגרסת 1080-ish: {os.path.basename(initial_video_path)}")
                        elif session.video_high_path and os.path.exists(session.video_high_path):
                            initial_video_path = session.video_high_path
                            logger.info(f"ℹ️ [WHATSAPP] משתמש ב-video_high_path: {os.path.basename(initial_video_path)}")
                        else:
                            logger.error("❌ [WHATSAPP] לא נמצא קובץ וידאו לשליחה")
                            raise Exception("No video file available for WhatsApp")
                        
                        # בדיקת גודל (דחיסה תתבצע ב-Node.js service)
                        initial_size = os.path.getsize(initial_video_path)
                        initial_size_mb = initial_size / (1024 * 1024)
                        logger.info(f"ℹ️ [WHATSAPP] גודל וידאו: {initial_size_mb:.2f} MB (דחיסה תתבצע ב-WhatsApp service אם נדרש)")
                        
                        # יצירת עותק עם שם נכון (דחיסה תתבצע ב-Node.js service)
                        original_video_filename = os.path.basename(initial_video_path)
                        target_video_name = build_target_filename(
                            artist_name=session.artist_name,
                            song_name=session.song_name,
                            original_filename=original_video_filename
                        )
                        video_to_send_whatsapp = create_upload_copy(
                            original_path=initial_video_path,
                            new_filename=target_video_name
                        )
                        if video_to_send_whatsapp:
                            session.add_file_for_cleanup(video_to_send_whatsapp)
                            logger.info(f"✅ [WHATSAPP] קובץ מוכן לשליחה: {os.path.basename(video_to_send_whatsapp)}")
                        else:
                            video_to_send_whatsapp = initial_video_path
                            logger.warning(f"⚠️ [WHATSAPP] לא הצליח ליצור עותק, משתמש בקובץ המקורי")
                        
                        # בדיקת גודל סופי
                        video_size = os.path.getsize(video_to_send_whatsapp)
                        video_size_mb = video_size / (1024 * 1024)
                        logger.info(f"✅ [WHATSAPP] גודל וידאו: {video_size_mb:.2f} MB")
                        
                        # הערה: דחיסה ל-70MB תתבצע אוטומטית ב-WhatsApp service אם הקובץ גדול מדי
                        # שולחים את הוידאו בכל מקרה - ה-service ידחוס אם צריך
                        
                        # איסוף רשימת קבוצות: קבועה + מהמאגר
                        whatsapp_video_groups = []
                        
                        # קבוצות מהמאגר (לפי תבנית whatsapp_video) - המשתמש מוסיף בעצמו
                        template_groups = channels_manager.get_template_channels("whatsapp_video", "whatsapp")
                        if template_groups:
                            whatsapp_video_groups.extend(template_groups)
                        
                        # הסרת כפילויות
                        whatsapp_video_groups = list(dict.fromkeys(whatsapp_video_groups))
                        
                        if whatsapp_video_groups:
                            logger.info(f"📱 [WHATSAPP] שלב 3/3 - שולח וידאו ל-{len(whatsapp_video_groups)} קבוצות")
                            
                            whatsapp_video_caption = template_manager.render(
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
                            
                            executor = executor_manager.get_executor()
                            loop = asyncio.get_event_loop()
                            whatsapp = WhatsAppDelivery(dry_run=WHATSAPP_DRY_RUN)
                            
                            try:
                                video_result = await send_to_whatsapp_groups(
                                    whatsapp_delivery=whatsapp,
                                    file_path=video_to_send_whatsapp,
                                    file_type='video',
                                    caption=whatsapp_video_caption,
                                    groups=whatsapp_video_groups,
                                    telegram_user_id=user_id,
                                    telegram_fallback_callback=telegram_fallback_callback,
                                    session=session
                                )
                                
                                # בדיקת תוצאות
                                if video_result.get('success') and video_result.get('sent_to'):
                                    logger.info(f"✅ [WHATSAPP] וידאו נשלח ל-{len(video_result['sent_to'])} קבוצות")
                                    # עדכון מעקב התקדמות
                                    tracker.upload_status['whatsapp']['video'] = True
                                    tracker.upload_progress['whatsapp']['video'] = 100
                                    tracker.upload_results['whatsapp']['video'] = {
                                        "success": True,
                                        "size_mb": round(video_size / (1024*1024), 1),
                                        "sent_to": len(video_result['sent_to'])
                                    }
                                    await tracker.update_status("העלאת קליפ לוואטסאפ", 99, 0)
                                else:
                                    logger.warning(f"⚠️ [WHATSAPP] שליחת וידאו נכשלה: {video_result.get('errors', [])}")
                                    tracker.errors.append({"platform": "whatsapp", "file_type": "video", "error": str(video_result.get('errors', []))})
                                    await tracker.update_status("העלאת קליפ לוואטסאפ - נכשל", 99, 0)
                            finally:
                                if 'whatsapp' in locals():
                                    whatsapp.close()
                        else:
                            logger.info("ℹ️ [WHATSAPP] אין קבוצות לשליחת וידאו - לא נשלח וידאו לוואטסאפ")
                            
                    except Exception as e:
                        logger.error(f"❌ [WHATSAPP] שגיאה בשליחת וידאו: {e}", exc_info=True)
                
            else:
                logger.warning("⚠️ [YOUTUBE] הורדת וידאו נכשלה לאחר 3 ניסיונות - הבוט ממשיך לעבוד")
                tracker.errors.append({"platform": "telegram", "file_type": "video", "error": "הורדת וידאו נכשלה לאחר 3 ניסיונות"})
                await tracker.update_status("הורדה של קליפ לטלגרם (מיוטיוב) - נכשל", 100, 0)
        
        # ========== סיום ==========
        # קביעת הצלחה או כישלון על בסיס העלאות לערוצים ווואטסאפ
        channel_image_success = tracker.upload_status['telegram']['image']
        channel_audio_success = tracker.upload_status['telegram']['audio']
        channel_video_success = not session.need_video or tracker.upload_status['telegram']['video']
        
        all_success = (
            channel_image_success and 
            channel_audio_success and
            channel_video_success and
            (not WHATSAPP_ENABLED or whatsapp_success)
        )
        
        # רשימת פריטים שנכשלו
        failed_items = []
        if not channel_image_success:
            failed_items.append("תמונה לערוץ")
        if not channel_audio_success:
            failed_items.append("MP3 לערוץ")
        if session.need_video and not channel_video_success:
            failed_items.append("וידאו לערוץ")
        if WHATSAPP_ENABLED and not whatsapp_success:
            failed_items.append("וואטסאפ")
        
        # עדכון הודעת סיכום סופית ב-status_msg
        tracker.is_completed = True
        
        # עדכון הודעת הסטטוס הסופית
        status_text = tracker.get_status_text()
        await status_msg.edit_text(status_text)
        
        # מחיקת הודעות ישנות
        from plugins.content_creator.utils import delete_old_messages
        await delete_old_messages(client, session.messages_to_delete, keep_last=status_msg)
        
        # סיכום מפורט (אופציונלי - עם גדלי קבצים)
        # אם רוצים להציג סיכום מפורט במקום הפשוט, ניתן להחליף את ההודעה למעלה ב:
        # detailed_summary = create_summary(upload_results)
        # await message.reply_text(detailed_summary)
        
        logger.info(f"✅ Content processing completed for user {user_id}")
        
        # ========== שליחה למשתמש בטלגרם - רק מה שנכשל בוואטסאפ ==========
        if WHATSAPP_ENABLED:
            failed_whatsapp = []
            
            # בדיקה מה נכשל
            if not tracker.upload_status['whatsapp']['image']:
                failed_whatsapp.append('image')
            if not tracker.upload_status['whatsapp']['audio']:
                failed_whatsapp.append('audio')
            if session.need_video and not tracker.upload_status['whatsapp']['video']:
                failed_whatsapp.append('video')
            
            if failed_whatsapp:
                logger.info(f"📤 [TELEGRAM → USER] שולח קבצים שנכשלו בוואטסאפ למשתמש: {', '.join(failed_whatsapp)}")
                
                try:
                    # תמונה
                    if 'image' in failed_whatsapp and session.processed_image_path and os.path.exists(session.processed_image_path):
                        image_caption = template_manager.render(
                            "whatsapp_image",  # משתמש באותה תבנית
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
                            'title': session.song_name,  # שם השיר - יוצג בגדול בטלגרם
                            'performer': session.artist_name  # שם האמנים - יוצג בקטן בטלגרם
                        }
                        
                        # הוספת משך זמן אם כבר חילצנו אותו
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
                        
                        # Thumbnail לוידאו
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
            else:
                logger.info("ℹ️ [TELEGRAM → USER] כל הקבצים נשלחו בהצלחה לוואטסאפ - אין צורך לשלוח למשתמש")
        
        # ========== מחיקת עותקים אחרי העלאה מוצלחת ==========
        # העותקים כבר ברשימת הניקוי (session.files_to_cleanup)
        # הם יימחקו אוטומטית אחרי 60 שניות
        # אם העלאה נכשלה - העותקים יישארו (ניתן לנסות שוב)
        
        # הערות: העותקים נוצרו עם שמות חדשים ונשלחו
        # אחרי העלאה מוצלחת - הם יימחקו אוטומטית
        logger.info(f"ℹ️ [CLEANUP] עותקי העלאה יימחקו אוטומטית אחרי 60 שניות")
        
        # ========== ניקוי אוטומטי לאחר 120 שניות ==========
        # חשוב: הקבצים נמחקים רק אחרי שהשליחה הושלמה בהצלחה
        # לא מוסיפים את הקבצים ל-cleanup לפני השליחה כדי למנוע מחיקה מוקדמת
        # זמן ארוך יותר (120 שניות) כדי לוודא שהשליחה לוואטסאפ הסתיימה
        schedule_cleanup, _ = _import_cleanup()
        asyncio.create_task(schedule_cleanup(session, delay_seconds=120))
        
        # איפוס הסשן (אבל לא מוחקים עדיין את הקבצים)
        session.update_state(UserState.IDLE)
        
    except Exception as e:
        logger.error(f"❌ Error processing content: {e}", exc_info=True)
        if 'tracker' in locals():
            tracker.errors.append({"platform": "general", "file_type": "processing", "error": str(e)})
        try:
            error_text = (
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש"
            )
            await status_msg.edit_text(error_text)
        except:
            from plugins.start import get_main_keyboard
            await message.reply_text(
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש",
                reply_markup=get_main_keyboard()
            )
        
        # ניקוי מיידי במקרה של שגיאה
        _, cleanup_session_files = _import_cleanup()
        await cleanup_session_files(session)


# ========== עיבוד אינסטגרם ==========

async def process_instagram_upload(client: Client, message: Message, session, status_msg: Message):
    """
    מעבד העלאה מאינסטגרם:
    1. מעלה את הקובץ שהורד לטלגרם ולוואטסאפ
    2. משתמש בתבניות telegram_instagram ו-whatsapp_instagram
    """
    user_id = session.user_id
    
    # ========== Initialize Progress Tracker ==========
    tracker = ProgressTracker(session, status_msg)
    
    # ========== מעקב התקדמות ==========
    upload_status = {
        "telegram": False,
        "whatsapp": False
    }
    
    # ========== מעקב פעולות נוכחיות ==========
    current_operation = ""
    current_operation_percent = 0
    is_completed = False
    
    def get_status_text():
        """מחזיר טקסט סטטוס מעודכן בתבנית החדשה"""
        text = ""
        
        # כותרת סיום (רק אם הושלם)
        if is_completed:
            text += "✅ **משימה הושלמה**\n\n"
        
        # ספירת קבצים מוצלחים
        telegram_count = 1 if upload_status['telegram'] else 0
        whatsapp_count = 1 if upload_status['whatsapp'] else 0
        
        text += f"📤 **טלגרם:** {telegram_count}/1\n"
        text += f"📱 **וואטסאפ:** {whatsapp_count}/1\n\n"
        
        # פעולה נוכחית (רק אם לא הושלם)
        if not is_completed and current_operation:
            text += f"{current_operation} {current_operation_percent}%\n"
            text += f"{create_progress_bar(current_operation_percent)}\n\n"
        
        # חישוב אחוז התקדמות כללי
        total_items = 2
        completed_items = sum([1 if upload_status['telegram'] else 0, 1 if upload_status['whatsapp'] else 0])
        overall_percent = int((completed_items / total_items) * 100) if total_items > 0 else 0
        text += f"{create_progress_bar(overall_percent)}\n"
        
        return text
    
    async def update_status(operation_name="", percent=0, emoji_index=0):
        """עדכן את הודעת הסטטוס עם התבנית החדשה"""
        nonlocal current_operation, current_operation_percent
        
        # עדכון הפעולה הנוכחית - שימוש במצבים המבוקשים
        if operation_name:
            current_operation = operation_name
            # המרה לאחוז הקרוב ביותר מבין המצבים המבוקשים
            current_operation_percent = get_progress_stage(percent)
        
        status_text = get_status_text()
        try:
            await status_msg.edit_text(status_text)
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
    
    try:
        # בדיקה שיש קובץ
        if not session.instagram_file_path or not os.path.exists(session.instagram_file_path):
            raise Exception("Instagram file not found")
        
        # בדיקה שיש טקסט (מחמירה - גם לא ריק)
        if not session.instagram_text or not session.instagram_text.strip():
            logger.error(f"❌ Instagram text is missing or empty for user {user_id}")
            logger.error(f"  Session state: {session.state}")
            logger.error(f"  Instagram URL: {session.instagram_url}")
            logger.error(f"  Instagram file path: {session.instagram_file_path}")
            raise Exception("Instagram text not found or empty")
        
        # קביעת סוג הקובץ
        media_type = session.instagram_media_type or "video"
        file_path = session.instagram_file_path
        
        logger.info(f"📤 Processing Instagram upload for user {user_id}")
        logger.info(f"  File: {file_path}")
        logger.info(f"  Media type: {media_type}")
        logger.info(f"  Text: {session.instagram_text[:100]}...")
        
        # יצירת טקסט מהתבנית
        try:
            telegram_caption = template_manager.render(
                "telegram_instagram",
                text=session.instagram_text
            )
            logger.info(f"✅ Telegram caption rendered: {telegram_caption[:100]}...")
            logger.info(f"📝 Telegram caption length: {len(telegram_caption)} characters")
            
            # בדיקה שה-caption לא ריק
            if not telegram_caption or not telegram_caption.strip():
                logger.warning(f"⚠️ Telegram caption is empty! Template might be empty or text is empty")
                telegram_caption = session.instagram_text  # fallback לטקסט המקורי
                logger.info(f"📝 Using original text as fallback: {telegram_caption[:100]}...")
        except Exception as e:
            logger.error(f"❌ Error rendering telegram caption: {e}")
            # fallback לטקסט המקורי אם יש בעיה
            telegram_caption = session.instagram_text if session.instagram_text else ""
            logger.info(f"📝 Using original text as fallback due to error: {telegram_caption[:100]}...")
        
        try:
            whatsapp_caption = template_manager.render(
                "whatsapp_instagram",
                text=session.instagram_text
            )
            logger.info(f"✅ WhatsApp caption rendered: {whatsapp_caption[:100]}...")
        except Exception as e:
            logger.error(f"❌ Error rendering whatsapp caption: {e}")
            raise Exception(f"Error rendering whatsapp caption: {str(e)}")
        
        # עדכון סטטוס
        if media_type == "video":
            await tracker.update_status("הורדה של קליפ מאינסטגרם", 0, 0)
        else:
            await tracker.update_status("הורדה של תמונה מאינסטגרם", 0, 0)
        
        # ========== העלאה לטלגרם ==========
        telegram_channels = []
        
        # ערוצים מתבנית - המשתמש מוסיף בעצמו
        template_channels = channels_manager.get_template_channels(
            "telegram_instagram", "telegram"
        )
        if template_channels:
            telegram_channels.extend(template_channels)
        telegram_channels = list(dict.fromkeys(telegram_channels))  # הסרת כפילויות
        
        telegram_success = False
        # שליחה רק אם יש ערוצים מהמאגר
        if telegram_channels:
            logger.info(f"📤 [TELEGRAM] שולח {media_type} ל-{len(telegram_channels)} ערוצים")
            
            if media_type == "video":
                await tracker.update_status("העלאת קליפ לטלגרם", 50, 0)
            else:
                await tracker.update_status("העלאת תמונה לטלגרם", 50, 0)
            
            # קביעת file_type לטלגרם
            if media_type == "video":
                telegram_file_type = "video"
            else:
                telegram_file_type = "photo"
            
            try:
                telegram_result = await send_to_telegram_channels(
                    client=client,
                    file_path=file_path,
                    file_type=telegram_file_type,
                    caption=telegram_caption,
                    channels=telegram_channels,
                    first_channel_peer_id_b64=telegram_channels[0] if telegram_channels else None,
                    protected_channels=[]
                )
                
                if telegram_result.get('success'):
                    telegram_success = True
                    upload_status['telegram'] = True
                    logger.info(f"✅ [TELEGRAM] נשלח ל-{len(telegram_result.get('sent_to', []))} ערוצים")
                    await tracker.update_status("העלאת קליפ לטלגרם" if media_type == "video" else "העלאת תמונה לטלגרם", 67, 0)
                else:
                    error_msg = telegram_result.get('error', 'Unknown error')
                    tracker.errors.append({"platform": "telegram", "file_type": media_type, "error": error_msg})
                    logger.error(f"❌ [TELEGRAM] שגיאה: {error_msg}")
                    await tracker.update_status("העלאת קליפ לטלגרם - נכשל" if media_type == "video" else "העלאת תמונה לטלגרם - נכשל", 67, 0)
            except Exception as e:
                tracker.errors.append({"platform": "telegram", "file_type": media_type, "error": str(e)})
                logger.error(f"❌ [TELEGRAM] שגיאה בהעלאה: {e}", exc_info=True)
                await tracker.update_status("העלאת קליפ לטלגרם - נכשל" if media_type == "video" else "העלאת תמונה לטלגרם - נכשל", 67, 0)
        else:
            logger.info("ℹ️ [TELEGRAM] אין ערוצים להעלאה")
        
        # ========== העלאה לוואטסאפ ==========
        whatsapp_success = False
        if WHATSAPP_ENABLED:
            whatsapp_groups = []
            
            # קבוצות מתבנית - המשתמש מוסיף בעצמו
            template_groups = channels_manager.get_template_channels(
                "whatsapp_instagram", "whatsapp"
            )
            if template_groups:
                whatsapp_groups.extend(template_groups)
            whatsapp_groups = list(dict.fromkeys(whatsapp_groups))  # הסרת כפילויות
            
            # שליחה רק אם יש קבוצות מהמאגר
            if whatsapp_groups:
                logger.info(f"📱 [WHATSAPP] שולח {media_type} ל-{len(whatsapp_groups)} קבוצות")
                
                if media_type == "video":
                    await tracker.update_status("העלאת קליפ לוואטסאפ", 79, 0)
                else:
                    await tracker.update_status("העלאת תמונה לוואטסאפ", 79, 0)
                
                # קביעת file_type לוואטסאפ
                if media_type == "video":
                    whatsapp_file_type = "video"
                else:
                    whatsapp_file_type = "image"
                
                try:
                    executor = executor_manager.get_executor()
                    loop = asyncio.get_event_loop()
                    
                    # ניסיון לאתחל WhatsApp - אם נכשל, נמשיך בלי וואטסאפ
                    try:
                        whatsapp = WhatsAppDelivery(dry_run=WHATSAPP_DRY_RUN)
                    except Exception as whatsapp_init_error:
                        logger.warning(f"⚠️ [WHATSAPP] לא ניתן לאתחל WhatsApp: {whatsapp_init_error}")
                        logger.info("💡 [WHATSAPP] המשך בלי וואטסאפ - נשלח רק לטלגרם")
                        tracker.errors.append({
                            "platform": "whatsapp", 
                            "file_type": media_type, 
                            "error": f"WhatsApp service not ready: {str(whatsapp_init_error)}"
                        })
                        whatsapp = None
                    
                    # אם WhatsApp לא זמין, דלג על שליחה
                    if whatsapp is None:
                        logger.info("ℹ️ [WHATSAPP] דילוג על שליחה - WhatsApp לא זמין")
                    else:
                        # Telegram Fallback Callback
                        def telegram_fallback_callback(user_id: int, file_path: str, template_text: str, failure_summary: str) -> bool:
                            try:
                                logger.info(f"📨 [TELEGRAM FALLBACK] Sending failed file to user {user_id}")
                                ext = os.path.splitext(file_path)[1].lower()
                                error_msg = f"⚠️ **העלאה לוואטסאפ נכשלה**\n\n{failure_summary}\n\n{template_text}"
                                
                                async def send_to_telegram():
                                    try:
                                        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                                            await client.send_video(user_id, file_path, caption=error_msg)
                                        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                            await client.send_photo(user_id, file_path, caption=error_msg)
                                        else:
                                            await client.send_document(user_id, file_path, caption=error_msg)
                                        return True
                                    except Exception as e:
                                        logger.error(f"❌ [TELEGRAM FALLBACK] Error: {e}")
                                        return False
                                
                                # הרצה ב-async
                                asyncio.create_task(send_to_telegram())
                                return True
                            except Exception as e:
                                logger.error(f"❌ [TELEGRAM FALLBACK] Error in callback: {e}")
                                return False
                        
                        whatsapp_result = await send_to_whatsapp_groups(
                            whatsapp_delivery=whatsapp,
                            file_path=file_path,
                            file_type=whatsapp_file_type,
                            caption=whatsapp_caption,
                            groups=whatsapp_groups,
                            telegram_user_id=user_id,
                            telegram_fallback_callback=telegram_fallback_callback,
                            session=session
                        )
                        
                        if whatsapp_result.get('success'):
                            whatsapp_success = True
                            upload_status['whatsapp'] = True
                            logger.info(f"✅ [WHATSAPP] נשלח ל-{len(whatsapp_result.get('sent_to', []))} קבוצות")
                            await tracker.update_status("העלאת קליפ לוואטסאפ" if media_type == "video" else "העלאת תמונה לוואטסאפ", 85, 0)
                        else:
                            error_msgs = whatsapp_result.get('errors', [])
                            for error_msg in error_msgs:
                                tracker.errors.append({"platform": "whatsapp", "file_type": media_type, "error": error_msg})
                            logger.error(f"❌ [WHATSAPP] שגיאות: {error_msgs}")
                            await tracker.update_status("העלאת קליפ לוואטסאפ - נכשל" if media_type == "video" else "העלאת תמונה לוואטסאפ - נכשל", 85, 0)
                except Exception as e:
                    tracker.errors.append({"platform": "whatsapp", "file_type": media_type, "error": str(e)})
                    logger.error(f"❌ [WHATSAPP] שגיאה בהעלאה: {e}", exc_info=True)
            else:
                logger.info("ℹ️ [WHATSAPP] אין קבוצות להעלאה - לא נשלח תוכן לוואטסאפ")
        else:
            logger.info("ℹ️ [WHATSAPP] וואטסאפ לא מופעל")
        
        # ========== סיכום ==========
        is_completed = True
        success_count = sum([telegram_success, whatsapp_success])
        
        # עדכון הודעת הסטטוס הסופית
        status_text = get_status_text()
        await status_msg.edit_text(status_text)
        
        # מחיקת הודעות ישנות
        from plugins.content_creator.utils import delete_old_messages
        await delete_old_messages(client, session.messages_to_delete, keep_last=status_msg)
        
        # ========== ניקוי אוטומטי ==========
        schedule_cleanup, _ = _import_cleanup()
        asyncio.create_task(schedule_cleanup(session, delay_seconds=120))
        
        # איפוס הסשן
        session.update_state(UserState.IDLE)
        
    except Exception as e:
        logger.error(f"❌ Error processing Instagram upload: {e}", exc_info=True)
        if 'tracker' in locals():
            tracker.errors.append({"platform": "general", "file_type": "processing", "error": str(e)})
        try:
            await status_msg.edit_text(
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש"
            )
        except:
            from plugins.start import get_main_keyboard
            await message.reply_text(
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש",
                reply_markup=get_main_keyboard()
            )
        
        # ניקוי מיידי במקרה של שגיאה
        _, cleanup_session_files = _import_cleanup()
        await cleanup_session_files(session)


# ========== עיבוד וידאו בלבד ==========

async def process_video_only(client: Client, message: Message, session, status_msg: Message):
    """
    מעבד רק וידאו (ללא תמונה ו-MP3):
    1. מוריד וידאו מיוטיוב
    2. מעלה אותו לטלגרם ולוואטסאפ
    3. משתמש בתבניות telegram_video ו-whatsapp_video
    """
    user_id = session.user_id
    
    # ========== Initialize Progress Tracker ==========
    tracker = ProgressTracker(session, status_msg)
    
    # ========== מעקב התקדמות מפורט ==========
    upload_status = {
        "telegram": {"video": False},
        "whatsapp": {"video": False}
    }
    
    upload_progress = {
        "telegram": {"video": 0},
        "whatsapp": {"video": 0}
    }
    
    # ========== מעקב פעולות נוכחיות ==========
    current_operation = ""
    current_operation_percent = 0
    is_completed = False
    
    def get_status_text():
        """מחזיר טקסט סטטוס מעודכן בתבנית החדשה"""
        text = ""
        
        # כותרת סיום (רק אם הושלם)
        if is_completed:
            text += "✅ **משימה הושלמה**\n\n"
        
        # ספירת קבצים מוצלחים
        telegram_count = 1 if upload_status['telegram']['video'] else 0
        whatsapp_count = 1 if upload_status['whatsapp']['video'] else 0
        
        text += f"📤 **טלגרם:** {telegram_count}/1\n"
        text += f"📱 **וואטסאפ:** {whatsapp_count}/1\n\n"
        
        # פעולה נוכחית (רק אם לא הושלם)
        if not is_completed and current_operation:
            text += f"{current_operation} {current_operation_percent}%\n"
            text += f"{create_progress_bar(current_operation_percent)}\n\n"
        
        # חישוב אחוז התקדמות כללי
        total_items = 2  # רק וידאו לטלגרם ווואטסאפ
        completed_items = 0
        for platform in ['telegram', 'whatsapp']:
            if upload_status[platform]['video']:
                completed_items += 1
            elif upload_progress[platform]['video'] > 0:
                completed_items += upload_progress[platform]['video'] / 100
        
        overall_percent = int((completed_items / total_items) * 100) if total_items > 0 else 0
        text += f"{create_progress_bar(overall_percent)}\n"
        
        return text
    
    async def update_status(operation_name="", percent=0, emoji_index=0):
        """עדכן את הודעת הסטטוס עם התבנית החדשה"""
        nonlocal current_operation, current_operation_percent
        
        # עדכון הפעולה הנוכחית
        if operation_name:
            current_operation = operation_name
            current_operation_percent = percent
        
        status_text = get_status_text()
        try:
            await status_msg.edit_text(status_text)
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
    
    try:
        # ========== שלב 1: הורדת וידאו מיוטיוב ==========
        await tracker.update_status("הורדה של קליפ לטלגרם (מיוטיוב)", 0, 0)
        logger.info(f"📥 Starting YouTube video download for user {user_id}")
        logger.info(f"  URL: {session.youtube_url}")
        
        # שימוש ב-video_downloader החדש
        async def update_status_wrapper(operation_name, percent, emoji_index=0):
            await tracker.update_status(operation_name, percent, emoji_index)
        
        video_success = await download_video_with_retry(
            session=session,
            upload_progress=tracker.upload_progress,
            update_status_func=update_status_wrapper,
            errors=tracker.errors
        )
        
        if not video_success or not session.video_high_path or not os.path.exists(session.video_high_path):
            raise Exception("הורדת וידאו נכשלה")
        
        # ========== שלב 2: הכנת וידאו להעלאה ==========
        await tracker.update_status("עיבוד קליפ טלגרם", 50, 0)
        logger.info("✅ [YOUTUBE] הורדת וידאו הושלמה, מתחיל העלאה!")
        
        # בניית שם קובץ וידאו לפני העלאה
        original_video_filename = os.path.basename(session.video_high_path)
        target_video_name = build_target_filename(
            artist_name=session.artist_name,
            song_name=session.song_name,
            original_filename=original_video_filename
        )
        
        # יצירת עותק של הוידאו עם שם חדש להעלאה
        upload_video_path = create_upload_copy(
            original_path=session.video_high_path,
            new_filename=target_video_name
        )
        if not upload_video_path:
            raise Exception("Failed to create video copy for upload")
        
        session.upload_video_path = upload_video_path
        session.add_file_for_cleanup(upload_video_path)
        logger.info(f"✅ Created video copy for upload: {target_video_name}")
        
        # בדיקת גודל
        video_size_mb = os.path.getsize(upload_video_path) / (1024 * 1024)
        logger.info(f"ℹ️ [TELEGRAM] גודל וידאו: {video_size_mb:.2f} MB")
        
        if video_size_mb > TELEGRAM_MAX_FILE_SIZE_MB:
            raise Exception(f"וידאו גדול מדי ל-Telegram: {video_size_mb:.2f}MB > {TELEGRAM_MAX_FILE_SIZE_MB}MB")
        
        # הכנת thumbnail ו-dimensions לוידאו
        video_thumb_path = None
        video_width = None
        video_height = None
        
        try:
            logger.info("📐 [TELEGRAM] מחלץ ממדי וידאו...")
            dimensions = await get_video_dimensions(session.video_high_path)
            if dimensions:
                video_width, video_height = dimensions
                logger.info(f"✅ [TELEGRAM] ממדי וידאו: {video_width}x{video_height}")
            
            logger.info("🖼️ [YOUTUBE] מוריד thumbnail...")
            raw_thumbnail = await fetch_youtube_thumbnail(
                url=session.youtube_url,
                cookies_path="cookies.txt"
            )
            
            if raw_thumbnail:
                session.add_file_for_cleanup(raw_thumbnail)
                logger.info(f"✅ [YOUTUBE] Thumbnail הורד: {raw_thumbnail}")
                
                if video_width and video_height:
                    aspect_ratio = video_width / video_height
                    logger.info(f"🎨 [TELEGRAM] מכין thumbnail (aspect ratio: {aspect_ratio:.3f})...")
                    
                    video_thumb_path = await prepare_telegram_thumbnail(
                        input_image_path=raw_thumbnail,
                        video_aspect_ratio=aspect_ratio
                    )
                    
                    if video_thumb_path:
                        session.add_file_for_cleanup(video_thumb_path)
                        logger.info(f"✅ [TELEGRAM] Thumbnail מוכן: {video_thumb_path}")
        except Exception as e:
            logger.error(f"❌ [TELEGRAM] שגיאה בהכנת thumbnail/dimensions: {e}", exc_info=True)
        
        # ========== שלב 3: העלאה לטלגרם ==========
        await tracker.update_status("העלאת קליפ לטלגרם", 67, 0)
        
        bot = client
        
        # נסיון למצוא את היוזרבוט (לקבצים גדולים)
        userbot = None
        try:
            # אם יש userbot פעיל, נשתמש בו לקבצים גדולים
            context = get_context()
            userbot = context.get_userbot()
            if userbot:
                logger.info("✅ [TELEGRAM] Userbot זמין לקבצים גדולים")
            else:
                logger.warning("⚠️ [TELEGRAM] Userbot לא זמין - משתמש בבוט רגיל")
        except Exception as e:
            logger.warning(f"⚠️ [TELEGRAM] Could not access userbot: {e}")
        
        if PUBLISH_TO_CHANNELS:
            try:
                # שימוש ב-Userbot לפרסום בערוצים (כמו שהיה מקודם)
                channel_client = userbot if userbot else bot
                client_type = "Userbot" if userbot else "Bot"
                logger.info(f"ℹ️ [TELEGRAM → CHANNEL] משתמש ב-{client_type} לפרסום")
                
                # איסוף רשימת ערוצים: רק מהמאגר (המשתמש מוסיף בעצמו)
                telegram_video_channels = []
                
                # ערוצים מהמאגר
                template_channels = channels_manager.get_template_channels("telegram_video", "telegram")
                if template_channels:
                    telegram_video_channels.extend(template_channels)
                telegram_video_channels = list(dict.fromkeys(telegram_video_channels))
                
                # שליחה רק אם יש ערוצים מהמאגר
                if telegram_video_channels:
                    logger.info(f"📢 [TELEGRAM → CHANNEL] מעלה וידאו ל-{len(telegram_video_channels)} ערוצים")
                    logger.info(f"📋 [TELEGRAM → CHANNEL] רשימת ערוצים: {telegram_video_channels}")
                    
                    logger.info(f"📋 [TELEGRAM → CHANNEL] רשימת ערוצים (peer_id_b64): {[ch[:20] + '...' if len(ch) > 20 else ch for ch in telegram_video_channels]}")
                    
                    # שימוש בתבנית telegram_video - מעבירים את כל המשתנים (גם אם לא כולם יעבדו)
                    # יצירת credits_text גם אם אין את כל הפרטים
                    credits_text = session.get_credits_text() if hasattr(session, 'get_credits_text') else ""
                    
                    channel_video_caption = template_manager.render(
                        "telegram_video",
                        song_name=session.song_name or "",
                        artist_name=session.artist_name or "",
                        year=session.year if hasattr(session, 'year') and session.year else "",
                        composer=session.composer if hasattr(session, 'composer') and session.composer else "",
                        arranger=session.arranger if hasattr(session, 'arranger') and session.arranger else "",
                        mixer=session.mixer if hasattr(session, 'mixer') and session.mixer else "",
                        credits=credits_text,
                        youtube_url=session.youtube_url or ""
                    )
                    
                    video_kwargs = {}
                    if video_width and video_height:
                        video_kwargs['width'] = video_width
                        video_kwargs['height'] = video_height
                    
                    if video_thumb_path and os.path.exists(video_thumb_path):
                        video_kwargs['thumb'] = video_thumb_path
                    
                    logger.info(f"📤 [TELEGRAM → CHANNEL] מתחיל שליחה ל-{len(telegram_video_channels)} ערוצים...")
                    video_result = await send_to_telegram_channels(
                        client=channel_client,
                        file_path=session.upload_video_path,
                        file_type='video',
                        caption=channel_video_caption,
                        channels=telegram_video_channels,
                        first_channel_peer_id_b64=telegram_video_channels[0] if telegram_video_channels else None,
                        protected_channels=[],
                        **video_kwargs
                    )
                    
                    if video_result['success']:
                        logger.info(f"✅ [TELEGRAM → CHANNEL] וידאו נשלח ל-{len(video_result['sent_to'])} ערוצים")
                        tracker.upload_status['telegram']['video'] = True
                        tracker.upload_progress['telegram']['video'] = 100
                        await tracker.update_status("העלאת קליפ לטלגרם", 79, 0)
                    else:
                        error_msg = video_result.get('error', 'Unknown error')
                        logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בשליחת וידאו: {error_msg}")
                        tracker.errors.append({"platform": "telegram", "file_type": "video", "error": str(error_msg)})
                        # אם השליחה לטלגרם נכשלה, נוודא שהקובץ עדיין קיים לפני שליחה ל-WhatsApp
                        # (יכול להיות שהקובץ נמחק או עדיין בשימוש)
                        if session.upload_video_path and not os.path.exists(session.upload_video_path):
                            logger.warning(f"⚠️ [TELEGRAM → WHATSAPP] קובץ upload_video_path נמחק או לא קיים: {session.upload_video_path}")
                            # נסיר את upload_video_path מהרשימה כדי שהקוד ינסה להשתמש ב-video_medium_path או video_high_path
                            session.upload_video_path = None
                else:
                    logger.info("ℹ️ [TELEGRAM → CHANNEL] אין ערוצים להעלאת וידאו")
            except Exception as e:
                logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בפרסום וידאו לערוצים: {e}", exc_info=True)
                tracker.errors.append({"platform": "telegram", "file_type": "video", "error": str(e)})
                # אם השליחה לטלגרם נכשלה, נוודא שהקובץ עדיין קיים לפני שליחה ל-WhatsApp
                if session.upload_video_path and not os.path.exists(session.upload_video_path):
                    logger.warning(f"⚠️ [TELEGRAM → WHATSAPP] קובץ upload_video_path נמחק או לא קיים: {session.upload_video_path}")
                    # נסיר את upload_video_path מהרשימה כדי שהקוד ינסה להשתמש ב-video_medium_path או video_high_path
                    session.upload_video_path = None
        
        # ========== שלב 4: העלאה לוואטסאפ ==========
        if WHATSAPP_ENABLED:
            try:
                await tracker.update_status("עיבוד קליפ וואטסאפ", 80, 0)
                
                # בחירת קובץ התחלתי - בודקים קודם את video_medium_path (הכי מתאים לוואטסאפ)
                # ואז את video_high_path (אם אין medium), ואז upload_video_path רק אם הוא עדיין קיים
                initial_video_path = None
                if session.video_medium_path and os.path.exists(session.video_medium_path):
                    initial_video_path = session.video_medium_path
                    logger.info(f"✅ [WHATSAPP] משתמש בגרסת 720-ish/100MB: {os.path.basename(initial_video_path)}")
                elif session.video_high_path and os.path.exists(session.video_high_path):
                    initial_video_path = session.video_high_path
                    logger.info(f"ℹ️ [WHATSAPP] משתמש ב-video_high_path: {os.path.basename(initial_video_path)}")
                elif session.upload_video_path and os.path.exists(session.upload_video_path):
                    initial_video_path = session.upload_video_path
                    logger.info(f"ℹ️ [WHATSAPP] משתמש בגרסת 1080-ish: {os.path.basename(initial_video_path)}")
                else:
                    # בדיקה מפורטת יותר - אולי הקובץ עדיין בשימוש
                    logger.warning(f"⚠️ [WHATSAPP] לא נמצא קובץ וידאו זמין. בודקים שוב...")
                    logger.warning(f"  video_medium_path: {session.video_medium_path} (קיים: {os.path.exists(session.video_medium_path) if session.video_medium_path else False})")
                    logger.warning(f"  video_high_path: {session.video_high_path} (קיים: {os.path.exists(session.video_high_path) if session.video_high_path else False})")
                    logger.warning(f"  upload_video_path: {session.upload_video_path} (קיים: {os.path.exists(session.upload_video_path) if session.upload_video_path else False})")
                    raise Exception("No video file available for WhatsApp")
                
                # יצירת עותק עם שם נכון
                original_video_filename = os.path.basename(initial_video_path)
                target_video_name = build_target_filename(
                    artist_name=session.artist_name,
                    song_name=session.song_name,
                    original_filename=original_video_filename
                )
                video_to_send_whatsapp = create_upload_copy(
                    original_path=initial_video_path,
                    new_filename=target_video_name
                )
                if video_to_send_whatsapp:
                    # לא מוסיפים ל-cleanup עכשיו - נמחק רק אחרי שהשליחה לכל הקבוצות תסתיים
                    # session.add_file_for_cleanup(video_to_send_whatsapp)  # הוסר - יוסיף בסיום השליחה
                    logger.info(f"✅ [WHATSAPP] קובץ מוכן לשליחה: {os.path.basename(video_to_send_whatsapp)}")
                else:
                    video_to_send_whatsapp = initial_video_path
                
                # איסוף רשימת קבוצות
                whatsapp_video_groups = []
                
                # קבוצות מהמאגר - המשתמש מוסיף בעצמו
                template_groups = channels_manager.get_template_channels("whatsapp_video", "whatsapp")
                if template_groups:
                    whatsapp_video_groups.extend(template_groups)
                whatsapp_video_groups = list(dict.fromkeys(whatsapp_video_groups))
                
                # שליחה תמיד אם יש קבוצה קבועה, גם אם אין קבוצות ידניות
                if whatsapp_video_groups:
                    logger.info(f"📱 [WHATSAPP] שולח וידאו ל-{len(whatsapp_video_groups)} קבוצות")
                    
                    # שימוש בתבנית whatsapp_video - מעבירים את כל המשתנים (גם אם לא כולם יעבדו)
                    # יצירת credits_text גם אם אין את כל הפרטים
                    credits_text = session.get_credits_text() if hasattr(session, 'get_credits_text') else ""
                    
                    whatsapp_video_caption = template_manager.render(
                        "whatsapp_video",
                        song_name=session.song_name or "",
                        artist_name=session.artist_name or "",
                        year=session.year if hasattr(session, 'year') and session.year else "",
                        composer=session.composer if hasattr(session, 'composer') and session.composer else "",
                        arranger=session.arranger if hasattr(session, 'arranger') and session.arranger else "",
                        mixer=session.mixer if hasattr(session, 'mixer') and session.mixer else "",
                        credits=credits_text,
                        youtube_url=session.youtube_url or ""
                    )
                    
                    executor = executor_manager.get_executor()
                    loop = asyncio.get_event_loop()
                    whatsapp = WhatsAppDelivery(dry_run=WHATSAPP_DRY_RUN)
                    
                    # Telegram Fallback Callback
                    def telegram_fallback_callback(user_id: int, file_path: str, template_text: str, failure_summary: str) -> bool:
                        try:
                            logger.info(f"📨 [TELEGRAM FALLBACK] Sending failed file to user {user_id}")
                            ext = os.path.splitext(file_path)[1].lower()
                            error_msg = f"⚠️ **העלאה לוואטסאפ נכשלה**\n\n{failure_summary}\n\n{template_text}"
                            
                            async def send_to_telegram():
                                try:
                                    if ext in ['.mp4', '.avi', '.mov', '.mkv']:
                                        await client.send_video(user_id, file_path, caption=error_msg)
                                    else:
                                        await client.send_document(user_id, file_path, caption=error_msg)
                                    return True
                                except Exception as e:
                                    logger.error(f"❌ [TELEGRAM FALLBACK] Error: {e}", exc_info=True)
                                    return False
                            
                            result = asyncio.run_coroutine_threadsafe(send_to_telegram(), asyncio.get_event_loop())
                            return result.result(timeout=30)
                        except Exception as e:
                            logger.error(f"❌ [TELEGRAM FALLBACK] Callback error: {e}", exc_info=True)
                            return False
                    
                    try:
                        video_result = await send_to_whatsapp_groups(
                            whatsapp_delivery=whatsapp,
                            file_path=video_to_send_whatsapp,
                            file_type='video',
                            caption=whatsapp_video_caption,
                            groups=whatsapp_video_groups,
                            telegram_user_id=user_id,
                            telegram_fallback_callback=telegram_fallback_callback,
                            session=session
                        )
                        
                        if video_result.get('success') and video_result.get('sent_to'):
                            logger.info(f"✅ [WHATSAPP] וידאו נשלח ל-{len(video_result['sent_to'])} קבוצות")
                            tracker.upload_status['whatsapp']['video'] = True
                            tracker.upload_progress['whatsapp']['video'] = 100
                            await tracker.update_status("וידאו נשלח לוואטסאפ", 100, 1)
                        else:
                            logger.warning(f"⚠️ [WHATSAPP] שליחת וידאו נכשלה: {video_result.get('errors', [])}")
                            tracker.errors.append({"platform": "whatsapp", "file_type": "video", "error": str(video_result.get('errors', []))})
                            await tracker.update_status("שליחת וידאו נכשלה", 100, 0)
                    finally:
                        # השליחה לכל הקבוצות הסתיימה - עכשיו אפשר להוסיף את הקובץ ל-cleanup
                        if video_to_send_whatsapp and os.path.exists(video_to_send_whatsapp):
                            session.add_file_for_cleanup(video_to_send_whatsapp)
                            logger.debug(f"🗑️ [WHATSAPP] קובץ נוסף ל-cleanup: {os.path.basename(video_to_send_whatsapp)}")
                        if 'whatsapp' in locals():
                            whatsapp.close()
                else:
                    logger.info("ℹ️ [WHATSAPP] אין קבוצות לשליחת וידאו")
            except Exception as e:
                logger.error(f"❌ [WHATSAPP] שגיאה בשליחת וידאו: {e}", exc_info=True)
                tracker.errors.append({"platform": "whatsapp", "file_type": "video", "error": str(e)})
        
        # ========== סיום ==========
        all_success = (
            tracker.upload_status['telegram']['video'] and
            (not WHATSAPP_ENABLED or tracker.upload_status['whatsapp']['video'])
        )
        
        tracker.is_completed = True
        
        status_text = tracker.get_status_text()
        await status_msg.edit_text(status_text)
        
        # מחיקת הודעות ישנות
        from plugins.content_creator.utils import delete_old_messages
        await delete_old_messages(client, session.messages_to_delete, keep_last=status_msg)
        
        logger.info(f"✅ Video-only processing completed for user {user_id}")
        
        # ניקוי אוטומטי לאחר 120 שניות (יותר זמן כדי לוודא שהשליחה לכל הקבוצות הסתיימה)
        # השליחה ל-WhatsApp היא await, אז היא ממתינה עד שהשליחה לכל הקבוצות תסתיים
        # אבל נוסיף עוד זמן כדי לוודא שהקבצים לא בשימוש
        schedule_cleanup, _ = _import_cleanup()
        asyncio.create_task(schedule_cleanup(session, delay_seconds=120))
        
        # איפוס הסשן
        session.update_state(UserState.IDLE)
        
    except Exception as e:
        logger.error(f"❌ Error processing video-only content: {e}", exc_info=True)
        if 'tracker' in locals():
            tracker.errors.append({"platform": "general", "file_type": "processing", "error": str(e)})
        try:
            error_text = (
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש"
            )
            await status_msg.edit_text(error_text)
        except:
            from plugins.start import get_main_keyboard
            await message.reply_text(
                f"❌ **שגיאה בעיבוד!**\n\n"
                f"פרטי שגיאה: {str(e)}\n\n"
                f"שלח /cancel להתחלה מחדש",
                reply_markup=get_main_keyboard()
            )
        
        _, cleanup_session_files = _import_cleanup()
        await cleanup_session_files(session)


async def schedule_instagram_timeout(session, status_msg: Message, delay_seconds: int = 300):
    """
    מתזמן ניקוי אוטומטי של קבצי אינסטגרם אם המשתמש לא שלח טקסט תוך 5 דקות
    הטיימר מתחיל מהרגע שהקישור נשלח, לא מהרגע שההורדה הסתיימה
    """
    try:
        await asyncio.sleep(delay_seconds)
        
        # בדיקה אם המשתמש עדיין במצב המתנה לטקסט ולא שלח טקסט
        # וגם בדיקה שהטיימר לא בוטל (אם המשתמש שלח טקסט, המצב ישתנה)
        if (session.state == UserState.WAITING_INSTAGRAM_TEXT and 
            not session.instagram_text):
            
            logger.info(f"⏰ Instagram timeout for user {session.user_id} - cleaning up after 5 minutes")
            
            try:
                await status_msg.edit_text(
                    "⏰ **זמן ההמתנה פג!**\n\n"
                    "לא התקבל טקסט תוך 5 דקות משליחת הקישור.\n"
                    "הקבצים נמחקו והתהליך בוטל.\n\n"
                    "תוכל להתחיל מחדש על ידי שליחת קישור אינסטגרם."
                )
            except:
                pass  # ההודעה כבר נמחקה או לא קיימת
            
            # ניקוי הקבצים
            _, cleanup_session_files = _import_cleanup()
            await cleanup_session_files(session)
            
            # איפוס המצב
            session.update_state(UserState.IDLE)
            session.instagram_url = None
            session.instagram_file_path = None
            session.instagram_media_type = None
            session.instagram_text = None
            session.instagram_download_time = None
            
            logger.info(f"✅ Instagram session cleaned up for user {session.user_id} due to timeout")
            
    except asyncio.CancelledError:
        logger.debug(f"Instagram timeout task cancelled for user {session.user_id}")
    except Exception as e:
        logger.error(f"❌ Error in Instagram timeout task: {e}", exc_info=True)



