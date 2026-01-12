"""
YouTube Download Module
הורדות מ-YouTube, דחיסה, המרות
"""
import os
import logging
import asyncio
import subprocess
import re
import time
from pathlib import Path
from typing import Optional, Tuple
import yt_dlp
import config
from .ffmpeg_utils import (
    get_video_codec,
    get_audio_codec,
    get_video_duration,
    convert_to_compatible_format,
    compress_with_ffmpeg,
    compress_to_target_size,
    _is_h264_compatible,
    _is_aac_compatible
)

logger = logging.getLogger(__name__)


def calculate_timeout(
    file_size_mb: float, 
    operation_type: str = "download",
    video_codec: str = "",
    audio_codec: str = ""
) -> int:
    """
    מחשב timeout דינמי לפי גודל קובץ וסוג פעולה
    
    Args:
        file_size_mb: גודל הקובץ ב-MB
        operation_type: סוג פעולה - "download" או "conversion"
        video_codec: קודק וידאו נוכחי (לבדיקה אם צריך המרה כבדה, רק ל-conversion)
        audio_codec: קודק אודיו נוכחי (רק ל-conversion)
    
    Returns:
        timeout בשניות
    """
    if operation_type == "conversion":
        # בדיקה אם צריך המרת וידאו כבדה (AV1/VP9 → H.264)
        heavy_video_codecs = ['av1', 'av01', 'vp9', 'vp09']
        is_heavy_conversion = any(codec.lower() in video_codec.lower() for codec in heavy_video_codecs) if video_codec else False
        
        if is_heavy_conversion:
            # המרה כבדה: 8 דקות לכל 100MB (480 שניות)
            calc_timeout = int((file_size_mb / 100) * 480)
            conversion_type = "כבדה (AV1/VP9 → H.264)"
        else:
            # המרה קלה: 4 דקות לכל 100MB (240 שניות)
            calc_timeout = int((file_size_mb / 100) * 240)
            conversion_type = "קלה"
        
        # מינימום 15 דקות (900 שניות) להמרה
        timeout = max(calc_timeout, 900)
        logger.info(f"⏱️ Timeout המרה ({conversion_type}): {timeout}s ({timeout//60} דקות) עבור {file_size_mb:.2f}MB")
    else:
        # הורדה: 5 דקות לכל 100MB (300 שניות)
        calc_timeout = int((file_size_mb / 100) * 300)
        
        # מינימום 10 דקות (600 שניות) להורדה
        timeout = max(calc_timeout, 600)
        logger.info(f"⏱️ Timeout הורדה: {timeout}s ({timeout//60} דקות) עבור קובץ {file_size_mb:.2f}MB")
    
    # הוספת 50% מרווח ביטחון
    timeout = int(timeout * 1.5)
    
    return timeout


# תאימות לאחור
def calculate_conversion_timeout(file_size_mb: float, video_codec: str = "", audio_codec: str = "") -> int:
    """תאימות לאחור - משתמש ב-calculate_timeout"""
    return calculate_timeout(file_size_mb, "conversion", video_codec, audio_codec)



async def download_youtube_video_dual(
    url: str,
    cookies_path: str = "cookies.txt",
    progress_callback=None
) -> Optional[Tuple[str, str]]:
    """
    מורידה וידאו מ-YouTube בשתי איכויות תואמות לכל המכשירים (H.264 + AAC)
    
    תהליך ההורדה:
    ----------------
    Deliverable A (1080-ish):
      - גובה: 930-1230 פיקסלים (±150 סביב 1080p)
      - מנסה להוריד streams תואמים (H.264+AAC) קודם
      - אם לא זמין, מוריד ומתמלל רק את מה שצריך
    
    Deliverable B (720-ish OR <=100MB):
      - גובה: 570-870 פיקסלים (±150 סביב 720p)
      - בוחר את הקטן מבין:
        1) גרסת 720-ish תואמת
        2) כל גרסה תואמת שסופית <=100MB
      - מתמלל עם bitrate targeting אם צריך להקטין
    
    Args:
        url: קישור YouTube
        cookies_path: נתיב לקובץ cookies.txt
        progress_callback: פונקציה לעדכון התקדמות המרת FFmpeg
    
    Returns:
        Tuple של (נתיב_1080ish, נתיב_720ish_or_100mb) או None אם נכשל
    """
    try:
        logger.info(f"📥 מתחיל הורדה כפולה: {url}")
        logger.info("🎬 מצב: 1080-ish (930-1230px) + 720-ish OR <=100MB (570-870px)")
        
        # ========== DELIVERABLE A: 1080-ish (930-1230px) ==========
        logger.info("\n🎯 DELIVERABLE A: 1080-ish (930-1230px)")
        
        # ניסיון 1: הורדת streams כבר תואמים (H.264+AAC)
        high_quality_file = await _download_single_quality(
            url=url,
            quality_name="1080-ish (תואם)",
            format_string=(
                # ניסיון 1: H.264 video + AAC audio (תואם מושלם)
                'bv*[height>=930][height<=1230][vcodec^=avc1][ext=mp4]+ba*[ext=m4a]/'
                'bv*[height>=930][height<=1230][vcodec^=avc1][ext=mp4]+ba*[acodec^=mp4a]/'
                # ניסיון 2: כל wideo stream + כל audio stream (ימוזג)
                'bv*[height>=930][height<=1230]+ba/'
                # ⚠️ REMOVED: 'b*[height>=930][height<=1230][ext=mp4]' - זה יכל להחזיר video-only!
                # במקום - דורשים מפורשות video+audio:
                'bestvideo[height>=930][height<=1230]+bestaudio'
            ),
            cookies_path=cookies_path,
            filename_suffix="_1080ish",
            progress_callback=progress_callback
        )
        
        # אם נכשל, ננסה כל קודק בטווח זה (אבל עדיין עם אודיו חובה!)
        if not high_quality_file:
            logger.info("⚠️ לא נמצא stream תואם, מוריד כל קודק בטווח + אודיו...")
            high_quality_file = await _download_single_quality(
                url=url,
                quality_name="1080-ish (כל קודק + אודיו חובה)",
                format_string=(
                    # כל video בטווח + כל audio stream (ימוזג)
                    'bv*[height>=930][height<=1230]+ba/'
                    # fallback: best video + best audio
                    'bestvideo[height>=930][height<=1230]+bestaudio'
                ),
                cookies_path=cookies_path,
                filename_suffix="_1080ish",
                progress_callback=progress_callback
            )
        
        if not high_quality_file:
            logger.error("❌ הורדת Deliverable A נכשלה")
            return None
        
        # ========== DELIVERABLE B: 720-ish OR <=70MB (לשימוש ב-WhatsApp) ==========
        logger.info("\n🎯 DELIVERABLE B: 720-ish (570-870px) OR <=70MB (לשימוש ב-WhatsApp)")
        
        # שלב 0: הערכת גודל משוער לפני הורדה
        format_720_string = (
            'bv*[height>=570][height<=870][vcodec^=avc1][ext=mp4]+ba*[ext=m4a]/'
            'bv*[height>=570][height<=870][vcodec^=avc1][ext=mp4]+ba*[acodec^=mp4a]/'
            'bv*[height>=570][height<=870]+ba/'
            'bestvideo[height>=570][height<=870]+bestaudio'
        )
        
        estimated_720_size = await estimate_download_size(url, format_720_string, cookies_path)
        logger.info(f"📊 גודל משוער של 720-ish: {estimated_720_size:.2f} MB" if estimated_720_size else "⚠️ לא ניתן להעריך גודל")
        
        # אם הגודל המשוער מעל 70MB, ננסה להוריד באיכות טובה יותר שתהיה מתחת ל-70MB
        medium_quality_file = None
        if estimated_720_size and estimated_720_size > 70:
            logger.info(f"⚠️ גודל משוער ({estimated_720_size:.2f}MB) מעל 70MB, מחפש איכות טובה יותר...")
            
            # ננסה להוריד באיכות נמוכה יותר (480p או 360p) שתהיה מתחת ל-70MB
            for target_height in [480, 360]:
                format_lower_string = (
                    f'bv*[height>={target_height-50}][height<={target_height+50}][vcodec^=avc1][ext=mp4]+ba*[ext=m4a]/'
                    f'bv*[height>={target_height-50}][height<={target_height+50}][vcodec^=avc1][ext=mp4]+ba*[acodec^=mp4a]/'
                    f'bv*[height>={target_height-50}][height<={target_height+50}]+ba/'
                    f'bestvideo[height>={target_height-50}][height<={target_height+50}]+bestaudio'
                )
                
                estimated_lower_size = await estimate_download_size(url, format_lower_string, cookies_path)
                if estimated_lower_size and estimated_lower_size <= 70:
                    logger.info(f"✅ נמצא format {target_height}p עם גודל משוער {estimated_lower_size:.2f}MB ≤ 70MB")
                    medium_quality_file = await _download_single_quality(
                        url=url,
                        quality_name=f"{target_height}p (תואם, ≤70MB)",
                        format_string=format_lower_string,
                        cookies_path=cookies_path,
                        filename_suffix="_720ish_temp"
                    )
                    if medium_quality_file:
                        break
        
        # אם לא מצאנו או לא הערכנו, ננסה 720-ish רגיל
        if not medium_quality_file:
            logger.info("📥 מוריד גרסת 720-ish רגילה...")
            medium_quality_file = await _download_single_quality(
                url=url,
                quality_name="720-ish (תואם)",
                format_string=format_720_string,
                cookies_path=cookies_path,
                filename_suffix="_720ish_temp"
            )
        
        # אם נכשל, ננסה כל קודק בטווח זה (אבל עדיין עם אודיו!)
        if not medium_quality_file:
            logger.info("⚠️ לא נמצא stream תואם, מוריד כל קודק בטווח + אודיו...")
            medium_quality_file = await _download_single_quality(
                url=url,
                quality_name="720-ish (כל קודק + אודיו חובה)",
                format_string=(
                    # כל video + כל audio
                    'bv*[height>=570][height<=870]+ba/'
                    'bestvideo[height>=570][height<=870]+bestaudio'
                ),
                cookies_path=cookies_path,
                filename_suffix="_720ish_temp"
            )
        
        if not medium_quality_file:
            logger.error("❌ הורדת Deliverable B נכשלה")
            return (high_quality_file, None)
        
        # שלב 2: בדיקה אם צריך דחיסה ל-70MB (גבול WhatsApp)
        medium_size_mb = os.path.getsize(medium_quality_file) / (1024 * 1024)
        logger.info(f"📊 גודל גרסת 720-ish: {medium_size_mb:.2f} MB")
        
        final_medium_file = medium_quality_file
        
        if medium_size_mb > 70:
            logger.info(f"🔄 הקובץ גדול מ-70MB, מייצר גרסה דחוסה ל-70MB...")
            
            # יצירת גרסה דחוסה ל-70MB עם bitrate targeting
            compressed_file = await compress_to_target_size(
                medium_quality_file, 
                target_size_mb=70,
                filename_suffix="_720ish_or_70mb"
            )
            
            if compressed_file:
                compressed_size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
                logger.info(f"📊 גודל גרסה דחוסה: {compressed_size_mb:.2f} MB")
                
                # בוחרים את הקטן מבין 720-ish לבין <=70MB
                logger.info(f"🤔 בוחר את הקטן: 720-ish ({medium_size_mb:.2f}MB) vs <=70MB ({compressed_size_mb:.2f}MB)")
                
                if compressed_size_mb < medium_size_mb and compressed_size_mb <= 70:
                    logger.info(f"✅ משתמש בגרסה דחוסה (קטנה יותר, ≤70MB)")
                    try:
                        os.remove(medium_quality_file)
                        logger.info(f"🗑️ גרסת 720-ish מקורית נמחקה")
                    except Exception as e:
                        logger.warning(f"⚠️ לא ניתן למחוק: {e}")
                    final_medium_file = compressed_file
                else:
                    logger.info(f"✅ משתמש בגרסת 720-ish (כבר קטנה מספיק או דחיסה לא הצליחה)")
                    try:
                        if compressed_file != final_medium_file:
                            os.remove(compressed_file)
                            logger.info(f"🗑️ גרסה דחוסה נמחקה")
                    except Exception as e:
                        logger.warning(f"⚠️ לא ניתן למחוק: {e}")
            else:
                logger.warning("⚠️ דחיסה נכשלה, משתמש ב-720-ish המקורי")
        else:
            logger.info(f"✅ גרסת 720-ish כבר ≤70MB, לא נדרשת דחיסה")
        
        # שינוי שם הקובץ הסופי
        final_medium_file_renamed = final_medium_file.replace("_temp", "_or_70mb")
        if final_medium_file_renamed != final_medium_file:
            try:
                # בדיקה אם הקובץ החדש כבר קיים
                if os.path.exists(final_medium_file_renamed):
                    # אם הקובץ החדש כבר קיים, נמחק אותו קודם
                    try:
                        os.remove(final_medium_file_renamed)
                        logger.debug(f"🗑️ נמחק קובץ ישן: {os.path.basename(final_medium_file_renamed)}")
                    except Exception as e:
                        logger.warning(f"⚠️ לא ניתן למחוק קובץ ישן: {e}")
                
                # שינוי שם הקובץ
                os.rename(final_medium_file, final_medium_file_renamed)
                final_medium_file = final_medium_file_renamed
                logger.debug(f"✅ שם קובץ שונה: {os.path.basename(final_medium_file_renamed)}")
            except Exception as e:
                logger.warning(f"⚠️ לא ניתן לשנות שם: {e}")
                # אם שינוי השם נכשל, נמשיך עם השם המקורי
        
        logger.info("\n✅ הורדה כפולה הושלמה בהצלחה!")
        logger.info(f"📹 DELIVERABLE A (1080-ish לטלגרם): {high_quality_file}")
        logger.info(f"📹 DELIVERABLE B (720-ish OR ≤70MB לוואטסאפ): {final_medium_file}")
        
        return (high_quality_file, final_medium_file)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהורדה כפולה: {e}", exc_info=True)
        return None


async def _download_single_quality(
    url: str,
    quality_name: str,
    format_string: str,
    cookies_path: str,
    filename_suffix: str = "",
    progress_callback=None
) -> Optional[str]:
    """
    מורידה וידאו באיכות ספציפית
    
    Args:
        url: קישור YouTube
        quality_name: שם האיכות (לתיעוד)
        format_string: format selector של yt-dlp
        cookies_path: נתיב לקובץ cookies
        filename_suffix: סיומת לשם הקובץ (למשל "_high" או "_medium")
        progress_callback: פונקציה לעדכון התקדמות המרה
    
    Returns:
        נתיב לקובץ שהורד והומר, או None אם נכשל
    """
    try:
        logger.info(f"📥 מוריד גרסה {quality_name}...")
        
        # וידוא שתיקיית downloads קיימת
        downloads_dir = Path(config.DOWNLOADS_PATH)
        downloads_dir.mkdir(exist_ok=True)
        
        # בדיקת קיום cookies
        if not os.path.exists(cookies_path):
            logger.warning(f"⚠️ קובץ cookies לא נמצא: {cookies_path}")
            cookies_path = None
        
        # תבנית שם קובץ עם סיומת
        output_template = str(downloads_dir / f"%(title)s_%(id)s{filename_suffix}.%(ext)s")
        
        # הגדרות yt-dlp
        ydl_opts = {
            'format': format_string,
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'cookiefile': cookies_path if cookies_path else None,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # הורדה ב-thread נפרד עם retry logic ל-rate limiting
        max_attempts = 3
        downloaded_file = None
        for attempt in range(max_attempts):
            try:
                def _download():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        return filename
                
                # הרצה אסינכרונית
                loop = asyncio.get_event_loop()
                downloaded_file = await loop.run_in_executor(None, _download)
                break  # הצליח - יוצאים מהלולאה
            except Exception as e:
                error_str = str(e).lower()
                # בדיקה אם זו שגיאת rate limiting
                if ("429" in error_str or "rate limit" in error_str or 
                    "too many requests" in error_str or 
                    "http error 429" in error_str):
                    if attempt < max_attempts - 1:
                        delay = 60 * (attempt + 1)  # 60s, 120s, 180s
                        logger.warning(f"⚠️ Rate limited by YouTube, waiting {delay}s before retry {attempt + 2}/{max_attempts}...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"❌ Rate limited by YouTube after {max_attempts} attempts")
                        return None
                else:
                    # שגיאה אחרת - מעלה אותה
                    raise
        
        # בדיקת קיום הקובץ
        if not os.path.exists(downloaded_file):
            logger.error(f"❌ קובץ {quality_name} לא נמצא: {downloaded_file}")
            return None
        
        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
        logger.info(f"✅ הורדה {quality_name} הושלמה: {file_size_mb:.2f} MB")
        
        # בדיקה אם הקובץ כבר בפורמט תואם (H.264 + AAC)
        logger.info(f"🔍 בודק פורמט קובץ {quality_name}...")
        # שימוש ב-cache למניעת קריאות מיותרות
        video_info = await get_video_codec(downloaded_file, use_cache=True)
        audio_info = await get_audio_codec(downloaded_file, use_cache=True)
        
        
        if video_info and audio_info:
            video_codec, video_tag = video_info
            audio_codec, audio_tag = audio_info
            
            logger.info(f"📊 קודקים - וידאו: {video_codec} ({video_tag}), אודיו: {audio_codec} ({audio_tag})")
            
            # ✅ בדיקה קריטית: וידוא שיש track אודיו (לא video-only)
            if not audio_codec or audio_codec.strip() == "":
                logger.error(f"❌ קובץ {quality_name} הורד ללא track אודיו (video-only format)!")
                logger.error(f"   זה בדרך כלל קורה כאשר yt-dlp בוחר format video-only")
                logger.error(f"   ישנה בעיה בבחירת הפורמט או שחסר JS runtime (Node.js/Deno)")
                # ניתן להוסיף כאן retry עם format selector אחר
                return None
            
            # בדיקה אם כבר תואם (case-insensitive)
            if _is_h264_compatible(video_codec, video_tag) and _is_aac_compatible(audio_codec, audio_tag):
                logger.info(f"✅ קובץ {quality_name} כבר בפורמט תואם (H.264 + AAC)")
                return downloaded_file
        else:
            logger.warning(f"⚠️ לא ניתן לקבוע קודקים עבור {quality_name}")
            video_codec = ""
            audio_codec = ""
        
        # אם לא תואם - מבצעים המרה עם timeout נפרד
        logger.info(f"🔄 קובץ {quality_name} לא תואם, מתחיל המרה...")
        
        # חישוב timeout דינמי להמרה לפי קודק וגודל
        conversion_timeout = calculate_conversion_timeout(file_size_mb, video_codec, audio_codec)
        logger.info(f"⏱️ Timeout להמרה: {conversion_timeout}s ({conversion_timeout//60} דקות)")
        
        try:
            # הרצת המרה עם timeout נפרד (לא חלק מה-download timeout!)
            compatible_file = await asyncio.wait_for(
                convert_to_compatible_format(downloaded_file, progress_callback=progress_callback),
                timeout=conversion_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"❌ המרת {quality_name} עברה timeout ({conversion_timeout}s)")
            logger.error(f"   הקובץ הורד בהצלחה אבל ההמרה ארכה יותר מדי")
            return None
        
        if compatible_file and os.path.exists(compatible_file):
            # בדיקה שהקובץ המומר אכן תואם (H.264 + AAC)
            # לא משתמשים ב-cache כאן כי זה קובץ חדש
            converted_video_info = await get_video_codec(compatible_file, use_cache=False)
            converted_audio_info = await get_audio_codec(compatible_file, use_cache=False)
            
            if converted_video_info and converted_audio_info:
                conv_video_codec, conv_video_tag = converted_video_info
                conv_audio_codec, conv_audio_tag = converted_audio_info
                
                # וידוא שההמרה הצליחה
                if _is_h264_compatible(conv_video_codec, conv_video_tag) and _is_aac_compatible(conv_audio_codec, conv_audio_tag):
                    # מחיקת הקובץ המקורי אם ההמרה הצליחה
                    if compatible_file != downloaded_file:
                        try:
                            os.remove(downloaded_file)
                            logger.info(f"🗑️ קובץ מקורי {quality_name} נמחק")
                        except Exception as e:
                            logger.warning(f"⚠️ לא ניתן למחוק: {e}")
                    
                    logger.info(f"✅ המרת {quality_name} הושלמה בהצלחה - קובץ תואם")
                    return compatible_file
                else:
                    logger.error(f"❌ המרת {quality_name} נכשלה - הקובץ המומר לא תואם (וידאו: {conv_video_codec}, אודיו: {conv_audio_codec})")
                    # מנסים למחוק את הקובץ המומר הלא תואם
                    try:
                        if compatible_file != downloaded_file:
                            os.remove(compatible_file)
                    except:
                        pass
                    return None
            else:
                logger.error(f"❌ לא ניתן לבדוק קודקים של הקובץ המומר {quality_name}")
                return None
        else:
            logger.error(f"❌ המרת {quality_name} נכשלה - קובץ מומר לא נוצר")
            return None
            
    except Exception as e:
        logger.error(f"❌ שגיאה בהורדת {quality_name}: {e}", exc_info=True)
        return None


async def download_youtube_video(
    url: str,
    quality: str = "1080p",
    cookies_path: str = "cookies.txt"
) -> Optional[str]:
    """
    מורידה וידאו מ-YouTube באיכות בודדת (תאימות לאחור)
    להורדה כפולה השתמש ב-download_youtube_video_dual
    
    Args:
        url: קישור YouTube
        quality: איכות וידאו -
                 "4k" - עד 2160p (4K)
                 "1440p" - עד 1440p (2K)
                 "1080p" - עד 1080p (ברירת מחדל)
                 "720p"/"mobile" - עד 720p
        cookies_path: נתיב לקובץ cookies.txt
    
    Returns:
        נתיב לקובץ שהורד או None אם נכשל
    """
    try:
        logger.info(f"📥 מתחיל הורדה: {url}")
        logger.info(f"🎬 איכות: {quality}")
        
        # וידוא שתיקיית downloads קיימת
        downloads_dir = Path(config.DOWNLOADS_PATH)
        downloads_dir.mkdir(exist_ok=True)
        
        # בדיקת קיום cookies
        if not os.path.exists(cookies_path):
            logger.warning(f"⚠️ קובץ cookies לא נמצא: {cookies_path}")
            logger.warning("ממשיך ללא cookies...")
            cookies_path = None
        
        # תבנית שם קובץ פלט
        output_template = str(downloads_dir / "%(title)s_%(id)s.%(ext)s")
        
        # הגדרות yt-dlp לפי איכות
        if quality == "4k" or quality == "2160p":
            ydl_opts = {
                'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
                'merge_output_format': 'mp4',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': False,
                'cookiefile': cookies_path if cookies_path else None,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            logger.info("📊 מצב: איכות 4K (עד 2160p, כל הקודקים)")
            
        elif quality == "1440p" or quality == "2k":
            ydl_opts = {
                'format': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]',
                'merge_output_format': 'mp4',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': False,
                'cookiefile': cookies_path if cookies_path else None,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            logger.info("📊 מצב: איכות 1440p (עד 1440p, כל הקודקים)")
            
        elif quality == "1080p":
            ydl_opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'merge_output_format': 'mp4',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': False,
                'cookiefile': cookies_path if cookies_path else None,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            logger.info("📊 מצב: איכות 1080p (עד 1080p, כל הקודקים)")
            
        elif quality == "mobile" or quality == "720p":
            ydl_opts = {
                'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'merge_output_format': 'mp4',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': False,
                'cookiefile': cookies_path if cookies_path else None,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            logger.info("📱 מצב: איכות מובייל (עד 720p, כל הקודקים)")
        else:
            logger.error(f"❌ איכות לא מוכרת: {quality}")
            return None
        
        # הורדה ב-thread נפרד
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename
        
        # הרצה אסינכרונית
        loop = asyncio.get_event_loop()
        downloaded_file = await loop.run_in_executor(None, _download)
        
        # בדיקת קיום הקובץ
        if not os.path.exists(downloaded_file):
            logger.error(f"❌ קובץ שהורד לא נמצא: {downloaded_file}")
            return None
        
        file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
        logger.info(f"✅ הורדה הושלמה: {downloaded_file}")
        logger.info(f"📊 גודל קובץ: {file_size_mb:.2f} MB")
        
        # בדיקה אם הקובץ כבר בפורמט תואם (H.264 + AAC)
        logger.info("🔍 בודק פורמט הקובץ שהורד...")
        video_info = await get_video_codec(downloaded_file)
        audio_info = await get_audio_codec(downloaded_file)
        
        if video_info and audio_info:
            video_codec, video_tag = video_info
            audio_codec, audio_tag = audio_info
            
            logger.info(f"📊 קודקים שהורדו - וידאו: {video_codec} ({video_tag}), אודיו: {audio_codec} ({audio_tag})")
            
            # בדיקה אם כבר תואם (case-insensitive)
            if _is_h264_compatible(video_codec, video_tag) and _is_aac_compatible(audio_codec, audio_tag):
                logger.info("✅ הקובץ כבר בפורמט תואם (H.264 + AAC) - לא נדרשת המרה!")
                return downloaded_file
            
            # אם לא תואם - מבצעים המרה
            logger.info(f"🔄 הקובץ לא תואם (וידאו: {video_codec}/{video_tag}, אודיו: {audio_codec}/{audio_tag})")
            logger.info("🔄 מתחיל המרה לפורמט תואם (H.264 + AAC)...")
        else:
            logger.warning("⚠️ לא ניתן לקבוע קודקים, מנסה המרה בכל מקרה...")
        
        compatible_file = await convert_to_compatible_format(downloaded_file)
        
        if compatible_file and os.path.exists(compatible_file):
            # מחיקת הקובץ המקורי אם ההמרה הצליחה
            if compatible_file != downloaded_file:
                try:
                    os.remove(downloaded_file)
                    logger.info(f"🗑️ קובץ מקורי נמחק: {downloaded_file}")
                except Exception as e:
                    logger.warning(f"⚠️ לא ניתן למחוק קובץ מקורי: {e}")
            
            return compatible_file
        else:
            logger.warning("⚠️ המרה נכשלה, מחזיר קובץ מקורי")
            return downloaded_file
            
    except Exception as e:
        logger.error(f"❌ שגיאה בהורדת וידאו: {e}", exc_info=True)
        return None


async def compress_video_smart(input_path: str, target_size_mb: int = 100) -> Optional[str]:
    """
    דחיסה חכמה של וידאו - בודק גודל ודוחס רק אם נדרש (תאימות לאחור - משתמש ב-compress_video)
    
    Args:
        input_path: נתיב לקובץ קלט
        target_size_mb: גודל יעד ב-MB (ברירת מחדל: 100 עבור WhatsApp)
    
    Returns:
        נתיב לקובץ דחוס או הקובץ המקורי (אם לא נדרשה דחיסה)
    """
    from .ffmpeg_utils import compress_video
    
    return await compress_video(
        input_path=input_path,
        target_size_mb=target_size_mb,
        method="two_pass",  # 2-pass לאיכות טובה יותר
        filename_suffix="_compressed",
        check_size=True  # בודק גודל לפני דחיסה
    )


# Cache למידע על וידאו (TTL: 5 דקות)
_video_info_cache = {}
_video_info_cache_timestamps = {}
_video_info_cache_ttl = 300  # 5 דקות בשניות

async def get_video_info(url: str, cookies_path: str = "cookies.txt", use_cache: bool = True) -> Optional[dict]:
    """
    מחזיר מידע על וידאו ללא הורדה
    עם caching למניעת קריאות מיותרות
    
    Args:
        url: קישור YouTube
        cookies_path: נתיב לקובץ cookies
        use_cache: האם להשתמש ב-cache (ברירת מחדל: True)
    
    Returns:
        dict עם מידע: title, duration, uploader, view_count, thumbnail
    """
    # בדיקת cache
    if use_cache and url in _video_info_cache:
        if url in _video_info_cache_timestamps:
            age = time.time() - _video_info_cache_timestamps[url]
            if age < _video_info_cache_ttl:
                logger.debug(f"📦 Using cached video info for: {url}")
                return _video_info_cache[url]
            else:
                # Cache expired
                del _video_info_cache[url]
                del _video_info_cache_timestamps[url]
    
    try:
        logger.info(f"ℹ️ מאחזר מידע על וידאו: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
        }
        
        def _get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'thumbnail': info.get('thumbnail'),
                }
        
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(None, _get_info)
        
        # שמירה ב-cache
        if use_cache and video_info:
            _video_info_cache[url] = video_info
            _video_info_cache_timestamps[url] = time.time()
        
        logger.info(f"✅ מידע התקבל: {video_info.get('title')}")
        return video_info
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקבלת מידע: {e}")
        return None


async def estimate_download_size(url: str, format_string: str, cookies_path: str = "cookies.txt") -> Optional[float]:
    """
    מעריך את הגודל המשוער של קובץ לפני הורדה (וידאו + אודיו)
    
    Args:
        url: קישור YouTube
        format_string: format selector של yt-dlp
        cookies_path: נתיב לקובץ cookies
    
    Returns:
        גודל משוער ב-MB או None אם נכשל
    """
    try:
        logger.info(f"📊 מעריך גודל משוער לפני הורדה...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'format': format_string,
        }
        
        def _estimate():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # ניסיון לקבל את ה-format שנבחר
                formats = info.get('formats', [])
                selected_format = None
                
                # חיפוש ה-format שנבחר לפי ה-format_string
                # yt-dlp בוחר את ה-format הטוב ביותר שמתאים ל-format_string
                if formats:
                    # ננסה למצוא את ה-format עם הגודל הגדול ביותר שמתאים
                    best_format = None
                    best_size = 0
                    
                    for fmt in formats:
                        # בדיקה אם ה-format מתאים ל-format_string (פשטני)
                        filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                        if filesize > best_size:
                            best_size = filesize
                            best_format = fmt
                    
                    selected_format = best_format
                
                # אם יש format נבחר, נשתמש בגודל שלו
                if selected_format:
                    filesize = selected_format.get('filesize') or selected_format.get('filesize_approx') or 0
                    if filesize > 0:
                        size_mb = filesize / (1024 * 1024)
                        logger.info(f"✅ גודל משוער: {size_mb:.2f} MB")
                        return size_mb
                
                # אם לא מצאנו, ננסה לחשב לפי bitrate + duration
                duration = info.get('duration', 0)
                if duration > 0:
                    # חישוב משוער לפי bitrate ממוצע
                    # כלל אגודל: 1080p ~8Mbps, 720p ~5Mbps, 480p ~2.5Mbps
                    # נשתמש ב-bitrate משוער לפי האיכות
                    estimated_bitrate_mbps = 5.0  # ברירת מחדל: 720p
                    if '1080' in format_string or 'height>=930' in format_string:
                        estimated_bitrate_mbps = 8.0
                    elif '720' in format_string or 'height>=570' in format_string:
                        estimated_bitrate_mbps = 5.0
                    else:
                        estimated_bitrate_mbps = 2.5
                    
                    # חישוב: bitrate (Mbps) * duration (seconds) / 8 = size (MB)
                    size_mb = (estimated_bitrate_mbps * duration) / 8
                    logger.info(f"✅ גודל משוער (לפי bitrate): {size_mb:.2f} MB")
                    return size_mb
                
                return None
        
        loop = asyncio.get_event_loop()
        estimated_size = await loop.run_in_executor(None, _estimate)
        return estimated_size
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהערכת גודל: {e}")
        return None


def estimate_converted_size(
    input_size_mb: float,
    duration: float,
    video_codec: str = "",
    audio_codec: str = "",
    target_crf: int = 23,
    target_scale: Optional[str] = None
) -> float:
    """
    מעריך את הגודל המשוער של קובץ אחרי המרה
    
    Args:
        input_size_mb: גודל הקובץ המקורי ב-MB
        duration: משך הוידאו בשניות
        video_codec: קודק וידאו נוכחי
        audio_codec: קודק אודיו נוכחי
        target_crf: CRF יעד (23 = איכות טובה, 28 = בינוני, 32 = דחוס)
        target_scale: scale יעד (למשל "1280", "960", "720")
    
    Returns:
        גודל משוער ב-MB אחרי המרה
    """
    try:
        # חישוב bitrate משוער לפי CRF
        # CRF 23 ≈ 2000kbps, CRF 28 ≈ 1500kbps, CRF 32 ≈ 1000kbps, CRF 35 ≈ 700kbps
        crf_to_bitrate = {
            23: 2000, 24: 1800, 25: 1700, 26: 1600, 27: 1500,
            28: 1400, 29: 1300, 30: 1200, 31: 1100, 32: 1000,
            33: 900, 34: 800, 35: 700, 36: 600, 37: 500
        }
        
        video_bitrate_kbps = crf_to_bitrate.get(target_crf, 1500)
        
        # התאמה לפי scale (אם מקטינים resolution, bitrate יורד)
        if target_scale:
            try:
                scale_height = int(target_scale)
                # כלל אגודל: bitrate פרופורציונלי ל-resolution
                if scale_height <= 720:
                    video_bitrate_kbps = int(video_bitrate_kbps * 0.6)  # 60% מהמקורי
                elif scale_height <= 960:
                    video_bitrate_kbps = int(video_bitrate_kbps * 0.75)  # 75% מהמקורי
                elif scale_height <= 1280:
                    video_bitrate_kbps = int(video_bitrate_kbps * 0.9)  # 90% מהמקורי
            except:
                pass
        
        # אודיו: 128kbps (ברירת מחדל)
        audio_bitrate_kbps = 128
        
        # חישוב גודל: (video_bitrate + audio_bitrate) * duration / 8
        total_bitrate_kbps = video_bitrate_kbps + audio_bitrate_kbps
        size_mb = (total_bitrate_kbps * duration) / (8 * 1024)
        
        logger.debug(f"📊 הערכת גודל אחרי המרה: CRF={target_crf}, scale={target_scale}, bitrate={total_bitrate_kbps}kbps → {size_mb:.2f}MB")
        return size_mb
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהערכת גודל אחרי המרה: {e}")
        # אם נכשל, נחזיר הערכה שמרנית (80% מהמקורי)
        return input_size_mb * 0.8
