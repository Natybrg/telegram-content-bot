"""
Content Creator Plugin
מנהל את תהליך יצירת התוכן המוזיקלי
"""
# ייצוא כל ה-handlers כדי שייטענו אוטומטית
from . import handlers
# ייצוא cleanup_session_files לשימוש ב-start.py ו-cancel
from .cleanup import cleanup_session_files

__all__ = ['handlers', 'cleanup_session_files']

