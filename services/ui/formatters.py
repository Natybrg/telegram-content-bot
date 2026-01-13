from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def format_mp3_metadata_message(metadata: dict, user_id: int = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    מעצב הודעת מטא-דאטה של MP3 בצורה פשוטה ומסודרת
    
    Args:
        metadata: מילון עם המטא-דאטה
        user_id: ID המשתמש (לשימוש ב-callback_data)
    
    Returns:
        tuple: (text, keyboard) - טקסט ההודעה והכפתור
    """
    info_text = ""
    
    # שם קובץ
    info_text += f"{metadata['filename']}\n"
    
    # שם זמר - שם שיר
    artist = metadata['tags'].get('אמן', '')
    title = metadata['tags'].get('כותרת', '')
    if artist or title:
        info_text += f"{artist} - {title}\n" if artist and title else f"{artist}{title}\n"
    
    info_text += "\n"
    
    # פרטים טכניים
    info_text += f"משקל: {metadata['file_size_mb']} MB\n"
    info_text += f"משך: {metadata['duration_formatted']}\n"
    info_text += f"bitrate: {metadata['bitrate']} kbps\n"
    info_text += f"samplerate: {metadata['sample_rate']} Hz\n"
    
    info_text += "\n"
    
    # כל התגיות - רק תגיות עם ערכים, בסדר אלפביתי
    tags_with_values = [(name, value) for name, value in sorted(metadata['tags'].items()) if value]
    
    # רשימת תגיות להצגה (כולל ריקות)
    all_tags_to_show = [
        'כותרת', 'אמן', 'אלבום', 'אמן אלבום', 'שנה', 'ז\'אנר',
        'מספר רצועה', 'מספר דיסק', 'אוסף',
        'מלחין', 'מעבד', 'מנצח', 'רמיקס על ידי', 'כותב מילים',
        'הערה', 'מפיץ', 'זכויות יוצרים', 'ISRC', 'BPM', 'שפה', 'מילים',
        'נקוד על ידי', 'הגדרות מקודד', 'זמן קידוד', 'אמן מקורי', 'אלבום מקורי',
        'תאריך יציאה מקורי', 'כותרת משנה'
    ]
    
    # הוספת תגיות TXXX
    txxx_tags = [name for name in metadata['tags'].keys() if name.startswith('TXXX:')]
    all_tags_to_show.extend(sorted(txxx_tags))
    
    # הוספת כל התגיות האחרות
    shown_tags = set()
    for tag_name in all_tags_to_show:
        if tag_name in metadata['tags']:
            shown_tags.add(tag_name)
            tag_value = metadata['tags'].get(tag_name, '')
            info_text += f"{tag_name}: {tag_value}\n" if tag_value else f"{tag_name}:\n"
    
    # הוספת תגיות נוספות שלא ברשימה
    for tag_name, tag_value in tags_with_values:
        if tag_name not in shown_tags:
            info_text += f"{tag_name}: {tag_value}\n" if tag_value else f"{tag_name}:\n"
    
    # כפתור סיום
    callback_data = f"mp3_done_{user_id}" if user_id else "mp3_done"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ סיום", callback_data=callback_data)]
    ])
    
    return info_text, keyboard
