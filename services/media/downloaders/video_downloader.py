"""
Video Downloader Service
שירות להורדת וידאו מיוטיוב עם retry logic ו-progress tracking
"""
import logging
import asyncio
import os
from typing import Callable, Dict, Any, Optional

from services.media.youtube import calculate_timeout, download_youtube_video_dual

# Import get_progress_stage directly to avoid circular import
def get_progress_stage(percent: float) -> int:
    """
    מחזיר את המצב הקרוב ביותר מבין המצבים המבוקשים
    """
    PROGRESS_STAGES = [0, 12, 43, 50, 67, 79, 80, 85, 99, 100]
    closest = PROGRESS_STAGES[0]
    min_diff = abs(percent - closest)
    
    for stage in PROGRESS_STAGES:
        diff = abs(percent - stage)
        if diff < min_diff:
            min_diff = diff
            closest = stage
    
    return closest

logger = logging.getLogger(__name__)


async def download_video_with_retry(
    session,
    upload_progress: Dict[str, Dict[str, Any]],
    update_status_func: Callable,
    errors: Optional[list] = None
) -> bool:
    """
    מוריד וידאו מיוטיוב עם retry logic, timeout דינמי, ומעקב התקדמות
    
    Args:
        session: אובייקט סשן המשתמש המכיל youtube_url ונתיבי קבצים
        upload_progress: מילון למעקב התקדמות העלאה (מצב משותף)
        update_status_func: פונקציה אסינכרונית לעדכון הודעת סטטוס המשתמש
        errors: רשימת שגיאות (אופציונלי) - אם מסופק, יוסיפו שגיאות כאן
        
    Returns:
        bool: True אם הצליח, False אחרת
    """
    max_retries = 3
    estimated_size_mb = 600
    
    # חישוב timeout כולל: הורדה + המרה כבדה (AV1/VP9 → H.264)
    download_timeout = calculate_timeout(estimated_size_mb, "download")
    conversion_timeout = calculate_timeout(estimated_size_mb, "conversion", "av1", "opus")
    dynamic_timeout = int((download_timeout + conversion_timeout) * 1.5)
    
    logger.info(f"⏱️ [YOUTUBE] Timeout כולל: {dynamic_timeout}s ({dynamic_timeout//60} דקות) = הורדה ({download_timeout//60} דקות) + המרה ({conversion_timeout//60} דקות) + מרווח")
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🎬 [YOUTUBE] ניסיון הורדה {attempt + 1}/{max_retries}...")
            logger.info(f"⏱️ Timeout: {dynamic_timeout}s ({dynamic_timeout//60} דקות)")
            
            # פונקציית callback להתקדמות המרת FFmpeg
            def ffmpeg_progress_callback(percent, current_time, eta):
                # עדכון progress של וידאו
                upload_progress['telegram']['video'] = percent
                upload_progress['whatsapp']['video'] = percent
                
                # עדכון סטטוס נוכחי - המרה לאחוז הקרוב ביותר
                progress_stage = get_progress_stage(percent)
                # עדכון סטטוס דרך callback (אם יש)
                if update_status_func:
                    asyncio.create_task(update_status_func(
                        f"עיבוד קליפ טלגרם: {percent}%",
                        progress_stage,
                        0
                    ))
            
            # Timeout דינמי לפי גודל משוער
            video_result = await asyncio.wait_for(
                download_youtube_video_dual(
                    url=session.youtube_url,
                    cookies_path="cookies.txt",
                    progress_callback=ffmpeg_progress_callback
                ),
                timeout=dynamic_timeout
            )
            
            if video_result and video_result[0] and os.path.exists(video_result[0]):
                # בדיקת גודל הקובץ
                file_size_mb = os.path.getsize(video_result[0]) / (1024 * 1024)
                if file_size_mb == 0:
                    raise Exception(f"קובץ וידאו ריק: {video_result[0]}")
                
                session.video_high_path = video_result[0]
                session.add_file_for_cleanup(video_result[0])
                logger.info(f"✅ [YOUTUBE] וידאו איכות גבוהה הורד: {video_result[0]} ({file_size_mb:.2f}MB)")
                
                if video_result[1] and os.path.exists(video_result[1]):
                    file_size_medium_mb = os.path.getsize(video_result[1]) / (1024 * 1024)
                    if file_size_medium_mb > 0:
                        session.video_medium_path = video_result[1]
                        session.add_file_for_cleanup(video_result[1])
                        logger.info(f"✅ [YOUTUBE] וידאו איכות בינונית הורד: {video_result[1]} ({file_size_medium_mb:.2f}MB)")
                    else:
                        logger.warning(f"⚠️ [YOUTUBE] קובץ וידאו בינוני ריק, מתעלם")
                else:
                    logger.info(f"ℹ️ [YOUTUBE] וידאו איכות בינונית לא זמין")
                
                # עדכון progress ל-100%
                upload_progress['telegram']['video'] = 100
                upload_progress['whatsapp']['video'] = 100
                if update_status_func:
                    await update_status_func("הורדה של קליפ לטלגרם (מיוטיוב)", 100, 0)
                return True
            else:
                error_msg = "הורדה נכשלה - לא הוחזר וידאו"
                if video_result and video_result[0]:
                    if not os.path.exists(video_result[0]):
                        error_msg = f"קובץ וידאו לא נמצא: {video_result[0]}"
                    else:
                        error_msg = f"קובץ וידאו לא תקין: {video_result[0]}"
                raise Exception(error_msg)
                
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ [YOUTUBE] Timeout בניסיון {attempt + 1}")
            if attempt < max_retries - 1:
                delay = 5 * (2 ** attempt)  # 5s, 10s, 20s
                if update_status_func:
                    await update_status_func(f"ניסיון {attempt + 1} נכשל (timeout)", 43, 0)
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"❌ [YOUTUBE] שגיאה בניסיון {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                delay = 5 * (2 ** attempt)
                if update_status_func:
                    await update_status_func(f"ניסיון {attempt + 1} נכשל", 43, 1)
                await asyncio.sleep(delay)
    
    # נכשל אחרי 3 ניסיונות
    logger.error("❌ [YOUTUBE] הורדת וידאו נכשלה לאחר 3 ניסיונות")
    if errors is not None:
        errors.append({
            "platform": "youtube",
            "file_type": "video",
            "error": "הורדת/המרת וידאו נכשלה לאחר 3 ניסיונות",
            "failure_source": "youtube_download_conversion"
        })
    if update_status_func:
        await update_status_func("הורדה של קליפ לטלגרם (מיוטיוב) - נכשל", 43, 0)
    return False
