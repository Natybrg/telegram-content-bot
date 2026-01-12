"""
פונקציות ניקוי קבצים
"""
import logging
import asyncio
import os
from services.user_states import UserState
from services.media import cleanup_files

logger = logging.getLogger(__name__)


async def schedule_instagram_timeout(session, status_msg, delay_seconds: int = 300):
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


async def schedule_cleanup(session, delay_seconds: int = 60):
    """
    מתזמן ניקוי קבצים לאחר זמן מסוים
    """
    try:
        logger.info(f"⏰ Scheduled cleanup in {delay_seconds} seconds for user {session.user_id}")
        await asyncio.sleep(delay_seconds)
        await cleanup_session_files(session)
    except Exception as e:
        logger.error(f"❌ Error in scheduled cleanup: {e}", exc_info=True)


async def cleanup_session_files(session):
    """
    מנקה את כל הקבצים של הסשן ומאפס את נתיבי הקבצים
    """
    try:
        logger.info(f"🧹 Cleaning up files for user {session.user_id}")
        
        # איסוף כל הקבצים שצריך למחוק (כולל אלה מהסשן)
        files_to_delete = list(session.files_to_cleanup) if hasattr(session, 'files_to_cleanup') else []
        
        # הוספת קבצים מהסשן אם הם קיימים
        session_files = [
            session.image_path,
            session.mp3_path,
            session.processed_image_path,
            session.processed_mp3_path,
            session.video_high_path,
            session.video_medium_path,
            session.instagram_file_path
        ]
        
        # הוספת קבצים נוספים מהסשן אם קיימים
        if hasattr(session, 'upload_image_path') and session.upload_image_path:
            session_files.append(session.upload_image_path)
        if hasattr(session, 'upload_video_path') and session.upload_video_path:
            session_files.append(session.upload_video_path)
        if hasattr(session, 'upload_mp3_path') and session.upload_mp3_path:
            session_files.append(session.upload_mp3_path)
        
        for file_path in session_files:
            if file_path and file_path not in files_to_delete and os.path.exists(file_path):
                files_to_delete.append(file_path)
                logger.debug(f"  📋 הוסף לניקוי: {os.path.basename(file_path)}")
        
        if files_to_delete:
            logger.info(f"🗑️  מוחק {len(files_to_delete)} קבצים...")
            for file_path in files_to_delete:
                logger.debug(f"  📄 {os.path.basename(file_path)}")
            deleted = await cleanup_files(*files_to_delete)
            logger.info(f"✅ Cleaned up {deleted}/{len(files_to_delete)} files")
        else:
            logger.info("ℹ️ No files to clean up")
        
        # ניקוי רשימת הקבצים
        if hasattr(session, 'files_to_cleanup'):
            session.files_to_cleanup.clear()
        
        # ניקוי נתיבי הקבצים מהסשן (למניעת התייחסויות לקבצים שנמחקו)
        session.image_path = None
        session.mp3_path = None
        session.processed_image_path = None
        session.processed_mp3_path = None
        session.video_high_path = None
        session.video_medium_path = None
        session.instagram_file_path = None
        session.instagram_url = None
        session.instagram_text = None
        session.instagram_media_type = None
        if hasattr(session, 'upload_image_path'):
            session.upload_image_path = None
        if hasattr(session, 'upload_video_path'):
            session.upload_video_path = None
        if hasattr(session, 'upload_mp3_path'):
            session.upload_mp3_path = None
        
        logger.info(f"✅ Session cleaned up for user {session.user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up session files: {e}", exc_info=True)

