"""
Text Utilities
Text processing and formatting functions
"""
import re
from typing import List, Optional


def clean_text(text: str) -> str:
    """
    ניקוי טקסט מתווים לא רצויים
    
    Args:
        text: טקסט לניקוי
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # הסרת whitespace מיותר
    text = " ".join(text.split())
    
    # הסרת תווים מיוחדים בעייתיים
    text = text.replace("\r", "").replace("\x00", "")
    
    return text.strip()


def escape_markdown(text: str) -> str:
    """
    Escape תווים מיוחדים ל-Telegram Markdown
    
    Args:
        text: טקסט ל-escape
        
    Returns:
        Escaped text
    """
    if not text:
        return ""
    
    # תווים שצריך escape ב-Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    קיצור טקסט לאורך מקסימלי
    
    Args:
        text: טקסט לקיצור
        max_length: אורך מקסימלי
        suffix: מה להוסיף אם קוצץ
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_lines(text: str, expected_lines: int) -> Optional[List[str]]:
    """
    פרסור טקסט למספר שורות צפוי
    
    Args:
        text: טקסט לפרסור
        expected_lines: מספר שורות צפוי
        
    Returns:
        List of lines או None if invalid
    """
    if not text:
        return None
    
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    if len(lines) != expected_lines:
        return None
    
    return lines


def extract_youtube_id(url: str) -> Optional[str]:
    """
    חילוץ YouTube video ID מ-URL
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID או None
    """
    if not url:
        return None
    
    # Patterns for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def is_valid_url(url: str) -> bool:
    """
    בדיקה אם URL תקין
    
    Args:
        url: URL לבדיקה
        
    Returns:
        True if valid URL
    """
    if not url:
        return False
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    return url_pattern.match(url) is not None


def sanitize_filename(filename: str) -> str:
    """
    ניקוי שם קובץ מתווים בעייתיים
    
    Args:
        filename: שם קובץ
        
    Returns:
        Safe filename
    """
    if not filename:
        return "unnamed"
    
    # הסרת תווים לא חוקיים
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # הסרת whitespace מיותר
    filename = " ".join(filename.split())
    
    # הגבלת אורך
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:200 - len(ext) - 1] + ('.' + ext if ext else '')
    
    return filename or "unnamed"
