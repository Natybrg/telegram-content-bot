"""
Queue Models
Data models for processing queue
"""
from datetime import datetime
from typing import Callable, Optional, Any


class QueueItem:
    """
    פריט בתור עיבוד
    
    Attributes:
        user_id: מזהה המשתמש
        callback: פונקציה לביצוע
        message: הודעת טלגרם
        added_at: מתי נוסף לתור
        status_msg: הודעת סטטוס (optional)
    """
    
    def __init__(
        self,
        user_id: int,
        callback: Callable,
        message: Any,
        added_at: datetime,
        status_msg: Optional[Any] = None
    ):
        self.user_id = user_id
        self.callback = callback
        self.message = message
        self.added_at = added_at
        self.status_msg = status_msg
    
    def __repr__(self) -> str:
        return f"QueueItem(user_id={self.user_id}, added_at={self.added_at})"
