"""
Image Processing
עיבוד תמונות - thumbnails, קרדיטים, המרות
"""
import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import yt_dlp
import config

logger = logging.getLogger(__name__)


async def add_text_to_image(
    image_path: str,
    text: str,
    output_path: Optional[str] = None,
    font_size: int = 40,
    text_color: tuple = (255, 255, 255),
    background_color: tuple = (0, 0, 0, 200),
    padding: int = 20
) -> Optional[str]:
    """
    מוסיף טקסט בתחתית התמונה עם רקע
    
    Args:
        image_path: נתיב לתמונת המקור
        text: הטקסט להוסיף (קרדיטים)
        output_path: נתיב לקובץ פלט (אם None, יוצר אוטומטית)
        font_size: גודל הפונט
        text_color: צבע הטקסט (RGB)
        background_color: צבע הרקע (RGBA)
        padding: ריווח מסביב לטקסט
    
    Returns:
        נתיב לתמונה המעובדת או None אם נכשל
    """
    try:
        logger.info(f"🖼️ מוסיף טקסט לתמונה: {image_path}")
        
        if not os.path.exists(image_path):
            logger.error(f"❌ תמונה לא נמצאה: {image_path}")
            return None
        
        # טעינת התמונה
        def _process_image():
            img = Image.open(image_path)
            
            # המרה ל-RGBA אם נדרש
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # יצירת שכבת טקסט
            txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            # ניסיון לטעון פונט - אם נכשל, משתמש בברירת מחדל
            try:
                # ניסיון עם פונט Arial Hebrew
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    # ניסיון עם פונט ברירת מחדל
                    font = ImageFont.load_default()
                    logger.warning("⚠️ לא נמצא פונט מותאם, משתמש בברירת מחדל")
                except:
                    font = None
            
            # חלוקת הטקסט לשורות
            lines = text.split('\n')
            
            # חישוב גובה הטקסט
            if font:
                # שימוש ב-textbbox במקום getsize (deprecated)
                sample_bbox = draw.textbbox((0, 0), "Test", font=font)
                line_height = sample_bbox[3] - sample_bbox[1] + 5
            else:
                line_height = 15
            
            total_text_height = len(lines) * line_height + padding * 2
            
            # יצירת רקע לטקסט
            bg_y_start = img.height - total_text_height
            draw.rectangle(
                [(0, bg_y_start), (img.width, img.height)],
                fill=background_color
            )
            
            # כתיבת הטקסט
            y_position = bg_y_start + padding
            for line in lines:
                if font:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                else:
                    text_width = len(line) * 8
                
                x_position = (img.width - text_width) // 2
                draw.text((x_position, y_position), line, font=font, fill=text_color)
                y_position += line_height
            
            # שילוב השכבות
            combined = Image.alpha_composite(img, txt_layer)
            
            # המרה חזרה ל-RGB לשמירה כ-JPEG
            final_img = combined.convert('RGB')
            
            # שמירה
            if not output_path:
                output = image_path.rsplit('.', 1)[0] + '_with_credits.jpg'
            else:
                output = output_path
            
            final_img.save(output, 'JPEG', quality=95)
            return output
        
        # הרצה אסינכרונית
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _process_image)
        
        logger.info(f"✅ תמונה עם טקסט נוצרה: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהוספת טקסט לתמונה: {e}", exc_info=True)
        return None


async def fetch_youtube_thumbnail(url: str, cookies_path: str = "cookies.txt") -> Optional[str]:
    """
    מוריד את ה-thumbnail הרשמי מ-YouTube
    
    Args:
        url: קישור YouTube
        cookies_path: נתיב לקובץ cookies
    
    Returns:
        נתיב לקובץ thumbnail שהורד או None אם נכשל
    """
    try:
        logger.info(f"🖼️ מוריד thumbnail מ-YouTube...")
        
        # קבלת מידע על הוידאו
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
        }
        
        def _get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # מחפש את ה-thumbnail הטוב ביותר
                thumbnail_url = None
                if info.get('thumbnail'):
                    thumbnail_url = info['thumbnail']
                elif info.get('thumbnails') and len(info['thumbnails']) > 0:
                    # בוחר את האיכות הגבוהה ביותר
                    thumbnail_url = info['thumbnails'][-1]['url']
                
                return thumbnail_url, info.get('id', 'video')
        
        loop = asyncio.get_event_loop()
        thumbnail_url, video_id = await loop.run_in_executor(None, _get_info)
        
        if not thumbnail_url:
            logger.warning("⚠️ לא נמצא thumbnail URL")
            return None
        
        logger.info(f"📥 מוריד thumbnail מ-{thumbnail_url}")
        
        # הורדת ה-thumbnail
        import urllib.request
        
        downloads_dir = Path(config.DOWNLOADS_PATH)
        downloads_dir.mkdir(exist_ok=True)
        
        thumbnail_path = downloads_dir / f"yt_thumb_{video_id}.jpg"
        
        def _download():
            urllib.request.urlretrieve(thumbnail_url, thumbnail_path)
        
        await loop.run_in_executor(None, _download)
        
        if not os.path.exists(thumbnail_path):
            logger.error("❌ הורדת thumbnail נכשלה")
            return None
        
        logger.info(f"✅ Thumbnail הורד: {thumbnail_path}")
        return str(thumbnail_path)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהורדת thumbnail: {e}", exc_info=True)
        return None


async def prepare_mp3_thumbnail(
    input_image_path: str,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    מכין thumbnail לשימוש עם MP3 ב-Telegram:
    - Format: JPEG
    - Dimensions: ≤ 320px (שומר aspect ratio, ללא cropping)
    - מתאים לשימוש עם send_audio(thumb=...)
    
    Args:
        input_image_path: נתיב לתמונת המקור
        output_path: נתיב פלט אופציונלי
    
    Returns:
        נתיב ל-thumbnail מוכן או None אם נכשל
    """
    try:
        logger.info(f"🎵 מכין MP3 thumbnail מ-{input_image_path}")
        
        if not os.path.exists(input_image_path):
            logger.error(f"❌ תמונת מקור לא נמצאה: {input_image_path}")
            return None
        
        # יצירת נתיב פלט
        if not output_path:
            output_path = input_image_path.rsplit('.', 1)[0] + '_mp3_thumb.jpg'
        
        def _process():
            # טעינת התמונה
            img = Image.open(input_image_path)
            
            # המרה ל-RGB אם נדרש
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # חישוב ממדים חדשים - מקסימום 320px בכל ציר, שומר aspect ratio
            max_size = 320
            width, height = img.size
            
            if width > max_size or height > max_size:
                # שמירה על aspect ratio (לא cropping, רק scaling)
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                # וידוא שלפחות פיקסל אחד
                new_width = max(1, new_width)
                new_height = max(1, new_height)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"📐 Thumbnail resized: {width}x{height} → {new_width}x{new_height}")
            
            # שמירה כ-JPEG באיכות טובה
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            
            file_size_kb = os.path.getsize(output_path) / 1024
            logger.info(f"✅ MP3 thumbnail נוצר: {file_size_kb:.1f} KB")
            
            return output_path
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _process)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהכנת MP3 thumbnail: {e}", exc_info=True)
        return None


async def prepare_telegram_thumbnail(
    input_image_path: str,
    video_aspect_ratio: float,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    מכין thumbnail לדרישות Telegram:
    - Format: JPEG
    - Size: ≤ 200 KB
    - Dimensions: ≤ 320px בכל ציר
    - Aspect ratio: זהה לוידאו (עם padding)
    
    Args:
        input_image_path: נתיב לתמונת המקור
        video_aspect_ratio: יחס רוחב-גובה של הוידאו (width/height)
        output_path: נתיב פלט אופציונלי
    
    Returns:
        נתיב ל-thumbnail מוכן או None אם נכשל
    """
    try:
        logger.info(f"🎨 מכין thumbnail לTelegram...")
        logger.info(f"  Input: {input_image_path}")
        logger.info(f"  Target aspect ratio: {video_aspect_ratio:.3f}")
        
        if not os.path.exists(input_image_path):
            logger.error(f"❌ תמונת מקור לא נמצאה: {input_image_path}")
            return None
        
        # יצירת נתיב פלט
        if not output_path:
            output_path = input_image_path.rsplit('.', 1)[0] + '_telegram_thumb.jpg'
        
        def _process():
            # טעינת התמונה
            img = Image.open(input_image_path)
            
            # המרה ל-RGB אם נדרש
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # חישוב ממדים חדשים (שמירה על aspect ratio של הוידאו)
            # מקסימום 320px בכל ציר
            max_size = 320
            
            if video_aspect_ratio > 1:  # רוחב > גובה (landscape)
                new_width = max_size
                new_height = int(max_size / video_aspect_ratio)
            else:  # גובה >= רוחב (portrait or square)
                new_height = max_size
                new_width = int(max_size * video_aspect_ratio)
            
            # וידוא שלפחות פיקסל אחד בכל ממד
            new_width = max(1, new_width)
            new_height = max(1, new_height)
            
            # שינוי גודל התמונה
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # שמירה עם quality הולך וקטן עד שמגיעים ל-200KB
            quality = 85
            while quality > 20:
                img_resized.save(output_path, 'JPEG', quality=quality, optimize=True)
                
                file_size_kb = os.path.getsize(output_path) / 1024
                
                if file_size_kb <= 200:
                    logger.info(f"✅ Thumbnail נוצר: {file_size_kb:.1f} KB, {new_width}x{new_height}, quality={quality}")
                    return output_path
                
                quality -= 5
            
            # אם עדיין גדול מדי, נסה לצמצם את הגודל
            logger.warning(f"⚠️ Thumbnail גדול מדי, מקטין ממדים...")
            scale_factor = 0.8
            new_width = max(1, int(new_width * scale_factor))
            new_height = max(1, int(new_height * scale_factor))
            
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img_resized.save(output_path, 'JPEG', quality=60, optimize=True)
            
            file_size_kb = os.path.getsize(output_path) / 1024
            logger.info(f"✅ Thumbnail נוצר (מוקטן): {file_size_kb:.1f} KB, {new_width}x{new_height}")
            
            return output_path
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _process)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהכנת thumbnail: {e}", exc_info=True)
        return None

