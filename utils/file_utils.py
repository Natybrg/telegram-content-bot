"""
File Utilities
Common file operations and path utilities
"""
import os
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_dir(directory: Path) -> Path:
    """
    מוודא שתיקייה קיימת, יוצר אותה אם לא
    
    Args:
        directory: נתיב לתיקייה
        
    Returns:
        Path object של התיקייה
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_delete(file_path: str) -> bool:
    """
    מחיקה בטוחה של קובץ (לא זורק exception)
    
    Args:
        file_path: נתיב לקובץ
        
    Returns:
        True if deleted, False otherwise
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"🗑️ Deleted: {file_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to delete {file_path}: {e}")
    return False


def get_file_size_mb(file_path: str) -> float:
    """
    מחזיר גודל קובץ ב-MB
    
    Args:
        file_path: נתיב לקובץ
        
    Returns:
        File size in MB
    """
    if not file_path or not os.path.exists(file_path):
        return 0.0
    return os.path.getsize(file_path) / (1024 * 1024)


def format_file_size(size_bytes: int) -> str:
    """
    פורמט גודל קובץ לתצוגה נוחה
    
    Args:
        size_bytes: גודל בבייטים
        
    Returns:
        Formatted string (e.g., "15.3 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def create_upload_copy(original_path: str, upload_dir: Optional[str] = None) -> Optional[str]:
    """
    יוצר עותק של קובץ להעלאה (למנוע בעיות נעילה)
    
    Args:
        original_path: נתיב לקובץ המקורי
        upload_dir: תיקייה ליצירת העותק (optional)
        
    Returns:
        Path to copy, or None if failed
    """
    try:
        if not os.path.exists(original_path):
            logger.error(f"Original file not found: {original_path}")
            return None
        
        # קביעת תיקית יעד
        if upload_dir:
            target_dir = Path(upload_dir)
        else:
            target_dir = Path(original_path).parent
        
        ensure_dir(target_dir)
        
        # יצירת שם קובץ ייחודי
        base_name = Path(original_path).stem
        extension = Path(original_path).suffix
        copy_path = target_dir / f"{base_name}_upload{extension}"
        
        # העתקה
        shutil.copy2(original_path, copy_path)
        logger.debug(f"📋 Created upload copy: {copy_path}")
        return str(copy_path)
        
    except Exception as e:
        logger.error(f"Failed to create upload copy: {e}")
        return None


def get_unique_filename(directory: Path, base_name: str, extension: str) -> str:
    """
    מחזיר שם קובץ ייחודי (מוסיף מספר אם קיים)
    
    Args:
        directory: תיקייה
        base_name: שם בסיס
        extension: סיומת (עם נקודה)
        
    Returns:
        Unique filename
    """
    counter = 1
    filename = f"{base_name}{extension}"
    
    while (directory / filename).exists():
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    return filename
