"""
טסט להורדה כפולה מ-YouTube
מוריד קליפ בשתי איכויות (1080-ish ו-720-ish/100MB) כולל המרה במידה וצריך
"""
import asyncio
import os
import logging
from pathlib import Path
import sys

# הוספת הנתיב של הפרויקט (תיקיית השורש)
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.media.youtube import download_youtube_video_dual
from services.media.ffmpeg_utils import (
    get_video_codec,
    get_audio_codec,
    get_video_duration,
    get_video_dimensions,
    _is_h264_compatible,
    _is_aac_compatible
)

# הגדרת לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """מחזיר גודל בפורמט קריא"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


async def analyze_video(video_path: str, quality_name: str):
    """מנתח קובץ וידאו ומציג מידע מפורט"""
    if not os.path.exists(video_path):
        logger.error(f"❌ קובץ לא נמצא: {video_path}")
        return
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 ניתוח קובץ: {quality_name}")
    logger.info(f"{'='*60}")
    
    # גודל קובץ
    file_size = os.path.getsize(video_path)
    logger.info(f"📁 גודל: {format_size(file_size)}")
    
    # קודקים
    video_info = await get_video_codec(video_path, use_cache=False)
    audio_info = await get_audio_codec(video_path, use_cache=False)
    
    if video_info:
        video_codec, video_tag = video_info
        logger.info(f"🎬 קודק וידאו: {video_codec} ({video_tag})")
        
        is_h264 = _is_h264_compatible(video_codec, video_tag)
        logger.info(f"   ✅ תואם H.264: {'כן' if is_h264 else 'לא'}")
    else:
        logger.warning("⚠️ לא ניתן לקבל קודק וידאו")
    
    if audio_info:
        audio_codec, audio_tag = audio_info
        logger.info(f"🎵 קודק אודיו: {audio_codec} ({audio_tag})")
        
        is_aac = _is_aac_compatible(audio_codec, audio_tag)
        logger.info(f"   ✅ תואם AAC: {'כן' if is_aac else 'לא'}")
    else:
        logger.warning("⚠️ לא ניתן לקבל קודק אודיו")
    
    # משך
    duration = await get_video_duration(video_path)
    if duration:
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        logger.info(f"⏱️ משך: {minutes}:{seconds:02d} ({duration:.2f} שניות)")
    
    # ממדים
    dimensions = await get_video_dimensions(video_path)
    if dimensions:
        width, height = dimensions
        logger.info(f"📐 ממדים: {width}x{height}")
    
    # סטטוס תואמות
    if video_info and audio_info:
        video_codec, video_tag = video_info
        audio_codec, audio_tag = audio_info
        
        is_compatible = (
            _is_h264_compatible(video_codec, video_tag) and
            _is_aac_compatible(audio_codec, audio_tag)
        )
        
        if is_compatible:
            logger.info("✅ **קובץ תואם לכל המכשירים (H.264 + AAC)**")
        else:
            logger.warning("⚠️ **קובץ לא תואם - נדרשת המרה**")
    
    logger.info(f"{'='*60}\n")


def progress_callback(percent: int, current_time: int, eta: int):
    """Callback לעדכון התקדמות המרה"""
    logger.info(f"⏳ התקדמות המרה: {percent}% | זמן: {current_time}s | ETA: ~{eta}s")


async def main():
    """פונקציה ראשית"""
    print("\n" + "="*60)
    print("🧪 טסט הורדה כפולה מ-YouTube")
    print("="*60)
    print()
    
    # קישור לבדיקה
    print("📝 הזן קישור YouTube (או לחץ Enter לשימוש בקישור ברירת מחדל):")
    url = input().strip()
    
    if not url:
        # קישור ברירת מחדל - סרטון קצר לבדיקה
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        print(f"   משתמש בקישור ברירת מחדל: {url}")
    
    print()
    print("🍪 האם יש קובץ cookies.txt? (y/n):")
    has_cookies = input().strip().lower() == 'y'
    cookies_path = "cookies.txt" if has_cookies and os.path.exists("cookies.txt") else None
    
    if cookies_path:
        print(f"   ✅ משתמש ב-cookies: {cookies_path}")
    else:
        print("   ⚠️ ממשיך ללא cookies")
    
    print()
    print("="*60)
    print("🚀 מתחיל הורדה כפולה...")
    print("="*60)
    print()
    
    try:
        # הורדה כפולה
        result = await download_youtube_video_dual(
            url=url,
            cookies_path=cookies_path or "cookies.txt",
            progress_callback=progress_callback
        )
        
        if not result:
            logger.error("❌ הורדה כפולה נכשלה")
            return
        
        high_quality_path, medium_quality_path = result
        
        print()
        print("="*60)
        print("✅ הורדה כפולה הושלמה!")
        print("="*60)
        print()
        
        # ניתוח קבצים
        if high_quality_path and os.path.exists(high_quality_path):
            await analyze_video(high_quality_path, "1080-ish (איכות גבוהה)")
        
        if medium_quality_path and os.path.exists(medium_quality_path):
            await analyze_video(medium_quality_path, "720-ish / <=100MB (איכות בינונית)")
        
        # סיכום
        print()
        print("="*60)
        print("📋 סיכום")
        print("="*60)
        
        if high_quality_path and os.path.exists(high_quality_path):
            high_size = os.path.getsize(high_quality_path)
            print(f"✅ 1080-ish: {os.path.basename(high_quality_path)} ({format_size(high_size)})")
        
        if medium_quality_path and os.path.exists(medium_quality_path):
            medium_size = os.path.getsize(medium_quality_path)
            print(f"✅ 720-ish/100MB: {os.path.basename(medium_quality_path)} ({format_size(medium_size)})")
        
        print()
        print("🗑️ האם למחוק את הקבצים? (y/n):")
        delete = input().strip().lower() == 'y'
        
        if delete:
            deleted_count = 0
            for path in [high_quality_path, medium_quality_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.info(f"🗑️ נמחק: {os.path.basename(path)}")
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"❌ שגיאה במחיקת {path}: {e}")
            
            print(f"\n✅ נמחקו {deleted_count} קבצים")
        else:
            print("\n📁 הקבצים נשמרו בתיקיית downloads/")
        
        print()
        print("="*60)
        print("✅ הטסט הושלם בהצלחה!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\n⏹️ הטסט בוטל על ידי המשתמש")
    except Exception as e:
        logger.error(f"❌ שגיאה בטסט: {e}", exc_info=True)
        print("\n❌ הטסט נכשל - בדוק את הלוגים למעלה")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ הטסט בוטל")
    except Exception as e:
        logger.error(f"❌ שגיאה: {e}", exc_info=True)

