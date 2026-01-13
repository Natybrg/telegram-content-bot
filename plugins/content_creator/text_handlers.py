"""
Handlers לטיפול בהודעות טקסט
"""
import logging
import asyncio
import os
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

import config
from core import is_authorized_user
from services.user_states import state_manager, UserState
from services.media import (
    download_instagram_story,
    download_instagram_reel,
    is_instagram_story_url,
    is_instagram_reel_url
)
from services.processing_queue import processing_queue
from services.rate_limiter import rate_limit
from services.content.orchestrator import process_content, process_video_only, process_instagram_upload
from .cleanup import schedule_instagram_timeout
from plugins.start import get_main_keyboard

logger = logging.getLogger(__name__)


# ========== טיפול בקישור אינסטגרם ==========

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test", "test_channel", "diagnose_channel"]), group=0)
@rate_limit(max_requests=10, window=60)
async def handle_instagram_url(client: Client, message: Message):
    """מטפל בקבלת קישור אינסטגרם (סטורי או רילס)"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized text from user {user.id}")
        return
    
    # קבלת סשן המשתמש
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping instagram handler")
        return
    
    url = message.text.strip()
    
    # בדיקה אם זה קישור אינסטגרם
    is_story = is_instagram_story_url(url)
    is_reel = is_instagram_reel_url(url)
    
    if not (is_story or is_reel):
        logger.debug(f"User {user.id} sent text but not an Instagram URL")
        return  # לא קישור אינסטגרם - לא מטפלים כאן
    
    # אם המשתמש במצב WAITING_INSTAGRAM_TEXT ושולח קישור אינסטגרם שוב,
    # נסביר לו שהוא צריך לשלוח טקסט, לא קישור
    if session.state == UserState.WAITING_INSTAGRAM_TEXT:
        await message.reply_text(
            "⚠️ **זה קישור אינסטגרם, לא טקסט!**\n\n"
            "אנא שלח את הטקסט שברצונך להוסיף להעלאה.\n\n"
            "💡 **הערה:** הקישור כבר נשמר. שלח עכשיו את הטקסט.\n\n"
            "לבטול: שלח /cancel"
        )
        return
    
    # בדיקה שאנחנו במצב IDLE (רק אז מטפלים בקישור חדש)
    if session.state != UserState.IDLE:
        logger.debug(f"User {user.id} sent text but not in IDLE state (state: {session.state})")
        return
    
    logger.info(f"📱 User {user.id} sent Instagram URL: {url}")
    
    try:
        # שמירת הקישור בסשן (רק הקישור, לא הטקסט!)
        session.instagram_url = url
        session.instagram_text = None  # איפוס טקסט קודם אם קיים
        session.instagram_file_path = None  # איפוס קובץ קודם
        session.instagram_media_type = None  # איפוס סוג מדיה
        
        # עדכון מצב מיד - כך שהבוט מחכה לטקסט כבר מהרגע הזה
        session.update_state(UserState.WAITING_INSTAGRAM_TEXT)
        
        # שמירת זמן שליחת הקישור (לצורך הטיימר של 5 דקות)
        session.instagram_download_time = datetime.now()
        
        # הודעת התחלה - מבקש טקסט לפני הורדה
        status_msg = await message.reply_text(
            "📥 **קישור אינסטגרם התקבל!**\n\n"
            "📝 **שלב 1:** שלח את הטקסט להעלאה\n\n"
            "💡 **הערה:** הקישור נשמר. שלח עכשיו את הטקסט שברצונך להוסיף להעלאה\n\n"
            "⏳ **שלב 2:** אחרי שתשלח טקסט, הבוט יוריד את הקובץ ויעלה אותו\n\n"
            "⏰ **זמן:** יש לך 5 דקות לשלוח טקסט\n\n"
            "לבטול: שלח /cancel"
        )
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        # התחלת טיימר לניקוי אוטומטי אחרי 5 דקות
        timeout_task = asyncio.create_task(schedule_instagram_timeout(session, status_msg, delay_seconds=300))
        session.instagram_timeout_task = timeout_task
        
    except Exception as e:
        logger.error(f"❌ Error handling Instagram URL: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בטיפול בקישור\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )


# ========== טיפול בפרטים לוידאו בלבד (3 שורות) ==========

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test", "test_channel", "diagnose_channel"]), group=1)
@rate_limit(max_requests=15, window=60)
async def handle_video_only_details(client: Client, message: Message):
    """מטפל בקבלת 3 שורות פרטים לוידאו בלבד (שם שיר, שם זמר, קישור יוטיוב)"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized text from user {user.id}")
        return
    
    # קבלת סשן המשתמש
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping video_only handler")
        return
    
    # בדיקה שאנחנו במצב IDLE (לא בתהליך אחר)
    if session.state != UserState.IDLE:
        logger.debug(f"User {user.id} sent text but not in IDLE state (state: {session.state})")
        return
    
    logger.info(f"📝 User {user.id} sent text in IDLE state - checking for video-only format")
    
    try:
        # פיצול הטקסט לשורות (מסיר שורות ריקות)
        lines = [line.strip() for line in message.text.strip().split('\n') if line.strip()]
        
        # בדיקה שיש בדיוק 3 שורות
        if len(lines) != 3:
            logger.debug(f"User {user.id} sent {len(lines)} lines, not 3 - not video-only format")
            return  # לא 3 שורות - לא זה מה שאנחנו מחפשים
        
        # שמירת הפרטים
        song_name = lines[0]
        artist_name = lines[1]
        youtube_url = lines[2]
        
        # ולידציה של URL
        youtube_patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
        ]
        
        is_valid_url = any(re.search(pattern, youtube_url) for pattern in youtube_patterns)
        
        if not is_valid_url:
            await message.reply_text(
                "⚠️ **קישור יוטיוב לא תקין!**\n\n"
                f"הקישור ששלחת: `{youtube_url}`\n\n"
                "קישור תקין צריך להיות אחד מהפורמטים הבאים:\n"
                "• https://www.youtube.com/watch?v=VIDEO_ID\n"
                "• https://youtu.be/VIDEO_ID\n"
                "• https://www.youtube.com/embed/VIDEO_ID\n\n"
                "שלח שוב עם קישור תקין"
            )
            return
        
        # שמירת הפרטים בסשן
        session.song_name = song_name
        session.artist_name = artist_name
        session.youtube_url = youtube_url
        session.need_video = True  # תמיד נדרש וידאו במצב זה
        
        # עדכון מצב
        session.update_state(UserState.PROCESSING)
        
        # הצגת סיכום
        summary = (
            "✅ **פרטים התקבלו!**\n\n"
            f"🎵 **שיר:** {session.song_name}\n"
            f"🎤 **זמר:** {session.artist_name}\n"
            f"📺 **יוטיוב:** {session.youtube_url}\n\n"
            f"🎬 **מצב:** העלאת וידאו בלבד\n\n"
            f"⏳ מתחיל עיבוד..."
        )
        
        status_msg = await message.reply_text(summary)
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        logger.info(f"✅ Video-only details saved for user {user.id}")
        logger.info(f"  Song: {session.song_name}")
        logger.info(f"  Artist: {session.artist_name}")
        logger.info(f"  YouTube URL: {session.youtube_url}")
        
        # הוספה לתור עיבוד
        await processing_queue.add_to_queue(
            user_id=user.id,
            callback=lambda: process_video_only(client, message, session, status_msg),
            message=message,
            status_msg=status_msg
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling video-only details: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בשמירת הפרטים\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )


# ========== טיפול בטקסט לאינסטגרם ==========

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test", "test_channel", "diagnose_channel"]), group=2)
@rate_limit(max_requests=15, window=60)
async def handle_instagram_text(client: Client, message: Message):
    """מטפל בקבלת טקסט לאינסטגרם"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized text from user {user.id}")
        return
    
    # קבלת סשן המשתמש
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping instagram text handler")
        return
    
    # בדיקה שאנחנו בשלב הנכון
    if session.state != UserState.WAITING_INSTAGRAM_TEXT:
        logger.debug(f"User {user.id} sent text but not in WAITING_INSTAGRAM_TEXT state (state: {session.state})")
        return
    
    # בדיקה שיש קישור אינסטגרם
    if not session.instagram_url:
        await message.reply_text(
            "❌ **שגיאה:** לא נמצא קישור אינסטגרם\n\n"
            "נסה שוב או שלח /cancel לביטול"
        )
        session.update_state(UserState.IDLE)
        return
    
    logger.info(f"📝 User {user.id} sent Instagram text")
    
    try:
        # בדיקה אם עברו 5 דקות מהרגע שהקישור נשלח
        if session.instagram_download_time:
            elapsed_seconds = (datetime.now() - session.instagram_download_time).total_seconds()
            if elapsed_seconds > 300:  # יותר מ-5 דקות
                await message.reply_text(
                    "⏰ **זמן ההמתנה פג!**\n\n"
                    "עברו יותר מ-5 דקות משליחת הקישור.\n"
                    "הקבצים נמחקו והתהליך בוטל.\n\n"
                    "תוכל להתחיל מחדש על ידי שליחת קישור אינסטגרם."
                )
                session.update_state(UserState.IDLE)
                return
        
        # שמירת הטקסט - וידוא שזה לא קישור אינסטגרם
        text = message.text.strip()
        if not text:
            await message.reply_text(
                "⚠️ **הטקסט ריק!**\n\n"
                "אנא שלח טקסט תקין.\n\n"
                "לבטול: שלח /cancel"
            )
            return
        
        # בדיקה שהטקסט לא קישור אינסטגרם (אם המשתמש שלח קישור במקום טקסט)
        if is_instagram_story_url(text) or is_instagram_reel_url(text):
            await message.reply_text(
                "⚠️ **זה קישור אינסטגרם, לא טקסט!**\n\n"
                "אנא שלח את הטקסט שברצונך להוסיף להעלאה.\n\n"
                "💡 **הערה:** הקישור כבר נשמר. שלח עכשיו את הטקסט.\n\n"
                "לבטול: שלח /cancel"
            )
            return
        
        # שמירת הטקסט (לא הקישור!)
        session.instagram_text = text
        logger.info(f"✅ Instagram text saved for user {user.id}: {text[:50]}...")
        
        # ביטול הטיימר כי קיבלנו טקסט
        if session.instagram_timeout_task:
            try:
                session.instagram_timeout_task.cancel()
            except:
                pass
        
        # הודעה שהטקסט נשמר ומתחילים הורדה
        status_msg = await message.reply_text(
            "✅ **שלב 1 הושלם: הטקסט נשמר!**\n\n"
            "⏳ **שלב 2:** מוריד את הקובץ מאינסטגרם...\n\n"
            "💡 **הערה:** אחרי ההורדה, נתחיל להעלות אוטומטית\n\n"
            "לבטול: שלח /cancel"
        )
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        # בדיקה אם ההורדה כבר התבצעה (אם לא, נתחיל הורדה)
        if not session.instagram_file_path or not os.path.exists(session.instagram_file_path):
            # התחלת הורדה - עכשיו שיש גם קישור וגם טקסט
            logger.info(f"📥 Starting Instagram download for user {user.id}")
            logger.info(f"  URL: {session.instagram_url}")
            logger.info(f"  Text: {session.instagram_text[:50]}...")
            
            # הורדה ברקע
            async def download_and_upload():
                """הורדה ואז העלאה אוטומטית"""
                try:
                    # זיהוי סוג הקישור
                    is_story = is_instagram_story_url(session.instagram_url)
                    is_reel = is_instagram_reel_url(session.instagram_url)
                    
                    if is_story:
                        logger.info(f"📱 Downloading Instagram story from: {session.instagram_url}")
                        file_path, media_type = await asyncio.to_thread(
                            download_instagram_story, session.instagram_url
                        )
                    elif is_reel:
                        logger.info(f"📱 Downloading Instagram reel from: {session.instagram_url}")
                        file_path, media_type = await asyncio.to_thread(
                            download_instagram_reel, session.instagram_url
                        )
                    else:
                        raise Exception("Invalid Instagram URL")
                    
                    # שמירת המידע בסשן
                    session.instagram_file_path = file_path
                    session.instagram_media_type = media_type
                    session.add_file_for_cleanup(file_path)
                    
                    logger.info(f"✅ Instagram media downloaded: {file_path} ({media_type})")
                    
                    # עדכון הודעה
                    await status_msg.edit_text(
                        "✅ **שלב 1 הושלם: הטקסט נשמר!**\n"
                        "✅ **שלב 2 הושלם: הורדה הושלמה!**\n\n"
                        f"📁 **סוג:** {'וידאו' if media_type == 'video' else 'תמונה'}\n\n"
                        "⏳ **שלב 3:** מעלה לטלגרם ווואטסאפ...\n\n"
                        "אנא המתן..."
                    )
                    
                    # בדיקה אם עברו 5 דקות
                    if session.instagram_download_time:
                        elapsed_seconds = (datetime.now() - session.instagram_download_time).total_seconds()
                        if elapsed_seconds > 300:
                            await status_msg.edit_text(
                                "⏰ **זמן ההמתנה פג!**\n\n"
                                "עברו יותר מ-5 דקות משליחת הקישור.\n"
                                "הקבצים נמחקו והתהליך בוטל."
                            )
                            session.update_state(UserState.IDLE)
                            return
                    
                    # בדיקה אם כבר התחילה העלאה
                    if session.state == UserState.PROCESSING:
                        logger.info(f"⚠️ User {session.user_id} - Upload already started")
                        return
                    
                    # עדכון מצב והתחלת העלאה
                    session.update_state(UserState.PROCESSING)
                    
                    # הוספה לתור עיבוד
                    from services.processing_queue import processing_queue
                    await processing_queue.add_to_queue(
                        user_id=session.user_id,
                        callback=lambda: process_instagram_upload(client, message, session, status_msg),
                        message=message,
                        status_msg=status_msg
                    )
                    
                except Exception as e:
                    logger.error(f"❌ Error downloading Instagram media: {e}", exc_info=True)
                    if session.state == UserState.WAITING_INSTAGRAM_TEXT or session.state == UserState.PROCESSING:
                        session.update_state(UserState.IDLE)
                        session.instagram_url = None
                        session.instagram_file_path = None
                        session.instagram_media_type = None
                        await status_msg.edit_text(
                            f"❌ **שגיאה בהורדה מאינסטגרם**\n\n"
                            f"השגיאה: {str(e)}\n\n"
                            "נסה שוב או שלח /cancel לביטול"
                        )
            
            # התחלת הורדה ברקע
            asyncio.create_task(download_and_upload())
            return  # יוצאים מהפונקציה - ההורדה תתבצע ברקע
        
        # בדיקה אם עברו 5 דקות (בדיקה נוספת לפני התחלת העלאה)
        if session.instagram_download_time:
            elapsed_seconds = (datetime.now() - session.instagram_download_time).total_seconds()
            if elapsed_seconds > 300:
                await message.reply_text(
                    "⏰ **זמן ההמתנה פג!**\n\n"
                    "עברו יותר מ-5 דקות משליחת הקישור.\n"
                    "הקבצים נמחקו והתהליך בוטל.\n\n"
                    "תוכל להתחיל מחדש על ידי שליחת קישור אינסטגרם."
                )
                session.update_state(UserState.IDLE)
                return
        
        # בדיקה אם כבר התחילה העלאה (race condition protection)
        if session.state == UserState.PROCESSING:
            logger.info(f"⚠️ User {user.id} - Upload already started, ignoring duplicate text")
            await message.reply_text(
                "⏳ **ההעלאה כבר התחילה!**\n\n"
                "אנא המתן לסיום ההעלאה."
            )
            return
        
        # בדיקה סופית שיש קובץ וטקסט
        if not session.instagram_file_path or not os.path.exists(session.instagram_file_path):
            await message.reply_text(
                "❌ **שגיאה:** הקובץ לא נמצא\n\n"
                "נסה שוב או שלח /cancel לביטול"
            )
            session.update_state(UserState.IDLE)
            return
        
        if not session.instagram_text or not session.instagram_text.strip():
            await message.reply_text(
                "❌ **שגיאה:** הטקסט לא נמצא\n\n"
                "נסה שוב או שלח /cancel לביטול"
            )
            return
        
        # אם הגענו לכאן, יש גם קובץ וגם טקסט - מתחילים העלאה
        status_msg = await message.reply_text(
            "✅ **שלב 1 הושלם: הטקסט נשמר!**\n"
            "✅ **שלב 2 הושלם: הורדה הושלמה!**\n\n"
            "⏳ **שלב 3:** מעלה לטלגרם ווואטסאפ...\n\n"
            "אנא המתן..."
        )
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        # עדכון מצב והתחלת העלאה
        session.update_state(UserState.PROCESSING)
        logger.info(f"🔄 User {user.id} state changed to PROCESSING - starting upload")
        logger.info(f"  File: {session.instagram_file_path}")
        logger.info(f"  Text: {session.instagram_text[:50]}...")
        
        # הוספה לתור עיבוד
        await processing_queue.add_to_queue(
            user_id=user.id,
            callback=lambda: process_instagram_upload(client, message, session, status_msg),
            message=message,
            status_msg=status_msg
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling Instagram text: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בשמירת הטקסט\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )


# ========== טיפול בפרטים (8 שורות) ==========

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test", "test_channel", "diagnose_channel"]), group=3)
@rate_limit(max_requests=15, window=60)
async def handle_details(client: Client, message: Message):
    """מטפל בקבלת 8 שורות הפרטים"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.warning(f"⛔ Unauthorized text from user {user.id}")
        return
    
    # קבלת סשן המשתמש
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן (settings.py יטפל)
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping content_creator handler")
        return
    
    # בדיקה שאנחנו בשלב הנכון
    if session.state != UserState.WAITING_DETAILS:
        logger.debug(f"User {user.id} sent text but not in WAITING_DETAILS state")
        return
    
    logger.info(f"📝 User {user.id} sent details")
    
    try:
        # פיצול הטקסט לשורות (מסיר שורות ריקות)
        lines = [line.strip() for line in message.text.strip().split('\n') if line.strip()]
        
        # בדיקה שיש 8 שורות (שורות ריקות לא נספרות)
        if len(lines) < 8:
            await message.reply_text(
                f"⚠️ **חסרות שורות!**\n\n"
                f"קיבלתי רק {len(lines)} שורות, צריך 8 שורות:\n"
                f"1. שם שיר\n"
                f"2. שם זמר\n"
                f"3. שנה\n"
                f"4. שם מלחין\n"
                f"5. שם מעבד\n"
                f"6. שם מיקס\n"
                f"7. קישור ליוטיוב\n"
                f"8. כן/לא (האם להוריד וידאו)\n\n"
                f"💡 שורות ריקות לא נספרות\n"
                f"שלח שוב עם כל הפרטים"
            )
            return
        
        # שמירת הפרטים
        session.song_name = lines[0]
        session.artist_name = lines[1]
        session.year = lines[2]
        session.composer = lines[3]
        session.arranger = lines[4]
        session.mixer = lines[5]
        session.youtube_url = lines[6]
        
        # בדיקת כן/לא לוידאו
        video_response = lines[7].lower()
        session.need_video = video_response in ['כן', 'yes', 'y', '1', 'true']
        
        # ולידציה של URL רק אם נדרש וידאו
        if session.need_video:
            youtube_patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
                r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
                r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
            ]
            
            is_valid_url = any(re.search(pattern, session.youtube_url) for pattern in youtube_patterns)
            
            if not is_valid_url:
                await message.reply_text(
                    "⚠️ **קישור יוטיוב לא תקין!**\n\n"
                    f"הקישור ששלחת: `{session.youtube_url}`\n\n"
                    "קישור תקין צריך להיות אחד מהפורמטים הבאים:\n"
                    "• https://www.youtube.com/watch?v=VIDEO_ID\n"
                    "• https://youtu.be/VIDEO_ID\n"
                    "• https://www.youtube.com/embed/VIDEO_ID\n\n"
                    "שלח שוב עם קישור תקין"
                )
                session.update_state(UserState.WAITING_DETAILS)  # נשאר במצב המתנה
                return
        
        # עדכון מצב
        session.update_state(UserState.PROCESSING)
        
        # הצגת סיכום
        summary = (
            "✅ **פרטים התקבלו!**\n\n"
            f"🎵 **שיר:** {session.song_name}\n"
            f"🎤 **זמר:** {session.artist_name}\n"
            f"📅 **שנה:** {session.year}\n"
            f"✍️ **מלחין:** {session.composer}\n"
            f"🎼 **מעבד:** {session.arranger}\n"
            f"🎚️ **מיקס:** {session.mixer}\n"
            f"📺 **יוטיוב:** {session.youtube_url}\n"
            f"🎬 **וידאו:** {'כן' if session.need_video else 'לא'}\n\n"
            f"⏳ מתחיל עיבוד..."
        )
        
        status_msg = await message.reply_text(summary)
        
        # שמירת הודעות למחיקה בסיום
        session.messages_to_delete.append(message)  # הודעת המשתמש
        session.messages_to_delete.append(status_msg)  # הודעת הבוט
        
        logger.info(f"✅ Details saved for user {user.id}")
        logger.info(f"  Song: {session.song_name}")
        logger.info(f"  Artist: {session.artist_name}")
        logger.info(f"  Need video: {session.need_video}")
        
        # הוספה לתור עיבוד
        await processing_queue.add_to_queue(
            user_id=user.id,
            callback=lambda: process_content(client, message, session, status_msg),
            message=message,
            status_msg=status_msg
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling details: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בשמירת הפרטים\n"
            "נסה שוב או שלח /cancel לביטול",
            reply_markup=get_main_keyboard()
        )
