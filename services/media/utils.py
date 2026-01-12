"""
General Utilities
פונקציות עזר כלליות - ניקוי קבצים, cookies, sanitization
"""
import os
import logging
import asyncio
import re
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    מנקה שם קובץ מתווים לא חוקיים
    מחליף תווים לא חוקיים ברווח
    לא מייצר underscore אלא אם המשתמש שלח אותו מראש
    
    Args:
        filename: שם הקובץ המקורי
    
    Returns:
        שם קובץ נקי
    """
    # תווים לא חוקיים ב-Windows/Linux/macOS/Android/iOS
    # כולל: < > : " / \ | ? * וכל תווי בקרה
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    
    # החלפת תווים לא חוקיים ברווח (לא Fullwidth - לתאימות מרבית)
    cleaned = re.sub(illegal_chars, ' ', filename)
    
    # צמצום רווחים כפולים לרווח אחד
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # הסרת רווחים בהתחלה ובסוף
    cleaned = cleaned.strip()
    
    # הסרת רווחים בסוף שם הקובץ (לפני הסיומת)
    # אם יש נקודה, נסיר רווחים לפני הנקודה האחרונה
    if '.' in cleaned:
        name_part, ext_part = cleaned.rsplit('.', 1)
        name_part = name_part.rstrip()  # הסרת רווחים בסוף שם הקובץ
        cleaned = f"{name_part}.{ext_part}"
    else:
        cleaned = cleaned.rstrip()  # הסרת רווחים בסוף
    
    # אם השם ריק, תן שם ברירת מחדל
    if not cleaned:
        cleaned = "file"
    
    logger.debug(f"📝 Sanitized filename: '{filename}' → '{cleaned}'")
    return cleaned


def get_file_extension(filename: str) -> str:
    """
    מחזיר את סיומת הקובץ מהנקודה האחרונה
    
    Args:
        filename: שם הקובץ
    
    Returns:
        סיומת הקובץ (כולל נקודה, למשל ".mp3")
    """
    if '.' not in filename:
        return ""
    return '.' + filename.rsplit('.', 1)[1]


def build_target_filename(artist_name: str, song_name: str, original_filename: str) -> str:
    """
    בונה שם קובץ יעד לפני העלאה: {artist_name} - {song_name}.{ext}
    
    Args:
        artist_name: שם האמן
        song_name: שם השיר
        original_filename: שם הקובץ המקורי (לחילוץ סיומת)
    
    Returns:
        שם קובץ נקי בפורמט: {artist} - {song}.{ext}
    """
    # ניקוי השמות
    clean_artist = sanitize_filename(artist_name)
    clean_song = sanitize_filename(song_name)
    
    # חילוץ סיומת מהנקודה האחרונה
    ext = get_file_extension(original_filename)
    if not ext:
        ext = ".mp3"  # ברירת מחדל
    
    # בניית שם הקובץ
    target_name = f"{clean_artist} - {clean_song}{ext}"
    
    logger.debug(f"📝 Target filename: '{target_name}'")
    return target_name


def create_upload_copy(original_path: str, new_filename: str) -> Optional[str]:
    """
    יוצר עותק של קובץ עם שם חדש להעלאה
    
    Args:
        original_path: נתיב לקובץ המקורי
        new_filename: שם הקובץ החדש (רק שם, לא נתיב מלא)
    
    Returns:
        נתיב לקובץ החדש או None אם נכשל
    """
    try:
        if not os.path.exists(original_path):
            logger.error(f"❌ קובץ מקורי לא נמצא: {original_path}")
            return None
        
        # יצירת נתיב לקובץ החדש באותה תיקייה
        directory = os.path.dirname(original_path)
        new_path = os.path.join(directory, new_filename)
        
        # העתקת הקובץ
        import shutil
        shutil.copy2(original_path, new_path)
        
        logger.info(f"📋 יצירת עותק להעלאה: {os.path.basename(original_path)} → {new_filename}")
        return new_path
        
    except Exception as e:
        logger.error(f"❌ שגיאה ביצירת עותק: {e}", exc_info=True)
        return None


def get_next_update_filename(file_path: str) -> str:
    """
    מחזיר שם קובץ עם "Update N" - מוסיף מספר אם הקובץ כבר קיים
    
    Args:
        file_path: נתיב לקובץ (כולל שם)
    
    Returns:
        נתיב לקובץ עם "Update N" אם צריך
    """
    if not os.path.exists(file_path):
        return file_path
    
    # חילוץ נתיב, שם בסיס וסיומת
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    if '.' in filename:
        name_base, ext = filename.rsplit('.', 1)
        ext = '.' + ext
    else:
        name_base = filename
        ext = ""
    
    # חיפוש שם פנוי
    counter = 1
    while True:
        new_filename = f"{name_base} Update {counter}{ext}"
        new_path = os.path.join(directory, new_filename)
        
        if not os.path.exists(new_path):
            logger.debug(f"📝 Next update filename: '{new_filename}'")
            return new_path
        
        counter += 1
        
        # הגנה מפני לולאה אינסופית
        if counter > 1000:
            logger.warning(f"⚠️ Too many update files, using timestamp")
            import time
            timestamp = int(time.time())
            new_filename = f"{name_base} Update {timestamp}{ext}"
            return os.path.join(directory, new_filename)


async def cleanup_files(*file_paths: str) -> int:
    """
    מוחק קבצים זמניים
    
    Returns:
        מספר קבצים שנמחקו בהצלחה
    """
    deleted_count = 0
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ נמחק: {file_path}")
                deleted_count += 1
        except Exception as e:
            logger.error(f"❌ שגיאה במחיקת {file_path}: {e}")
    
    return deleted_count


def validate_cookies_file(cookies_path: str) -> bool:
    """
    בודק אם קובץ cookies תקין
    
    Args:
        cookies_path: נתיב לקובץ cookies
    
    Returns:
        True אם הקובץ תקין, False אחרת
    """
    try:
        if not os.path.exists(cookies_path):
            return False
        
        with open(cookies_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # בדיקה בסיסית - צריך להכיל לפחות שורה אחת עם tab (פורמט Netscape cookies)
            # או לפחות שורה אחת שאינה הערה (לא מתחילה ב-#)
            valid_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            if not valid_lines:
                return False
            # בדיקה אם יש לפחות שורה אחת עם tab (פורמט Netscape)
            return any('\t' in line for line in valid_lines)
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת קובץ cookies: {e}")
        return False


def validate_path(path: str, base_dir: Path) -> bool:
    """
    בודק אם path בטוח (לא יוצא מ-base_dir) - הגנה מפני path traversal
    
    Args:
        path: הנתיב לבדיקה
        base_dir: תיקיית הבסיס
    
    Returns:
        True אם הנתיב בטוח, False אחרת
    """
    try:
        resolved = Path(path).resolve()
        base_resolved = base_dir.resolve()
        return str(resolved).startswith(str(base_resolved))
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת path: {e}")
        return False


async def update_cookies(new_cookies_path: str, destination: str = "cookies.txt") -> bool:
    """
    מחליף את קובץ ה-cookies הקיים בקובץ חדש
    
    Args:
        new_cookies_path: נתיב לקובץ cookies החדש (שהורד מהמשתמש)
        destination: נתיב היעד (ברירת מחדל: cookies.txt בתיקיית הפרויקט)
    
    Returns:
        True אם הצליח, False אחרת
    """
    try:
        logger.info(f"🍪 מעדכן קובץ cookies...")
        logger.info(f"  מקור: {new_cookies_path}")
        logger.info(f"  יעד: {destination}")
        
        if not os.path.exists(new_cookies_path):
            logger.error(f"❌ קובץ cookies מקור לא נמצא: {new_cookies_path}")
            return False
        
        # בדיקת path traversal - וידוא שהנתיב בטוח
        base_dir = Path.cwd()
        if not validate_path(new_cookies_path, base_dir):
            logger.error(f"❌ נתיב לא בטוח (path traversal): {new_cookies_path}")
            return False
        
        # בדיקת תקינות קובץ cookies
        if not validate_cookies_file(new_cookies_path):
            logger.error(f"❌ קובץ cookies לא תקין: {new_cookies_path}")
            return False
        
        # ולידציה בסיסית של פורמט הקובץ
        with open(new_cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if not content.strip():
                logger.error("❌ קובץ cookies ריק")
                return False
            
            # בדיקה בסיסית - צריך להכיל שורות עם tabs
            lines = content.strip().split('\n')
            valid_lines = sum(1 for line in lines 
                            if line.strip() and not line.startswith('#') 
                            and '\t' in line)
            
            if valid_lines == 0:
                logger.warning("⚠️ פורמט cookies עשוי להיות לא תקין")
        
        # גיבוי של cookies קיים
        if os.path.exists(destination):
            backup_path = destination + '.backup'
            logger.info(f"💾 יצירת גיבוי: {backup_path}")
            
            def _backup():
                import shutil
                shutil.copy2(destination, backup_path)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _backup)
        
        # העתקת הקובץ החדש
        def _copy():
            import shutil
            shutil.copy2(new_cookies_path, destination)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _copy)
        
        logger.info(f"✅ קובץ cookies עודכן בהצלחה")
        logger.info(f"📊 גודל קובץ: {os.path.getsize(destination)} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בעדכון cookies: {e}", exc_info=True)
        return False

