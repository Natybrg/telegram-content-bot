"""
FFmpeg Utilities
פונקציות עזר לעבודה עם FFmpeg - קודקים, המרות, דחיסה
"""
import os
import logging
import asyncio
import subprocess
import re
import shutil
from typing import Optional, Tuple, Dict, Any
from functools import lru_cache
import time
import multiprocessing

logger = logging.getLogger(__name__)

# פונקציה עזר לחישוב מספר threads
def _get_optimal_threads() -> int:
    """מחזיר מספר threads אופטימלי ל-FFmpeg"""
    return min(multiprocessing.cpu_count(), 8)


def check_available_memory(min_gb: float = 2.0) -> bool:
    """
    בודק אם יש מספיק זיכרון פנוי לפני המרה כבדה
    
    Args:
        min_gb: כמות זיכרון מינימלית נדרשת ב-GB (ברירת מחדל: 2GB)
    
    Returns:
        True אם יש מספיק זיכרון, False אחרת
    """
    try:
        import psutil  # type: ignore
        available_gb = psutil.virtual_memory().available / (1024**3)
        if available_gb < min_gb:
            logger.warning(f"⚠️ זיכרון פנוי נמוך: {available_gb:.2f}GB < {min_gb}GB")
            return False
        logger.debug(f"✅ זיכרון פנוי: {available_gb:.2f}GB")
        return True
    except ImportError:
        # אם psutil לא מותקן, מחזירים True (לא חוסמים)
        logger.debug("⚠️ psutil לא מותקן, דילוג על בדיקת זיכרון")
        return True
    except Exception as e:
        logger.warning(f"⚠️ שגיאה בבדיקת זיכרון: {e}")
        return True  # לא חוסמים אם יש שגיאה

# Cache לבדיקת זמינות FFmpeg
_ffmpeg_available: Optional[bool] = None
_ffmpeg_check_done: bool = False


async def check_ffmpeg_available() -> bool:
    """
    בודק אם FFmpeg מותקן וזמין ב-PATH
    מחזיר True אם זמין, False אחרת
    """
    global _ffmpeg_available, _ffmpeg_check_done
    
    # אם כבר בדקנו, מחזירים את התוצאה
    if _ffmpeg_check_done:
        return _ffmpeg_available if _ffmpeg_available is not None else False
    
    try:
        result = await asyncio.create_subprocess_exec(
            'ffmpeg', '-version',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.wait()
        _ffmpeg_available = result.returncode == 0
        _ffmpeg_check_done = True
        
        if _ffmpeg_available:
            logger.info("✅ FFmpeg is available")
        else:
            logger.error("❌ FFmpeg is not available (return code != 0)")
        
        return _ffmpeg_available
    except FileNotFoundError:
        logger.error("❌ FFmpeg is not installed or not in PATH")
        _ffmpeg_available = False
        _ffmpeg_check_done = True
        return False
    except Exception as e:
        logger.error(f"❌ Error checking FFmpeg availability: {e}")
        _ffmpeg_available = False
        _ffmpeg_check_done = True
        return False


# Cache לתוצאות ffprobe (למניעת קריאות מיותרות)
_codec_cache = {}
# Cache עם TTL (Time To Live) - 5 דקות
_cache_ttl = 300  # 5 דקות בשניות
_cache_timestamps = {}


def _is_h264_compatible(codec_name: str, codec_tag: str) -> bool:
    """
    בודק אם קודק וידאו תואם H.264 (case-insensitive)
    """
    codec_name_lower = codec_name.lower() if codec_name else ""
    codec_tag_lower = codec_tag.lower() if codec_tag else ""
    
    return codec_name_lower == "h264" or codec_tag_lower.startswith("avc1")


def _is_aac_compatible(codec_name: str, codec_tag: str) -> bool:
    """
    בודק אם קודק אודיו תואם AAC (case-insensitive)
    """
    codec_name_lower = codec_name.lower() if codec_name else ""
    codec_tag_lower = codec_tag.lower() if codec_tag else ""
    
    return codec_name_lower == "aac" or "mp4a" in codec_tag_lower


def _get_preset_priority_list(video_codec: str = None) -> list:
    """
    מחזיר רשימת presets לפי סדר עדיפות (מהיר → איטי)
    תמיד ננסה את המהיר ביותר קודם
    
    Args:
        video_codec: קודק הוידאו (אופציונלי)
    
    Returns:
        רשימת presets: ['veryfast', 'fast', 'medium', ...]
    """
    codec_lower = video_codec.lower() if video_codec else ""
    
    # עבור AV1/VP9 - תמיד ננסה preset מהיר יותר קודם (המרה כבדה ממילא)
    if codec_lower in ['av1', 'av01', 'vp9', 'vp09']:
        return ['veryfast', 'fast', 'medium']
    
    # עבור קודקים אחרים - ננסה מהיר → איטי
    return ['veryfast', 'fast', 'medium', 'slow']


def _get_optimal_preset(file_size_mb: float, duration: float = None, video_codec: str = None) -> str:
    """
    מחזיר preset אופטימלי לפי גודל קובץ, משך וקודק
    תמיד מחזיר את המהיר ביותר (הפונקציה הזו משמשת רק ל-initial attempt)
    
    Args:
        file_size_mb: גודל הקובץ ב-MB
        duration: משך הוידאו בשניות (אופציונלי)
        video_codec: קודק הוידאו (אופציונלי)
    
    Returns:
        שם preset: 'veryfast', 'fast', 'medium', 'slow'
    """
    # תמיד נחזיר את המהיר ביותר - אם נכשל, ננסה איטי יותר
    priority_list = _get_preset_priority_list(video_codec)
    return priority_list[0]  # תמיד המהיר ביותר


def _detect_hardware_encoder() -> Optional[str]:
    """
    בודק אם יש hardware encoder זמין
    
    Returns:
        שם encoder: 'h264_nvenc', 'h264_qsv', 'h264_videotoolbox', או None
    """
    try:
        # בדיקת NVENC (NVIDIA)
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if 'h264_nvenc' in result.stdout:
            logger.info("✅ Hardware encoder detected: NVIDIA NVENC")
            return 'h264_nvenc'
        elif 'h264_qsv' in result.stdout:
            logger.info("✅ Hardware encoder detected: Intel QuickSync")
            return 'h264_qsv'
        elif 'h264_videotoolbox' in result.stdout:
            logger.info("✅ Hardware encoder detected: VideoToolbox (macOS)")
            return 'h264_videotoolbox'
    except:
        pass
    
    return None


def _needs_special_decoder(video_codec: str) -> Optional[str]:
    """
    בודק אם צריך decoder מיוחד לקודק מסוים
    
    Args:
        video_codec: שם הקודק (למשל 'av1', 'vp9')
    
    Returns:
        שם decoder או None אם לא נדרש
    """
    if not video_codec:
        return None
    
    codec_lower = video_codec.lower()
    
    # AV1 דורש decoder מיוחד
    if codec_lower in ['av1', 'av01']:
        # ננסה libdav1d (מהיר יותר) או libaom
        return 'libdav1d'
    
    # VP9 - FFmpeg יכול לטפל בזה אוטומטית, אבל אפשר לציין במפורש
    if codec_lower in ['vp9', 'vp09']:
        return 'libvpx-vp9'
    
    return None


def _get_hardware_encoder_params(encoder: str, preset: str) -> list:
    """
    מחזיר פרמטרים ספציפיים ל-hardware encoder
    
    Args:
        encoder: שם ה-encoder (למשל 'h264_nvenc')
        preset: preset (למשל 'medium')
    
    Returns:
        רשימת פרמטרים ל-FFmpeg
    """
    params = []
    
    if encoder == 'h264_nvenc':
        # NVENC דורש preset שונה (p1-p7 במקום veryfast-slow)
        preset_map = {
            'veryfast': 'p1',
            'fast': 'p3',
            'medium': 'p4',
            'slow': 'p6'
        }
        nvenc_preset = preset_map.get(preset, 'p4')
        params.extend([
            '-preset', nvenc_preset,
            '-rc', 'vbr',  # Variable bitrate
            '-cq', '23',   # Constant quality (דומה ל-CRF)
            '-b:v', '0',   # Bitrate 0 = CQ mode
        ])
    elif encoder == 'h264_qsv':
        # QuickSync
        params.extend([
            '-preset', preset,
            '-global_quality', '23',
        ])
    elif encoder == 'h264_videotoolbox':
        # VideoToolbox (macOS)
        params.extend([
            '-quality', '1',  # 0-3, 1 = high quality
            '-allow_sw', '1',  # Allow software fallback
        ])
    
    return params


async def parse_ffprobe_output(
    video_path: str,
    select_streams: str,
    show_entries: str,
    use_cache: bool = True
) -> Optional[Dict[str, str]]:
    """
    פונקציה גנרית ל-parsing של ffprobe output
    
    Args:
        video_path: נתיב לקובץ וידאו
        select_streams: stream selector (למשל "v:0" או "a:0")
        show_entries: entries להצגה (למשל "stream=codec_name,codec_tag_string")
        use_cache: האם להשתמש ב-cache
    
    Returns:
        Dictionary עם הערכים שנמצאו או None
    """
    cache_key = f"{video_path}_{select_streams}_{show_entries}"
    
    # בדיקת cache
    if use_cache and cache_key in _codec_cache:
        if cache_key in _cache_timestamps:
            age = time.time() - _cache_timestamps[cache_key]
            if age < _cache_ttl:
                logger.debug(f"📦 Using cached ffprobe result for: {cache_key}")
                return _codec_cache[cache_key]
            else:
                # Cache expired
                del _codec_cache[cache_key]
                del _cache_timestamps[cache_key]
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', select_streams,
            '-show_entries', show_entries,
            '-of', 'default=noprint_wrappers=1',
            video_path
        ]
        
        def _probe():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                check=True
            )
            return result.stdout.strip()
        
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, _probe)
        
        # Parse output - מחפש key=value
        result = {}
        for line in output.split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # הסרת prefix "TAG:" אם קיים
                if key.startswith('TAG:'):
                    key = key[4:]
                result[key] = value
        
        # שמירה ב-cache
        if use_cache and result:
            _codec_cache[cache_key] = result
            _cache_timestamps[cache_key] = time.time()
        
        return result if result else None
        
    except Exception as e:
        logger.error(f"❌ שגיאה ב-ffprobe parsing: {e}")
        return None


async def get_video_codec(video_path: str, use_cache: bool = True) -> Optional[Tuple[str, str]]:
    """
    מחזיר את קודק הוידאו וה-codec_tag באמצעות ffprobe
    עם caching למניעת קריאות מיותרות
    
    Args:
        video_path: נתיב לקובץ וידאו
        use_cache: האם להשתמש ב-cache (ברירת מחדל: True)
    
    Returns: Tuple of (codec_name, codec_tag_string) או None
    """
    # בדיקת cache
    if use_cache and video_path in _codec_cache:
        cache_key = f"{video_path}_video"
        if cache_key in _codec_cache:
            logger.debug(f"📦 Using cached video codec for: {video_path}")
            return _codec_cache[cache_key]
    
    try:
        # שימוש בפונקציה הגנרית
        parsed = await parse_ffprobe_output(
            video_path,
            'v:0',
            'stream=codec_name,codec_tag_string',
            use_cache
        )
        
        if not parsed:
            return None
        
        codec_name = parsed.get('codec_name', '')
        codec_tag = parsed.get('codec_tag_string', '')
        
        return (codec_name, codec_tag)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקבלת קודק וידאו: {e}")
        return None


async def get_audio_codec(video_path: str, use_cache: bool = True) -> Optional[Tuple[str, str]]:
    """
    מחזיר את קודק האודיו וה-codec_tag באמצעות ffprobe
    עם caching למניעת קריאות מיותרות
    
    Args:
        video_path: נתיב לקובץ וידאו
        use_cache: האם להשתמש ב-cache (ברירת מחדל: True)
    
    Returns: Tuple of (codec_name, codec_tag_string) או None
    """
    # בדיקת cache
    if use_cache and video_path in _codec_cache:
        cache_key = f"{video_path}_audio"
        if cache_key in _codec_cache:
            logger.debug(f"📦 Using cached audio codec for: {video_path}")
            return _codec_cache[cache_key]
    
    try:
        # שימוש בפונקציה הגנרית
        parsed = await parse_ffprobe_output(
            video_path,
            'a:0',
            'stream=codec_name,codec_tag_string',
            use_cache
        )
        
        if not parsed:
            return None
        
        codec_name = parsed.get('codec_name', '')
        codec_tag = parsed.get('codec_tag_string', '')
        
        return (codec_name, codec_tag)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקבלת קודק אודיו: {e}")
        return None


async def get_video_duration(video_path: str) -> Optional[float]:
    """
    מחזיר את משך הוידאו בשניות באמצעות ffprobe
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        def _probe():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return float(result.stdout.strip())
        
        loop = asyncio.get_event_loop()
        duration = await loop.run_in_executor(None, _probe)
        return duration
        
    except Exception as e:
        logger.error(f"❌ שגיאה בקבלת משך וידאו: {e}")
        return None


async def get_video_dimensions(video_path: str) -> Optional[Tuple[int, int]]:
    """
    מחזיר את הממדים האמיתיים של הוידאו (width, height) כפי שהם מוצגים
    לוקח בחשבון rotation metadata - אם הוידאו מסובב 90° או 270°, מחליף width↔height
    
    Args:
        video_path: נתיב לקובץ וידאו
    
    Returns:
        Tuple של (width, height) או None אם נכשל
    """
    try:
        logger.info(f"📐 מחלץ ממדי וידאו: {video_path}")
        
        # שימוש ב-parse_ffprobe_output במקום parsing ידני
        parsed = await parse_ffprobe_output(
            video_path=video_path,
            select_streams='v:0',
            show_entries='stream=width,height:stream_tags=rotate',
            use_cache=True
        )
        
        if not parsed:
            logger.error(f"❌ לא ניתן לחלץ ממדים מ-{video_path}")
            return None
        
        # חילוץ width, height ו-rotation
        width = parsed.get('width')
        height = parsed.get('height')
        rotation_str = parsed.get('rotate', '0')
        
        # המרה למספרים
        try:
            width = int(width) if width else None
            height = int(height) if height else None
            rotation = int(rotation_str) if rotation_str else 0
        except (ValueError, TypeError):
            logger.warning(f"⚠️ שגיאה בהמרת ממדים למספרים: width={width}, height={height}, rotation={rotation_str}")
            rotation = 0
        
        if width is None or height is None:
            logger.error(f"❌ לא ניתן לחלץ ממדים מ-{video_path}")
            return None
        
        # אם הוידאו מסובב 90° או 270°, נחליף width ו-height
        if rotation in [90, 270]:
            logger.info(f"🔄 וידאו מסובב {rotation}°, מחליף width↔height")
            width, height = height, width
        
        logger.info(f"📐 ממדי וידאו: {width}x{height} (rotation: {rotation}°)")
        return (width, height)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בחילוץ ממדי וידאו: {e}")
        return None


async def convert_to_compatible_format(input_path: str, progress_callback=None) -> Optional[str]:
    """
    ממיר וידאו לפורמט תואם לכל המכשירים (H.264 + AAC)
    בודק אם הקובץ כבר בפורמט הנכון, ואם לא - ממיר אותו
    
    Args:
        input_path: נתיב לקובץ קלט
        progress_callback: פונקציה לעדכון התקדמות (מקבלת: percent, current_time, eta)
    
    Returns:
        נתיב לקובץ המומר או הקובץ המקורי (אם כבר תואם)
    """
    try:
        logger.info(f"🔍 בודק פורמט וידאו: {input_path}")
        
        if not os.path.exists(input_path):
            logger.error(f"❌ קובץ לא נמצא: {input_path}")
            return None
        
        # בדיקת קודקים נוכחיים
        video_info = await get_video_codec(input_path)
        audio_info = await get_audio_codec(input_path)
        
        if video_info and audio_info:
            video_codec, video_tag = video_info
            audio_codec, audio_tag = audio_info
            
            logger.info(f"📊 קודק וידאו נוכחי: {video_codec} ({video_tag})")
            logger.info(f"📊 קודק אודיו נוכחי: {audio_codec} ({audio_tag})")
            
            # בדיקה אם כבר בפורמט תואם (case-insensitive)
            if _is_h264_compatible(video_codec, video_tag) and _is_aac_compatible(audio_codec, audio_tag):
                logger.info("✅ הקובץ כבר בפורמט תואם (H.264 + AAC)")
                return input_path
        else:
            logger.warning("⚠️ לא ניתן לקבוע קודקים, ממשיך להמרה...")
            # הגדרת ערכי ברירת מחדל אם לא ניתן לקבוע קודקים
            video_codec = ""
            video_tag = ""
            audio_codec = ""
            audio_tag = ""
        
        # קבלת משך הוידאו לחישוב התקדמות
        duration = await get_video_duration(input_path)
        if not duration:
            logger.warning("⚠️ לא ניתן לקבל משך וידאו - התקדמות לא תוצג")
        
        # קבלת גודל קובץ לאופטימיזציה
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        
        # יצירת נתיב פלט
        output_path = input_path.rsplit('.', 1)[0] + '_compatible.mp4'
        
        # בדיקה מה צריך להמיר
        video_compatible = _is_h264_compatible(video_codec, video_tag) if video_info and video_codec else False
        audio_compatible = _is_aac_compatible(audio_codec, audio_tag) if audio_info and audio_codec else False
        
        logger.info(f"🔄 ממיר לפורמט תואם...")
        
        # בדיקת זיכרון לפני המרה כבדה
        if not check_available_memory(min_gb=2.0):
            logger.error("❌ אין מספיק זיכרון פנוי להמרה (נדרש לפחות 2GB)")
            return None
        
        # בדיקה אם הקודק הוא AV1/VP9 (דורש decoder מיוחד)
        codec_lower = video_codec.lower() if video_codec else ""
        is_av1_or_vp9 = codec_lower in ['av1', 'av01', 'vp9', 'vp09']
        
        # זיהוי hardware encoder (תמיד ננסה hardware קודם אם זמין)
        hw_encoder = _detect_hardware_encoder()
        
        # רשימת ניסיונות: תמיד ננסה את המהיר ביותר קודם
        # עבור AV1/VP9: ננסה hardware encoder עם decoder אוטומטי, אם נכשל - libx264
        # עבור קודקים אחרים: ננסה hardware encoder, אם נכשל - libx264
        encoder_priority = []
        
        if is_av1_or_vp9:
            # עבור AV1/VP9 - ננסה hardware encoder קודם (אם זמין)
            # FFmpeg יכול להשתמש ב-hardware decoder אוטומטית אם זמין
            if hw_encoder:
                encoder_priority.append((hw_encoder, True, "hardware encoder (אוטומטי decoder)"))
            encoder_priority.append(('libx264', False, "libx264 (software)"))
        else:
            # עבור קודקים אחרים - hardware קודם
            if hw_encoder:
                encoder_priority.append((hw_encoder, True, "hardware encoder"))
            encoder_priority.append(('libx264', False, "libx264 (software)"))
        
        # רשימת presets לפי עדיפות (מהיר → איטי)
        preset_priority = _get_preset_priority_list(video_codec)
        
        # ניסיון המרה עם fallback אוטומטי ו-retry logic
        last_error = None
        max_retries = 2  # מספר ניסיונות נוספים עם פרמטרים שונים
        
        for encoder, use_hw, encoder_desc in encoder_priority:
            for preset in preset_priority:
                logger.info(f"🚀 מנסה: {encoder_desc}, preset: {preset}")
                
                # ניסיון ראשון
                try:
                    result = await _try_convert(
                        input_path, output_path, encoder, use_hw, preset,
                        video_compatible, audio_compatible,
                        video_codec, video_tag, audio_codec, audio_tag,
                        duration, progress_callback
                    )
                    
                    if result:
                        logger.info(f"✅ המרה הצליחה עם: {encoder_desc}, preset: {preset}")
                        
                        # בדיקת איכות אחרי המרה
                        original_size_mb = os.path.getsize(input_path) / (1024 * 1024)
                        converted_size_mb = os.path.getsize(result) / (1024 * 1024)
                        
                        logger.info(f"📊 גודל מקורי: {original_size_mb:.2f} MB")
                        logger.info(f"📊 גודל מומר: {converted_size_mb:.2f} MB")
                        
                        # בדיקת bitrate בסיסית (אם הקובץ גדל משמעותית, יש בעיה)
                        if converted_size_mb > original_size_mb * 1.5:
                            logger.warning(f"⚠️ הקובץ המומר גדול ב-{((converted_size_mb/original_size_mb - 1) * 100):.1f}% מהמקורי - ייתכן שיש בעיה באיכות")
                        
                        # בדיקת bitrate מינימלי (אם הקובץ קטן מדי, ייתכן שהאיכות נמוכה מדי)
                        if duration and duration > 0:
                            estimated_bitrate_mbps = (converted_size_mb * 8) / duration
                            if estimated_bitrate_mbps < 0.5:  # פחות מ-0.5 Mbps
                                logger.warning(f"⚠️ Bitrate משוער נמוך מאוד: {estimated_bitrate_mbps:.2f} Mbps - ייתכן שהאיכות נמוכה")
                        
                        # ניקוי cache (הקובץ השתנה)
                        cache_keys_to_remove = [k for k in _codec_cache.keys() if input_path in k]
                        for key in cache_keys_to_remove:
                            del _codec_cache[key]
                        
                        if progress_callback:
                            try:
                                progress_callback(100, int(duration) if duration else 0, 0)
                            except:
                                pass
                        
                        return result
                        
                except Exception as e:
                    last_error = e
                    logger.warning(f"⚠️ נכשל עם {encoder_desc}, preset: {preset}: {str(e)[:100]}")
                    
                    # Retry עם preset מהיר יותר או CRF גבוה יותר
                    if preset != preset_priority[-1]:  # אם זה לא ה-preset האחרון
                        # ננסה preset מהיר יותר
                        faster_preset_index = preset_priority.index(preset) + 1
                        if faster_preset_index < len(preset_priority):
                            faster_preset = preset_priority[faster_preset_index]
                            logger.info(f"🔄 Retry עם preset מהיר יותר: {faster_preset}")
                            try:
                                # יצירת output path חדש
                                retry_output_path = output_path.rsplit('.', 1)[0] + '_retry.mp4'
                                result = await _try_convert(
                                    input_path, retry_output_path, encoder, use_hw, faster_preset,
                                    video_compatible, audio_compatible,
                                    video_codec, video_tag, audio_codec, audio_tag,
                                    duration, progress_callback
                                )
                                if result:
                                    logger.info(f"✅ Retry הצליח עם preset: {faster_preset}")
                                    # העברת הקובץ ל-output_path המקורי
                                    if retry_output_path != output_path:
                                        if os.path.exists(output_path):
                                            os.remove(output_path)
                                        shutil.move(retry_output_path, output_path)
                                        result = output_path
                                    
                                    # בדיקת איכות
                                    original_size_mb = os.path.getsize(input_path) / (1024 * 1024)
                                    converted_size_mb = os.path.getsize(result) / (1024 * 1024)
                                    logger.info(f"📊 גודל מקורי: {original_size_mb:.2f} MB, מומר: {converted_size_mb:.2f} MB")
                                    
                                    # ניקוי cache
                                    cache_keys_to_remove = [k for k in _codec_cache.keys() if input_path in k]
                                    for key in cache_keys_to_remove:
                                        del _codec_cache[key]
                                    
                                    if progress_callback:
                                        try:
                                            progress_callback(100, int(duration) if duration else 0, 0)
                                        except:
                                            pass
                                    
                                    return result
                            except Exception as retry_error:
                                logger.warning(f"⚠️ Retry נכשל: {str(retry_error)[:100]}")
                    
                    # ממשיך לניסיון הבא
                    continue
        
        # אם כל הניסיונות נכשלו
        if last_error:
            logger.error(f"❌ כל הניסיונות נכשלו. שגיאה אחרונה: {last_error}")
        return None
        
    except Exception as e:
        logger.error(f"❌ שגיאה כללית בהמרת פורמט: {e}", exc_info=True)
        return None


async def _try_convert(
    input_path: str, output_path: str, encoder: str, use_hw: bool, preset: str,
    video_compatible: bool, audio_compatible: bool,
    video_codec: str, video_tag: str, audio_codec: str, audio_tag: str,
    duration: float, progress_callback
) -> Optional[str]:
    """
    מנסה לבצע המרה אחת עם פרמטרים ספציפיים
    
    Returns:
        נתיב לקובץ המומר אם הצליח, None אם נכשל
    """
    threads = _get_optimal_threads()
    
    # בניית פקודת ffmpeg
    cmd = ['ffmpeg', '-i', input_path]
        
    if not video_compatible and not audio_compatible:
        # שני הקודקים לא תואמים - מתמלל שניהם
        if use_hw:
            hw_params = _get_hardware_encoder_params(encoder, preset)
            cmd.extend(['-c:v', encoder])
            cmd.extend(hw_params)
            cmd.extend([
                '-threads', str(threads),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '2',
            ])
        else:
            cmd.extend([
                '-c:v', encoder,
                '-preset', preset,
                '-crf', '23',
                '-threads', str(threads),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '2',
            ])
    elif not video_compatible:
        # רק וידאו לא תואם - מתמלל וידאו, מעתיק אודיו
        if use_hw:
            hw_params = _get_hardware_encoder_params(encoder, preset)
            cmd.extend(['-c:v', encoder])
            cmd.extend(hw_params)
            cmd.extend([
                '-threads', str(threads),
                '-c:a', 'copy',
            ])
        else:
            cmd.extend([
                '-c:v', encoder,
                '-preset', preset,
                '-crf', '23',
                '-threads', str(threads),
                '-c:a', 'copy',
            ])
    elif not audio_compatible:
        # רק אודיו לא תואם - מעתיק וידאו, מתמלל אודיו
        cmd.extend([
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
        ])
    
    # הוספת אופטימיזציה לסטרימינג ונתיב פלט
    cmd.extend([
        '-movflags', '+faststart',
        '-y',
        output_path
    ])
    
    def _convert():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=0
        )
        
        last_percent = 0
        time_pattern = re.compile(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})')
        error_output = []
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            
            if 'error' in line.lower() or 'failed' in line.lower():
                error_output.append(line)
            
            match = time_pattern.search(line)
            if match and duration and duration > 0:
                try:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds
                    
                    percent = min(int((current_time / duration) * 100), 99)
                    
                    if percent >= last_percent + 1 or percent == 99:
                        last_percent = percent
                        eta = int((duration - current_time))
                        logger.info(f"⏳ המרה: {percent}% | זמן: {int(current_time)}s / {int(duration)}s | ETA: ~{eta}s")
                        
                        if progress_callback:
                            try:
                                progress_callback(percent, int(current_time), eta)
                            except:
                                pass
                except Exception:
                    pass
        
        returncode = process.wait()
        
        if returncode != 0:
            error_msg = '\n'.join(error_output[-5:]) if error_output else "Check logs above"
            raise subprocess.CalledProcessError(returncode, cmd, stderr=error_msg)
        
        return returncode
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _convert)
        
        if not os.path.exists(output_path):
            return None
        
        # בדיקת קודקים של הקובץ המומר
        converted_video_info = await get_video_codec(output_path, use_cache=False)
        converted_audio_info = await get_audio_codec(output_path, use_cache=False)
        
        if converted_video_info and converted_audio_info:
            conv_video_codec, conv_video_tag = converted_video_info
            conv_audio_codec, conv_audio_tag = converted_audio_info
            
            if _is_h264_compatible(conv_video_codec, conv_video_tag) and _is_aac_compatible(conv_audio_codec, conv_audio_tag):
                return output_path
        
        # הקובץ לא תואם - נמחק ונחזיר None
        try:
            os.remove(output_path)
        except:
            pass
        return None
        
    except subprocess.CalledProcessError as e:
        # נכשל - נמחק קובץ חלקי אם קיים
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"❌ FFmpeg נכשל בהמרה: {error_msg}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        # ניקוי קבצי log אם נכשל
        for log_file in ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']:
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except:
                    pass
        return None
    except Exception as e:
        logger.error(f"❌ שגיאה בניסיון המרה: {e}", exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        # ניקוי קבצי log אם נכשל
        for log_file in ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']:
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except:
                    pass
        return None


async def compress_video(
    input_path: str,
    target_size_mb: Optional[int] = None,
    target_bitrate: Optional[int] = None,
    method: str = "single_pass",
    filename_suffix: str = "_compressed",
    progress_callback=None,
    check_size: bool = True
) -> Optional[str]:
    """
    פונקציה מאוחדת לדחיסת וידאו
    
    Args:
        input_path: נתיב לקובץ קלט
        target_size_mb: גודל יעד ב-MB (אם None, משתמש ב-target_bitrate)
        target_bitrate: bitrate יעד ב-kbps (אם None, מחשב מ-target_size_mb)
        method: שיטת דחיסה - "single_pass" או "two_pass" (ברירת מחדל: "single_pass")
        filename_suffix: סיומת לשם הקובץ הפלט
        progress_callback: פונקציה לעדכון התקדמות (מקבלת: percent, current_time, eta)
        check_size: האם לבדוק גודל לפני דחיסה (אם True, מחזיר את הקובץ המקורי אם כבר קטן מספיק)
    
    Returns:
        נתיב לקובץ דחוס או הקובץ המקורי (אם לא נדרשה דחיסה) או None אם נכשל
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"❌ קובץ לא נמצא: {input_path}")
            return None
        
        # בדיקת גודל אם נדרש
        if check_size:
            current_size_mb = os.path.getsize(input_path) / (1024 * 1024)
            logger.info(f"📊 גודל נוכחי: {current_size_mb:.2f} MB")
            
            if target_size_mb and current_size_mb <= target_size_mb:
                logger.info(f"✅ גודל קובץ מתאים, אין צורך בדחיסה")
                return input_path
        
        # קבלת משך הוידאו
        duration = await get_video_duration(input_path)
        if not duration or duration <= 0:
            logger.error("❌ לא ניתן לקבל משך וידאו")
            return None
        
        logger.info(f"⏱️ משך וידאו: {duration:.2f} שניות")
        
        # חישוב bitrate אם לא סופק
        if target_bitrate is None:
            if target_size_mb is None:
                logger.error("❌ צריך לספק או target_size_mb או target_bitrate")
                return None
            
            # חישוב bitrate מ-target size
            target_bits = target_size_mb * 8 * 1024 * 1024 * 0.95  # 95% לבטיחות
            audio_bitrate_kbps = 128
            audio_bits = audio_bitrate_kbps * 1024 * duration
            video_bits = target_bits - audio_bits
            target_bitrate = int(video_bits / duration / 1024)
        
        # וידוא bitrate מינימלי
        if target_bitrate < 300:
            target_bitrate = 300
            logger.warning(f"⚠️ Bitrate נמוך מדי, משתמש במינימום: 300k")
        
        logger.info(f"🎯 Bitrate יעד: {target_bitrate}k")
        
        # יצירת נתיב פלט
        base_path = input_path.rsplit('.', 1)[0]
        base_path = base_path.replace('_temp', '').replace('_720ish', '')
        output_path = f"{base_path}{filename_suffix}.mp4"
        
        # בחירת שיטת דחיסה
        if method == "two_pass":
            await _compress_two_pass(input_path, output_path, target_bitrate)
        else:
            await _compress_single_pass(input_path, output_path, target_bitrate, duration, progress_callback)
        
        if not os.path.exists(output_path):
            logger.error(f"❌ קובץ דחוס לא נוצר: {output_path}")
            return None
        
        # בדיקת גודל סופי
        if check_size:
            final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            current_size_mb = os.path.getsize(input_path) / (1024 * 1024)
            compression_ratio = (1 - final_size_mb / current_size_mb) * 100
            
            logger.info(f"✅ דחיסה הושלמה: {output_path}")
            logger.info(f"📊 גודל מקורי: {current_size_mb:.2f} MB")
            logger.info(f"📊 גודל דחוס: {final_size_mb:.2f} MB")
            logger.info(f"📊 יחס דחיסה: {compression_ratio:.1f}%")
            
            if target_size_mb and final_size_mb > target_size_mb:
                logger.warning(f"⚠️ גודל סופי ({final_size_mb:.2f}MB) חורג מהיעד ({target_size_mb}MB)")
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ שגיאה בדחיסת וידאו: {e}", exc_info=True)
        return None


async def _compress_single_pass(
    input_path: str,
    output_path: str,
    target_bitrate: int,
    duration: float,
    progress_callback=None
) -> None:
    """דחיסה ב-single pass"""
    threads = _get_optimal_threads()
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',
        '-b:v', f'{target_bitrate}k',
        '-maxrate', f'{target_bitrate}k',
        '-threads', str(threads),
        '-bufsize', f'{target_bitrate * 2}k',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-ac', '2',
        '-movflags', '+faststart',
        '-y',
        output_path
    ]
    
    def _compress():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=0
        )
        
        last_percent = 0
        time_pattern = re.compile(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})')
        error_output = []
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            
            if 'error' in line.lower() or 'failed' in line.lower():
                error_output.append(line)
            
            match = time_pattern.search(line)
            if match and duration and duration > 0:
                try:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds
                    
                    percent = min(int((current_time / duration) * 100), 99)
                    
                    if percent >= last_percent + 1 or percent == 99:
                        last_percent = percent
                        eta = int((duration - current_time))
                        logger.info(f"⏳ דחיסה: {percent}% | זמן נוכחי: {int(current_time)}s / {int(duration)}s | ETA: ~{eta}s")
                        
                        if progress_callback:
                            try:
                                progress_callback(percent, int(current_time), eta)
                            except:
                                pass
                except Exception:
                    pass
        
        returncode = process.wait()
        
        if returncode != 0:
            error_msg = '\n'.join(error_output[-5:]) if error_output else "Check logs above"
            raise subprocess.CalledProcessError(returncode, cmd, stderr=error_msg)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _compress)


async def _compress_two_pass(
    input_path: str,
    output_path: str,
    target_bitrate: int
) -> None:
    """דחיסה ב-2-pass"""
    null_output = 'NUL' if os.name == 'nt' else '/dev/null'
    threads = _get_optimal_threads()
    
    # Pass 1
    logger.info("🔄 מתחיל Pass 1/2 (ניתוח)...")
    cmd_pass1 = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',
        '-b:v', f'{target_bitrate}k',
        '-preset', 'medium',
        '-threads', str(threads),
        '-pass', '1',
        '-an',
        '-f', 'mp4',
        '-y',
        null_output
    ]
    
    def _run_pass1():
        subprocess.run(cmd_pass1, check=True, capture_output=True, 
                     encoding='utf-8', errors='ignore')
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_pass1)
    
    # Pass 2
    logger.info("🔄 מתחיל Pass 2/2 (דחיסה)...")
    cmd_pass2 = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',
        '-b:v', f'{target_bitrate}k',
        '-preset', 'medium',
        '-threads', str(threads),
        '-pass', '2',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-ac', '2',
        '-strict', '-2',
        '-movflags', '+faststart',
        '-y',
        output_path
    ]
    
    def _run_pass2():
        subprocess.run(cmd_pass2, check=True, capture_output=True,
                     encoding='utf-8', errors='ignore')
    
    await loop.run_in_executor(None, _run_pass2)
    
    # ניקוי קבצי log
    for log_file in ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']:
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except:
                pass


# תאימות לאחור - שמירה על הפונקציות הישנות
async def compress_to_target_size(
    input_path: str, 
    target_size_mb: int = 70,
    filename_suffix: str = "_compressed",
    progress_callback=None
) -> Optional[str]:
    """
    דחיסת וידאו לגודל יעד (תאימות לאחור - משתמש ב-compress_video)
    """
    return await compress_video(
        input_path=input_path,
        target_size_mb=target_size_mb,
        filename_suffix=filename_suffix,
        progress_callback=progress_callback,
        method="single_pass",
        check_size=False
    )


async def compress_with_ffmpeg(input_path: str, output_path: str, target_bitrate: int):
    """
    דחיסת וידאו עם FFmpeg בשיטת 2-pass (תאימות לאחור - משתמש ב-compress_video)
    """
    try:
        result = await compress_video(
            input_path=input_path,
            target_bitrate=target_bitrate,
            method="two_pass",
            filename_suffix="",
            check_size=False
        )
        
        # אם הצליח, נשנה את השם ל-output_path המבוקש
        if result and result != output_path:
            shutil.move(result, output_path)
        
        if not os.path.exists(output_path):
            raise Exception("קובץ דחוס לא נוצר")
        
        logger.info("✅ דחיסה עם FFmpeg הושלמה")
    except Exception as e:
        logger.error(f"❌ שגיאה בדחיסה: {e}")
        raise

