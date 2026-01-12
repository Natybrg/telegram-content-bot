"""
טסט מקצועי להעלאת קובץ וידאו ל-WhatsApp כ-MEDIA בלבד (ללא fallback ל-DOCUMENT)

שימוש:
    python test_whatsapp_upload.py                    # טסט עם קובץ אוטומטי
    python test_whatsapp_upload.py --file path/to/file # טסט עם קובץ ספציפי
    python test_whatsapp_upload.py --dry-run           # טסט ללא שליחה אמיתית
    python test_whatsapp_upload.py --list             # רשימת קבצים זמינים
"""
import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

# הוספת הנתיב של הפרויקט (תיקיית השורש)
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from services.whatsapp.delivery import WhatsAppDelivery

# ============================================
# Configuration
# ============================================

MAX_FILE_SIZE_GB = 2
MAX_VIDEO_AS_MEDIA_MB = 100

# ============================================
# Terminal Colors
# ============================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def color_text(text, color):
    """הוספת צבע לטקסט"""
    return f"{color}{text}{Colors.ENDC}"

# ============================================
# Logging Functions
# ============================================

def log_header(text):
    """לוג כותרת"""
    print("\n" + "="*60)
    print(color_text(text, Colors.HEADER + Colors.BOLD))
    print("="*60)

def log_success(text):
    """לוג הצלחה"""
    print(color_text(f"✅ {text}", Colors.GREEN))

def log_error(text):
    """לוג שגיאה"""
    print(color_text(f"❌ {text}", Colors.RED))

def log_warning(text):
    """לוג אזהרה"""
    print(color_text(f"⚠️  {text}", Colors.YELLOW))

def log_info(text):
    """לוג מידע"""
    print(color_text(f"ℹ️  {text}", Colors.CYAN))

def log_step(step_num, total_steps, text):
    """לוג שלב"""
    print(color_text(f"\n[{step_num}/{total_steps}] {text}", Colors.BLUE + Colors.BOLD))

# ============================================
# File Detection & Validation
# ============================================

def detect_file_type(file_path: str) -> Tuple[str, bool, bool]:
    """
    זיהוי סוג קובץ
    
    Returns:
        (mime_type, is_video, is_mp4)
    """
    ext = Path(file_path).suffix.lower()
    
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'}
    is_video = ext in video_extensions
    is_mp4 = ext == '.mp4'
    
    mime_map = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.m4v': 'video/mp4',
        '.3gp': 'video/3gpp'
    }
    
    mime_type = mime_map.get(ext, 'application/octet-stream')
    
    return mime_type, is_video, is_mp4

def validate_video_codec(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    בדיקת codec של וידאו באמצעות ffprobe
    מחזיר (is_valid, error_message)
    """
    ext = Path(file_path).suffix.lower()
    if ext != '.mp4':
        return False, f"קובץ לא MP4: {ext}. נדרש MP4 עם H.264"
    
    # בדיקה אם ffprobe זמין
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
             '-show_entries', 'stream=codec_name', '-of', 'json', file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            log_warning(f"ffprobe לא הצליח לבדוק את הקובץ: {result.stderr}")
            log_warning("ממשיך ללא בדיקת codec (רק בדיקת סיומת .mp4)")
            return True, None  # אם ffprobe נכשל, נמשיך רק עם בדיקת סיומת
        
        try:
            probe_data = json.loads(result.stdout)
            streams = probe_data.get('streams', [])
            if not streams:
                return False, "לא נמצא stream וידאו בקובץ"
            
            codec_name = streams[0].get('codec_name', '').lower()
            if codec_name != 'h264':
                return False, (
                    f"Codec לא נתמך: {codec_name}. נדרש H.264 (libx264).\n"
                    f"המרה: ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 23 output.mp4"
                )
            
            return True, None
        except json.JSONDecodeError:
            log_warning("לא הצלחתי לפרש את תוצאת ffprobe")
            log_warning("ממשיך ללא בדיקת codec (רק בדיקת סיומת .mp4)")
            return True, None
            
    except FileNotFoundError:
        log_warning("ffprobe לא נמצא. ממשיך ללא בדיקת codec (רק בדיקת סיומת .mp4)")
        return True, None
    except subprocess.TimeoutExpired:
        log_warning("ffprobe timeout. ממשיך ללא בדיקת codec (רק בדיקת סיומת .mp4)")
        return True, None
    except Exception as e:
        log_warning(f"שגיאה בבדיקת codec: {e}. ממשיך ללא בדיקת codec (רק בדיקת סיומת .mp4)")
        return True, None

def validate_file(file_path: str, strict_media_mode: bool = False):
    """בדיקת תקינות קובץ"""
    if not os.path.exists(file_path):
        return False, "קובץ לא נמצא"
    
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    file_size_gb = file_size / (1024 * 1024 * 1024)
    
    # בדיקת גודל מקסימלי
    if file_size_gb > MAX_FILE_SIZE_GB:
        return False, f"קובץ גדול מדי: {file_size_gb:.2f}GB (מקסימום: {MAX_FILE_SIZE_GB}GB)"
    
    mime_type, is_video, is_mp4 = detect_file_type(file_path)
    
    # במצב strict (רק MEDIA), דורש MP4 עם H.264
    if strict_media_mode:
        if not is_video or not is_mp4:
            return False, "במצב MEDIA בלבד: נדרש קובץ וידאו MP4"
        
        is_valid, codec_error = validate_video_codec(file_path)
        if not is_valid:
            return False, codec_error or "בעיה בבדיקת codec"
    
    return True, {
        'file_path': file_path,
        'file_size_bytes': file_size,
        'file_size_mb': file_size_mb,
        'file_size_gb': file_size_gb,
        'mime_type': mime_type,
        'is_video': is_video,
        'is_mp4': is_mp4
    }

# ============================================
# Strategy Determination
# ============================================

def determine_strategy(file_info, media_only: bool = False):
    """
    קביעת אסטרטגיית שליחה
    
    Args:
        file_info: מידע על הקובץ
        media_only: אם True, רק MEDIA (ללא fallback)
    
    Returns:
        {
            'primary': 'media' | 'document',
            'fallback': 'document' | None,
            'reason': str,
            'expected_method': str
        }
    """
    size_mb = file_info['file_size_mb']
    is_video = file_info['is_video']
    is_mp4 = file_info['is_mp4']
    
    if media_only:
        # במצב MEDIA בלבד - רק וידאו MP4
        if not is_video or not is_mp4:
            return {
                'primary': 'media',
                'fallback': None,
                'reason': 'MEDIA בלבד - נדרש וידאו MP4',
                'expected_method': 'wa_media'
            }
        
        return {
            'primary': 'media',
            'fallback': None,
            'reason': f'MEDIA בלבד - וידאו MP4 {size_mb:.2f}MB',
            'expected_method': 'wa_media'
        }
    
    # מצב רגיל (עם fallback)
    # Case 1: וידאו MP4 קטן מ-100MB
    if is_video and is_mp4 and size_mb <= MAX_VIDEO_AS_MEDIA_MB:
        risk = "נמוך" if size_mb <= 64 else "בינוני"
        return {
            'primary': 'media',
            'fallback': 'document',
            'reason': f'וידאו MP4 {size_mb:.2f}MB ≤ {MAX_VIDEO_AS_MEDIA_MB}MB (סיכון: {risk})',
            'expected_method': 'wa_media או wa_document (אם MEDIA נכשל)'
        }
    
    # Case 2: וידאו MP4 גדול מ-100MB
    if is_video and is_mp4 and size_mb > MAX_VIDEO_AS_MEDIA_MB:
        return {
            'primary': 'document',
            'fallback': None,
            'reason': f'וידאו MP4 {size_mb:.2f}MB > {MAX_VIDEO_AS_MEDIA_MB}MB',
            'expected_method': 'wa_document'
        }
    
    # Case 3: וידאו לא MP4
    if is_video and not is_mp4:
        ext = Path(file_info['file_path']).suffix
        return {
            'primary': 'document',
            'fallback': None,
            'reason': f'וידאו {ext} (לא MP4)',
            'expected_method': 'wa_document'
        }
    
    # Case 4: קובץ לא וידאו
    return {
        'primary': 'document',
        'fallback': None,
        'reason': 'קובץ לא וידאו',
        'expected_method': 'wa_document'
    }

# ============================================
# Main Test Function
# ============================================

def test_whatsapp_upload(
    file_path: Optional[str] = None,
    dry_run: Optional[bool] = None,
    prefer_large: bool = False,
    media_only: bool = False
) -> bool:
    """
    טסט העלאה ל-WhatsApp
    
    Args:
        file_path: נתיב לקובץ (אופציונלי)
        dry_run: אם True, לא ישלח בפועל
        prefer_large: אם True, יבחר את הקובץ הגדול ביותר
        media_only: אם True, רק MEDIA (ללא fallback ל-DOCUMENT)
    """
    log_header("🧪 טסט העלאה ל-WhatsApp" + (" (MEDIA בלבד)" if media_only else ""))
    
    # בדיקת הגדרות
    log_step(1, 5, "בדיקת הגדרות")
    
    if not config.WHATSAPP_ENABLED:
        log_error("WhatsApp לא מופעל ב-config")
        return False
    
    if not config.WHATSAPP_CHAT_NAME:
        log_error("לא הוגדר שם צ'אט ב-config")
        return False
    
    log_success(f"WhatsApp מופעל")
    log_success(f"שם צ'אט: {config.WHATSAPP_CHAT_NAME}")
    log_success(f"Service URL: {config.WHATSAPP_SERVICE_URL}")
    
    # קביעת dry_run
    use_dry_run = dry_run if dry_run is not None else config.WHATSAPP_DRY_RUN
    log_success(f"Dry Run: {use_dry_run}")
    
    if media_only:
        log_info("⚠️  מצב MEDIA בלבד - לא יהיה fallback ל-DOCUMENT")
    
    # חיפוש קובץ
    log_step(2, 5, "חיפוש קובץ")
    
    if not file_path:
        file_path = find_video_file(prefer_large=prefer_large)
        if not file_path:
            log_error("לא נמצא קובץ לטסט")
            log_info("הוסף קבצי וידאו לתיקייה: " + config.DOWNLOADS_PATH)
            return False
    
    # בדיקת תקינות (עם בדיקת codec במצב media_only)
    is_valid, result = validate_file(file_path, strict_media_mode=media_only)
    
    if not is_valid:
        log_error(f"קובץ לא תקין: {result}")
        if media_only:
            log_error("\n💡 טיפים לפתרון:")
            log_error("   1. ודא שהקובץ הוא MP4 עם H.264 (libx264)")
            log_error("   2. המרה: ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 23 output.mp4")
            log_error("   3. בדוק שהקובץ לא פגום")
        return False
    
    file_info = result
    log_success(f"נמצא קובץ: {Path(file_path).name} ({file_info['file_size_mb']:.2f} MB)")
    
    # בדיקת גודל
    if file_info['file_size_gb'] > MAX_FILE_SIZE_GB:
        log_error(f"קובץ גדול מדי: {file_info['file_size_gb']:.2f}GB > {MAX_FILE_SIZE_GB}GB")
        log_warning("הקובץ לא יישלח (מעל המגבלה של 2GB)")
        return False
    
    log_success(f"גודל קובץ: {file_info['file_size_mb']:.2f} MB (מתאים)")
    
    # קביעת אסטרטגיה
    log_step(3, 5, "קביעת אסטרטגיית שליחה")
    
    strategy = determine_strategy(file_info, media_only=media_only)
    
    log_info(f"אסטרטגיה עיקרית: {strategy['primary'].upper()}")
    if strategy['fallback']:
        log_info(f"Fallback: {strategy['fallback'].upper()}")
    else:
        log_info("Fallback: אין (MEDIA בלבד)" if media_only else "Fallback: אין")
    log_info(f"סיבה: {strategy['reason']}")
    log_info(f"צפוי: {strategy['expected_method']}")
    
    # יצירת WhatsApp delivery
    log_step(4, 5, "חיבור ל-WhatsApp Service")
    
    try:
        whatsapp = WhatsAppDelivery(dry_run=use_dry_run)
        log_success("WhatsApp Service מוכן")
    except Exception as e:
        log_error(f"שגיאה בחיבור ל-WhatsApp Service: {e}")
        return False
    
    # שליחה
    log_step(5, 5, "שליחת הקובץ")
    
    start_time = time.time()
    
    try:
        result = whatsapp.send_file(
            file_path=file_path,
            chat_name=config.WHATSAPP_CHAT_NAME,
            caption=f"🧪 טסט העלאה | {file_info['file_size_mb']:.2f}MB | {datetime.now().strftime('%H:%M:%S')}",
            file_type='video' if file_info['is_video'] else 'document',
            telegram_user_id=None,
            telegram_fallback_callback=None
        )
        
        duration = time.time() - start_time
        
        # ניתוח תוצאה
        log_header("📊 תוצאות")
        
        if isinstance(result, dict):
            success = result.get('success', False)
            delivered_via = result.get('delivered_via', 'unknown')
            
            if success:
                # במצב media_only - בדיקה שהנשלח הוא MEDIA
                if media_only:
                    if delivered_via != 'wa_media':
                        log_error(f"❌ נכשל: הקובץ נשלח כ-{delivered_via} במקום wa_media")
                        log_error("\n💡 סיבות אפשריות:")
                        log_error("   1. WhatsApp Web לא הצליח לעבד את הוידאו כ-MEDIA")
                        log_error("   2. בעיה עם whatsapp-web.js או WhatsApp Web API")
                        log_error("   3. הקובץ לא תואם לדרישות WhatsApp Web")
                        log_error("   4. בעיה עם Chrome/Chromium או puppeteer")
                        log_error("\n📋 פרטים נוספים:")
                        if 'attempts' in result:
                            attempts = result['attempts']
                            for attempt in attempts if isinstance(attempts, list) else []:
                                if not attempt.get('success'):
                                    log_error(f"   ניסיון {attempt.get('method', 'unknown')}: {attempt.get('error', 'לא ידוע')}")
                        return False
                
                log_success("נשלח בהצלחה!")
                log_info(f"דרך: {delivered_via}")
                log_info(f"זמן: {duration:.2f} שניות")
                
                # בדיקה אם זה מה שציפינו
                if media_only:
                    if delivered_via == 'wa_media':
                        log_success(f"✓ נשלח כ-MEDIA כצפוי: {delivered_via}")
                    else:
                        log_error(f"❌ נשלח כ-{delivered_via} במקום wa_media")
                        return False
                else:
                    if strategy['expected_method'].startswith(delivered_via) or delivered_via in strategy['expected_method']:
                        log_success(f"✓ נשלח בדרך הצפויה: {delivered_via}")
                    else:
                        log_warning(f"⚠ נשלח בדרך שונה מהצפוי:")
                        log_warning(f"   צפוי: {strategy['expected_method']}")
                        log_warning(f"   בפועל: {delivered_via}")
                
                # הצגת attempts
                if 'attempts' in result:
                    attempts = result['attempts']
                    log_info(f"מספר ניסיונות: {len(attempts) if isinstance(attempts, list) else 'N/A'}")
                
                return True
            else:
                log_error("נכשל!")
                log_info(f"דרך: {delivered_via}")
                error_msg = result.get('final_error', result.get('error', 'לא ידוע'))
                log_error(f"שגיאה: {error_msg}")
                
                if media_only:
                    log_error("\n💡 סיבות אפשריות:")
                    log_error("   1. WhatsApp Web לא הצליח לעבד את הוידאו כ-MEDIA")
                    log_error("   2. בעיה עם whatsapp-web.js או WhatsApp Web API")
                    log_error("   3. הקובץ לא תואם לדרישות WhatsApp Web (MP4 + H.264)")
                    log_error("   4. בעיה עם Chrome/Chromium או puppeteer")
                    log_error("   5. שגיאת 'Evaluation failed: t' - בעיה ידועה ב-whatsapp-web.js")
                
                # הצגת attempts
                if 'attempts' in result:
                    attempts = result['attempts']
                    log_info(f"מספר ניסיונות: {len(attempts) if isinstance(attempts, list) else 'N/A'}")
                    for attempt in attempts if isinstance(attempts, list) else []:
                        if not attempt.get('success'):
                            log_error(f"   ניסיון {attempt.get('method', 'unknown')}: {attempt.get('error', 'לא ידוע')}")
                
                # בדיקה אם צריך fallback לטלגרם
                if result.get('should_send_telegram'):
                    log_warning("📨 נדרש fallback לטלגרם")
                    log_info("בסביבת ייצור, הקובץ היה נשלח לטלגרם")
                
                return False
        else:
            # פורמט ישן
            log_success("נשלח בהצלחה!")
            log_info(f"זמן: {duration:.2f} שניות")
            return True
        
    except Exception as e:
        duration = time.time() - start_time
        log_error(f"שגיאה בשליחה: {e}")
        log_info(f"זמן עד כישלון: {duration:.2f} שניות")
        if media_only:
            log_error("\n💡 סיבות אפשריות:")
            log_error("   1. שגיאה בחיבור ל-WhatsApp Service")
            log_error("   2. בעיה עם whatsapp-web.js")
            log_error("   3. בעיה עם הקובץ או הנתיב")
        return False

# ============================================
# Helper Functions
# ============================================

def list_video_files():
    """רשימת כל קבצי הוידאו"""
    downloads_dir = Path(config.DOWNLOADS_PATH)
    
    if not downloads_dir.exists():
        return []
    
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.3gp']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(downloads_dir.glob(f'*{ext}')))
    
    return video_files

def find_video_file(prefer_large=False):
    """מציאת קובץ וידאו"""
    video_files = list_video_files()
    
    if not video_files:
        return None
    
    # סינון קבצים תקפים (עד 2GB)
    valid_files = []
    for video_file in video_files:
        size_mb = video_file.stat().st_size / (1024 * 1024)
        size_gb = size_mb / 1024
        if size_gb <= MAX_FILE_SIZE_GB:
            valid_files.append((video_file, size_mb))
    
    if not valid_files:
        return None
    
    # מיון לפי העדפה
    valid_files.sort(key=lambda x: x[1], reverse=prefer_large)
    selected_file, _ = valid_files[0]
    
    return str(selected_file)

# ============================================
# CLI Main
# ============================================

def main():
    """פונקציה ראשית"""
    parser = argparse.ArgumentParser(
        description='טסט העלאה ל-WhatsApp',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
דוגמאות:
  python test_whatsapp_upload.py                    # טסט רגיל
  python test_whatsapp_upload.py --file video.mp4   # טסט עם קובץ ספציפי
  python test_whatsapp_upload.py --dry-run          # טסט ללא שליחה
  python test_whatsapp_upload.py --list             # רשימת קבצים
  python test_whatsapp_upload.py --large            # הקובץ הגדול ביותר
  python test_whatsapp_upload.py --media-only       # MEDIA בלבד (ללא fallback)
        """
    )
    
    parser.add_argument('--file', '-f', type=str, help='נתיב לקובץ ספציפי')
    parser.add_argument('--dry-run', '-d', action='store_true', help='לא לשלוח בפועל')
    parser.add_argument('--list', '-l', action='store_true', help='הצג רשימת קבצים')
    parser.add_argument('--large', action='store_true', help='בחר את הקובץ הגדול ביותר')
    parser.add_argument('--media-only', '-m', action='store_true', 
                       help='שליחה כ-MEDIA בלבד (ללא fallback ל-DOCUMENT). נדרש MP4 עם H.264')
    
    args = parser.parse_args()
    
    # הצגת רשימת קבצים
    if args.list:
        log_header("📋 רשימת קבצי וידאו זמינים")
        
        video_files = list_video_files()
        
        if not video_files:
            log_error("לא נמצאו קבצי וידאו")
            log_info(f"תיקייה: {config.DOWNLOADS_PATH}")
            return 0
        
        valid_files = []
        invalid_files = []
        
        for video_file in video_files:
            size_mb = video_file.stat().st_size / (1024 * 1024)
            size_gb = size_mb / 1024
            mime_type, is_video, is_mp4 = detect_file_type(str(video_file))
            
            if size_gb <= MAX_FILE_SIZE_GB:
                valid_files.append((video_file, size_mb, is_mp4))
            else:
                invalid_files.append((video_file, size_mb))
        
        if valid_files:
            print(f"\n{color_text('✅ קבצים תקפים:', Colors.GREEN)}")
            valid_files.sort(key=lambda x: x[1])
            
            for video_file, size_mb, is_mp4 in valid_files:
                format_emoji = "🎬" if is_mp4 else "📹"
                size_color = Colors.GREEN if size_mb <= MAX_VIDEO_AS_MEDIA_MB else Colors.YELLOW
                print(f"   {format_emoji} {video_file.name}: {color_text(f'{size_mb:.2f} MB', size_color)}")
                
                # הסבר איך יישלח
                if is_mp4 and size_mb <= MAX_VIDEO_AS_MEDIA_MB:
                    print(f"      → ינסה MEDIA (וידאו לצפייה), fallback ל-DOCUMENT")
                    print(f"      → או: --media-only לשליחה כ-MEDIA בלבד")
                elif is_mp4 and size_mb > MAX_VIDEO_AS_MEDIA_MB:
                    print(f"      → DOCUMENT בלבד (מעל {MAX_VIDEO_AS_MEDIA_MB}MB)")
                else:
                    print(f"      → DOCUMENT בלבד (לא MP4)")
        
        if invalid_files:
            print(f"\n{color_text('⚠️  קבצים גדולים מדי:', Colors.RED)}")
            for video_file, size_mb in invalid_files:
                print(f"   ❌ {video_file.name}: {size_mb:.2f} MB")
        
        print("\n" + "="*60)
        return 0
    
    # הרצת טסט
    success = test_whatsapp_upload(
        file_path=args.file,
        dry_run=args.dry_run,
        prefer_large=args.large,
        media_only=args.media_only
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())