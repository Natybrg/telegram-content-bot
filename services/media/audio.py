"""
Audio Processing
עיבוד קבצי אודיו - תגיות MP3, metadata
"""
import os
import logging
import asyncio
from typing import Optional, Dict
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, TCON, COMM, TCOM, 
    TPUB, TXXX, TCOP, TSRC, TBPM, TLAN, USLT, APIC, TCMP, TENC, 
    TSSE, TDEN, TOPE, TOAL, TDOR, TIT3, TPE3, TPE4
)

logger = logging.getLogger(__name__)


async def update_mp3_tags(
    mp3_path: str,
    image_path: str,
    metadata: Dict[str, str],
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    מעדכן תגיות MP3 כולל תמונת אלבום
    לא מוחק תגיות קיימות - רק מוסיף/מעדכן
    
    Args:
        mp3_path: נתיב לקובץ MP3
        image_path: נתיב לתמונת האלבום
        metadata: מילון עם המטא-דאטה:
            - title: שם השיר
            - artist: שם האמן
            - year: שנה
            - composer: מלחין
            - arranger: מעבד
            - mixer: מיקס
            - album: אלבום (ברירת מחדל: "סינגל")
        output_path: נתיב לקובץ פלט (אם None, מעדכן את המקור)
    
    Returns:
        נתיב לקובץ המעודכן או None אם נכשל
    """
    try:
        logger.info(f"🎵 מעדכן תגיות MP3: {mp3_path}")
        
        if not os.path.exists(mp3_path):
            logger.error(f"❌ קובץ MP3 לא נמצא: {mp3_path}")
            return None
        
        if not os.path.exists(image_path):
            logger.error(f"❌ תמונה לא נמצאה: {image_path}")
            return None
        
        # ערך הקרדיט הקבוע
        CREDIT_TEXT = "חסידי〽️יוזיק ~ https://linktr.ee/hasidim_music"
        
        def _update_tags():
            # העתקת הקובץ אם נדרש
            target_path = output_path if output_path else mp3_path
            if output_path and output_path != mp3_path:
                from services.media.utils import create_upload_copy
                import os
                # יצירת עותק עם שם חדש
                new_path = create_upload_copy(mp3_path, os.path.basename(output_path))
                if new_path:
                    target_path = new_path
                else:
                    # אם create_upload_copy נכשל, נשתמש ב-output_path ישירות
                    import shutil
                    shutil.copy2(mp3_path, output_path)
                    target_path = output_path
            
            # טעינת קובץ MP3
            try:
                audio = MP3(target_path, ID3=ID3)
            except:
                logger.error(f"❌ לא ניתן לטעון קובץ MP3")
                return None
            
            # וידוא שיש תגיות (לא מוחקים קיימות!)
            try:
                audio.add_tags()
            except:
                pass  # תגיות כבר קיימות
            
            # פונקציה עזר לבדיקה אם תגית קיימת עם ערך שונה
            def should_update_tag(tag_key, new_value):
                """בודק אם צריך לעדכן תגית - רק אם הערך החדש שונה מהקיים"""
                if not new_value:
                    return False  # אין ערך חדש - לא מעדכנים
                try:
                    existing = audio.tags.get(tag_key)
                    if existing:
                        existing_text = existing.text[0] if isinstance(existing.text, list) else str(existing.text)
                        # אם הערך זהה - לא מעדכנים
                        if existing_text == new_value:
                            return False
                except:
                    pass
                return True
            
            # פונקציה עזר להוספת תגית רק אם צריך
            def add_or_update_tag(tag_class, tag_key, value, description=""):
                """מוסיף/מעדכן תגית רק אם צריך"""
                if not value:
                    return
                if should_update_tag(tag_key, value):
                    try:
                        audio.tags.delall(tag_key)  # מוחק את הישן כדי להוסיף חדש
                    except:
                        pass
                    audio.tags.add(tag_class(encoding=3, text=value))
                    logger.debug(f"  📌 {description or tag_key}: {value}")
            
            # 1. TIT2 (Track Title)
            add_or_update_tag(TIT2, 'TIT2', metadata.get('title'), 'Title')
            
            # 2. TPE1 (Artist)
            add_or_update_tag(TPE1, 'TPE1', metadata.get('artist'), 'Artist')
            
            # 3. TALB (Album) - "סינגל"
            album_value = metadata.get('album', 'סינגל')
            add_or_update_tag(TALB, 'TALB', album_value, 'Album')
            
            # 4. TPE2 (Album Artist)
            add_or_update_tag(TPE2, 'TPE2', metadata.get('artist'), 'Album Artist')
            
            # 5. TRCK (Track Number) - "1/1"
            try:
                audio.tags.delall('TRCK')
            except:
                pass
            audio.tags.add(TRCK(encoding=3, text="1/1"))
            logger.debug("  📌 Track: 1/1")
            
            # 6. Track Total - כלול ב-1/1, לא צריך תגית נפרדת
            
            # 7. TPOS (Disk Number) - "1/1"
            try:
                audio.tags.delall('TPOS')
            except:
                pass
            audio.tags.add(TPOS(encoding=3, text="1/1"))
            logger.debug("  📌 Disk: 1/1")
            
            # 8. Disk Total - כלול ב-1/1, לא צריך תגית נפרדת
            
            # 9. TDRC (Year/Date)
            add_or_update_tag(TDRC, 'TDRC', metadata.get('year'), 'Year')
            
            # 10. TCON (Genre)
            add_or_update_tag(TCON, 'TCON', CREDIT_TEXT, 'Genre')
            
            # 11. COMM (Comment)
            add_or_update_tag(COMM, 'COMM', CREDIT_TEXT, 'Comment')
            
            # 12. TCOM (Composer)
            add_or_update_tag(TCOM, 'TCOM', metadata.get('composer'), 'Composer')
            
            # 13. TEXT (Lyricist) - לא קיים ב-ID3v2.3, משתמשים ב-TXXX
            try:
                audio.tags.delall('TXXX:LYRICIST')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='LYRICIST', text=CREDIT_TEXT))
            logger.debug(f"  📌 Lyricist: {CREDIT_TEXT}")
            
            # 14. TPUB (Publisher)
            add_or_update_tag(TPUB, 'TPUB', CREDIT_TEXT, 'Publisher')
            
            # 15. TXXX:LABEL (Record Label)
            try:
                audio.tags.delall('TXXX:LABEL')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='LABEL', text=CREDIT_TEXT))
            logger.debug(f"  📌 Label: {CREDIT_TEXT}")
            
            # 16. TCOP (Copyright) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 17. TSRC (ISRC) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 18. TBPM (BPM) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 19. TLAN (Language) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 20. USLT (Lyrics)
            add_or_update_tag(USLT, 'USLT', CREDIT_TEXT, 'Lyrics')
            
            # 21. APIC (Album Cover) - תמיד מעדכן
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
                
                # זיהוי סוג התמונה
                image_type = 'image/jpeg'
                if image_path.lower().endswith('.png'):
                    image_type = 'image/png'
                elif image_path.lower().endswith('.webp'):
                    image_type = 'image/webp'
                
                # המרת WebP ל-JPEG אם צריך (למניעת בעיות תאימות)
                if image_type == 'image/webp':
                    try:
                        from PIL import Image
                        import io
                        img = Image.open(io.BytesIO(image_data))
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=95)
                        image_data = output.getvalue()
                        image_type = 'image/jpeg'
                        logger.debug("  🔄 המרת WebP ל-JPEG")
                    except Exception as e:
                        logger.warning(f"  ⚠️ לא ניתן להמיר WebP ל-JPEG: {e}")
                
                # מוחקים תמונות קיימות
                try:
                    audio.tags.delall('APIC')
                except:
                    pass
                
                # הוספת תמונת אלבום - חשוב: type=3 = Cover (front)
                # זה התמונה שתוצג בנגנים ובמערכות הפעלה
                audio.tags.add(
                    APIC(
                        encoding=3,  # UTF-8
                        mime=image_type,
                        type=3,  # 3 = Cover (front) - התמונה שתוצג
                        desc='Cover',  # תיאור
                        data=image_data
                    )
                )
                logger.info(f"  🖼️ Album art משובץ: {image_path} ({len(image_data)} bytes, {image_type})")
            
            # 22. TCMP (Compilation) - 0
            try:
                audio.tags.delall('TCMP')
            except:
                pass
            audio.tags.add(TCMP(encoding=3, text="0"))
            logger.debug("  📌 Compilation: 0")
            
            # 23. TENC (Encoded By)
            add_or_update_tag(TENC, 'TENC', CREDIT_TEXT, 'Encoded By')
            
            # 24. TSSE (Encoder Settings) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 25. TDEN (Encoding Time) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 26. TOPE (Original Artist)
            add_or_update_tag(TOPE, 'TOPE', metadata.get('artist'), 'Original Artist')
            
            # 27. TOAL (Original Album)
            add_or_update_tag(TOAL, 'TOAL', album_value, 'Original Album')
            
            # 28. TDOR (Original Release Date)
            add_or_update_tag(TDOR, 'TDOR', metadata.get('year'), 'Original Release Date')
            
            # 29. TIT3 (Subtitle)
            add_or_update_tag(TIT3, 'TIT3', metadata.get('title'), 'Subtitle')
            
            # 30. GRP1 (Grouping) - לא קיים ב-ID3v2.3, משתמשים ב-TXXX
            try:
                audio.tags.delall('TXXX:GROUPING')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='GROUPING', text=CREDIT_TEXT))
            logger.debug(f"  📌 Grouping: {CREDIT_TEXT}")
            
            # 31. TMOO (Mood) - לא קיים ב-ID3v2.3, משתמשים ב-TXXX
            try:
                audio.tags.delall('TXXX:MOOD')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='MOOD', text=CREDIT_TEXT))
            logger.debug(f"  📌 Mood: {CREDIT_TEXT}")
            
            # 32. TPE3 (Conductor) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 33. TIPL:arranger (Arranger) - משתמשים ב-TXXX במקום TIPL
            arranger = metadata.get('arranger')
            if arranger:
                try:
                    audio.tags.delall('TXXX:ARRANGER')
                except:
                    pass
                audio.tags.add(TXXX(encoding=3, desc='ARRANGER', text=arranger))
                logger.debug(f"  📌 Arranger: {arranger}")
            
            # 34. TIPL:producer (Producer) - להשאיר קיים או ריק
            # לא מעדכנים אם לא צוין אחרת
            
            # 35. TPE4 (Remixed By) - Mixer
            mixer = metadata.get('mixer')
            if mixer:
                add_or_update_tag(TPE4, 'TPE4', mixer, 'Remixed By (Mixer)')
            
            # תגיות TXXX נוספות (קרדיט)
            try:
                audio.tags.delall('TXXX:SOURCE')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='SOURCE', text=CREDIT_TEXT))
            
            try:
                audio.tags.delall('TXXX:WEBSITE')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='WEBSITE', text="https://linktr.ee/hasidim_music"))
            
            try:
                audio.tags.delall('TXXX:CREDIT')
            except:
                pass
            audio.tags.add(TXXX(encoding=3, desc='CREDIT', text=CREDIT_TEXT))
            
            # שמירה - וידוא שהתמונה נשמרת בקובץ
            audio.save(v2_version=3)  # v2_version=3 = ID3v2.3 (תואם לכל הנגנים)
            logger.info(f"✅ תגיות MP3 עודכנו בהצלחה")
            
            # וידוא שהתמונה נשמרה - בדיקה
            try:
                audio_verify = MP3(target_path, ID3=ID3)
                apic_tags = audio_verify.tags.getall('APIC')
                if apic_tags:
                    logger.info(f"✅ תמונת אלבום משובצת בקובץ: {len(apic_tags)} תמונה/ות")
                else:
                    logger.warning("⚠️ תמונת אלבום לא נמצאה בקובץ לאחר השמירה!")
            except Exception as e:
                logger.warning(f"⚠️ לא ניתן לוודא תמונת אלבום: {e}")
            
            return target_path
        
        # הרצה אסינכרונית
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _update_tags)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בעדכון תגיות MP3: {e}", exc_info=True)
        return None


async def extract_mp3_metadata(mp3_path: str, original_filename: str = None) -> Optional[Dict]:
    """
    מוציא את כל המטא-דאטה מקובץ MP3
    
    Args:
        mp3_path: נתיב לקובץ MP3
        original_filename: שם הקובץ המקורי (אם לא מסופק, משתמש בשם הקובץ מהנתיב)
    
    Returns:
        מילון עם כל המטא-דאטה:
        - filename: שם הקובץ המקורי
        - file_size: גודל הקובץ (בבתים)
        - file_size_mb: גודל הקובץ (במגה-בייט)
        - duration: משך זמן (בשניות)
        - duration_formatted: משך זמן (פורמט HH:MM:SS)
        - bitrate: bitrate (kbps)
        - sample_rate: sample rate (Hz)
        - album_art: נתיב זמני לתמונת האלבום (אם קיימת) או None
        - tags: מילון עם כל התגיות
    """
    try:
        if not os.path.exists(mp3_path):
            logger.error(f"❌ קובץ MP3 לא נמצא: {mp3_path}")
            return None
        
        def _extract_metadata():
            # טעינת קובץ MP3
            try:
                audio = MP3(mp3_path, ID3=ID3)
            except Exception as e:
                logger.error(f"❌ לא ניתן לטעון קובץ MP3: {e}")
                return None
            
            # מידע בסיסי על הקובץ
            file_size = os.path.getsize(mp3_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # משך זמן
            duration = audio.info.length if hasattr(audio.info, 'length') else 0
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
            
            # Bitrate
            bitrate = audio.info.bitrate if hasattr(audio.info, 'bitrate') else 0
            bitrate_kbps = bitrate // 1000 if bitrate else 0
            
            # Sample rate
            sample_rate = audio.info.sample_rate if hasattr(audio.info, 'sample_rate') else 0
            
            # שם הקובץ - שימוש בשם המקורי אם מסופק, אחרת שם הקובץ מהנתיב
            if original_filename:
                filename = original_filename
            else:
                filename = os.path.basename(mp3_path)
            
            # חילוץ תמונת אלבום
            album_art_path = None
            try:
                if audio.tags:
                    apic_tags = audio.tags.getall('APIC')
                    if apic_tags:
                        # לוקחים את התמונה הראשונה (Cover front)
                        apic = apic_tags[0]
                        if hasattr(apic, 'data') and apic.data:
                            # שמירת התמונה לקובץ זמני
                            import tempfile
                            import io
                            from PIL import Image
                            
                            # זיהוי סוג התמונה
                            mime_type = apic.mime if hasattr(apic, 'mime') else 'image/jpeg'
                            ext = '.jpg'
                            if 'png' in mime_type.lower():
                                ext = '.png'
                            elif 'webp' in mime_type.lower():
                                ext = '.webp'
                            
                            # יצירת קובץ זמני
                            temp_dir = tempfile.gettempdir()
                            temp_filename = f"album_art_{os.path.basename(mp3_path).replace('.mp3', '')}{ext}"
                            album_art_path = os.path.join(temp_dir, temp_filename)
                            
                            # שמירת התמונה
                            with open(album_art_path, 'wb') as f:
                                f.write(apic.data)
                            
                            logger.info(f"✅ תמונת אלבום נשמרה: {album_art_path}")
            except Exception as e:
                logger.warning(f"⚠️ לא ניתן לחלץ תמונת אלבום: {e}")
            
            # חילוץ כל התגיות - כולל תגיות ריקות
            tags = {}
            
            # רשימת כל התגיות הסטנדרטיות עם שמות בעברית
            tag_mapping = {
                'TIT2': 'כותרת',
                'TPE1': 'אמן',
                'TALB': 'אלבום',
                'TPE2': 'אמן אלבום',
                'TRCK': 'מספר רצועה',
                'TPOS': 'מספר דיסק',
                'TDRC': 'שנה',
                'TCON': 'ז\'אנר',
                'COMM': 'הערה',
                'TCOM': 'מלחין',
                'TPUB': 'מפיץ',
                'TCOP': 'זכויות יוצרים',
                'TSRC': 'ISRC',
                'TBPM': 'BPM',
                'TLAN': 'שפה',
                'USLT': 'מילים',
                'TCMP': 'אוסף',
                'TENC': 'נקוד על ידי',
                'TSSE': 'הגדרות מקודד',
                'TDEN': 'זמן קידוד',
                'TOPE': 'אמן מקורי',
                'TOAL': 'אלבום מקורי',
                'TDOR': 'תאריך יציאה מקורי',
                'TIT3': 'כותרת משנה',
                'TPE3': 'מנצח',
                'TPE4': 'רמיקס על ידי',
            }
            
            # רשימת תגיות TXXX נפוצות עם שמות בעברית
            txxx_hebrew_names = {
                'LYRICIST': 'כותב מילים',
                'LABEL': 'חברת תקליטים',
                'ARRANGER': 'מעבד',
                'GROUPING': 'קיבוץ',
                'MOOD': 'מצב רוח',
                'SOURCE': 'מקור',
                'WEBSITE': 'אתר',
                'CREDIT': 'קרדיט',
            }
            
            # אתחול כל התגיות הסטנדרטיות (גם אם אין להן ערכים)
            for tag_key, tag_name_hebrew in tag_mapping.items():
                tags[tag_name_hebrew] = ''
            
            if audio.tags:
                # חילוץ תגיות סטנדרטיות
                for tag_key, tag_name_hebrew in tag_mapping.items():
                    try:
                        tag_value = audio.tags.get(tag_key)
                        if tag_value:
                            if hasattr(tag_value, 'text'):
                                text = tag_value.text
                                if isinstance(text, list):
                                    tags[tag_name_hebrew] = text[0] if text else ''
                                else:
                                    tags[tag_name_hebrew] = str(text)
                            else:
                                tags[tag_name_hebrew] = str(tag_value)
                    except Exception as e:
                        logger.debug(f"לא ניתן לחלץ תגית {tag_key}: {e}")
                
                # חילוץ תגיות TXXX (תגיות מותאמות אישית)
                try:
                    txxx_tags = audio.tags.getall('TXXX')
                    for txxx in txxx_tags:
                        if hasattr(txxx, 'desc') and hasattr(txxx, 'text'):
                            desc = txxx.desc
                            # שימוש בשם עברי אם קיים, אחרת השם המקורי
                            tag_name_hebrew = txxx_hebrew_names.get(desc, f'TXXX:{desc}')
                            text = txxx.text[0] if isinstance(txxx.text, list) else str(txxx.text)
                            tags[tag_name_hebrew] = text
                except Exception as e:
                    logger.debug(f"לא ניתן לחלץ תגיות TXXX: {e}")
            
            return {
                'filename': filename,
                'file_size': file_size,
                'file_size_mb': round(file_size_mb, 2),
                'duration': duration,
                'duration_formatted': duration_formatted,
                'bitrate': bitrate_kbps,
                'sample_rate': int(sample_rate) if sample_rate else 0,
                'album_art': album_art_path,
                'tags': tags
            }
        
        # הרצה אסינכרונית
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _extract_metadata)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ שגיאה בחילוץ מטא-דאטה מ-MP3: {e}", exc_info=True)
        return None

