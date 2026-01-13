"""
Progress Tracker for Content Processing

Manages progress tracking and status text generation for content uploads.
"""
import logging

logger = logging.getLogger(__name__)


def create_status_text(
    session,
    upload_status: dict,
    upload_progress: dict,
    current_operation: str = "",
    current_operation_percent: int = 0,
    is_completed: bool = False,
    include_queue_info: bool = False,
    queue_status: dict = None
) -> str:
    """
    מחזיר טקסט סטטוס מעודכן בתבנית החדשה
    
    Args:
        session: User session object
        upload_status: Dictionary tracking completion status {'telegram': {...}, 'whatsapp': {...}}
        upload_progress: Dictionary tracking progress percentage
        current_operation: Name of current operation
        current_operation_percent: Progress percentage of current operation
        is_completed: Whether processing is complete
        include_queue_info: Whether to include queue information
        queue_status: Queue status dictionary
    
    Returns:
        Formatted status text
    """
    from .common import create_progress_bar  # Import here to avoid circular import
    
    text = ""
    
    # מידע על התור (רק אם המשתמש בתור)
    if include_queue_info and queue_status and queue_status.get('user_in_queue'):
        text += "📊 **מצב התור**\n\n"
        text += f"👥 **סה\"כ בתור:** {queue_status.get('queue_size', 0)} משתמשים\n"
        if queue_status.get('user_position'):
            text += f"📍 **המיקום שלך:** {queue_status.get('user_position')}\n"
            text += f"⏱️ **זמן משוער:** ~{queue_status.get('estimated_wait_minutes', 0)} דקות\n"
        text += "\n"
    
    # כותרת סיום (רק אם הושלם)
    if is_completed:
        text += "✅ **משימה הושלמה**\n\n"
    
    # ספירת קבצים מוצלחים
    telegram_count = sum(1 for key in ['image', 'audio', 'video'] if upload_status['telegram'].get(key, False))
    telegram_total = 2 + (1 if session.need_video else 0)  # תמונה + MP3 + (וידאו אם נדרש)
    
    whatsapp_count = sum( 1 for key in ['image', 'audio', 'video'] if upload_status['whatsapp'].get(key, False))
    whatsapp_total = 2 + (1 if session.need_video else 0)  # תמונה + MP3 + (וידאו אם נדרש)
    
    text += f"📤 **טלגרם:** {telegram_count}/{telegram_total}\n"
    text += f"📱 **וואטסאפ:** {whatsapp_count}/{whatsapp_total}\n\n"
    
    # פעולה נוכחית (רק אם לא הושלם)
    if not is_completed and current_operation:
        text += f"{current_operation} {current_operation_percent}%\n"
        text += f"{create_progress_bar(current_operation_percent)}\n\n"
    
    # חישוב אחוז התקדמות כללי
    total_items = 0
    completed_items = 0
    for platform in ['telegram', 'whatsapp']:
        for key in ['image', 'audio', 'video']:
            if key == 'video' and not session.need_video:
                continue  # דלג על וידאו אם לא נדרש
            total_items += 1
            if upload_status[platform].get(key, False):
                completed_items += 1
            elif upload_progress[platform].get(key, 0) > 0:
                # אם יש התקדמות חלקית, נחשב חלקית
                completed_items += upload_progress[platform][key] / 100
    
    overall_percent = int((completed_items / total_items) * 100) if total_items > 0 else 0
    text += f"{create_progress_bar(overall_percent)}\n"
    
    return text


class ProgressTracker:
    """
    Progress Tracker class for managing upload progress and status
    """
    
    def __init__(self, session, status_msg):
        """
        Initialize Progress Tracker
        
        Args:
            session: User session object
            status_msg: Telegram status message object
        """
        self.session = session
        self.status_msg = status_msg
        
        # ========== מעקב התקדמות מפורט ==========
        self.upload_status = {
            "telegram": {"image": False, "audio": False, "video": False},
            "whatsapp": {"image": False, "audio": False, "video": False}
        }
        
        # ========== מעקב אחוזי התקדמות לכל פריט ==========
        self.upload_progress = {
            "telegram": {"image": 0, "audio": 0, "video": 0},
            "whatsapp": {"image": 0, "audio": 0, "video": 0}
        }
        
        # ========== מעקב שגיאות ==========
        self.errors = []
        
        # ========== מעקב פעולות נוכחיות ==========
        self.current_operation = ""  # שם הפעולה הנוכחית
        self.current_operation_percent = 0  # אחוז מהפעולה הנוכחית
        
        # ========== מעקב תוצאות מפורט עם גדלי קבצים ==========
        self.upload_results = {
            "telegram": {},
            "whatsapp": {}
        }
        
        # ========== סטטוס סיום ==========
        self.is_completed = False
    
    def get_status_text(self, include_queue_info=False, queue_status=None):
        """Get current status text"""
        return create_status_text(
            session=self.session,
            upload_status=self.upload_status,
            upload_progress=self.upload_progress,
            current_operation=self.current_operation,
            current_operation_percent=self.current_operation_percent,
            is_completed=self.is_completed,
            include_queue_info=include_queue_info,
            queue_status=queue_status
        )
    
    async def update_status(self, operation_name="", percent=0, emoji_index=0):
        """
        עדכן את הודעת הסטטוס עם התבנית החדשה
        
        Args:
            operation_name: Name of the operation
            percent: Progress percentage
            emoji_index: Emoji index (not used currently)
        """
        # עדכון הפעולה הנוכחית
        if operation_name:
            self.current_operation = operation_name
            self.current_operation_percent = percent
        
        status_text = self.get_status_text()
        try:
            await self.status_msg.edit_text(status_text)
        except Exception as e:
            logger.warning(f"Failed to update status message: {e}")
    
    def mark_completed(self, platform: str, file_type: str, success: bool = True, **kwargs):
        """
        Mark a file upload as completed
        
        Args:
            platform: 'telegram' or 'whatsapp'
            file_type: 'image', 'audio', or 'video'
            success: Whether the upload was successful
            **kwargs: Additional result data (size_mb, sent_to, etc.)
        """
        if platform in self.upload_status and file_type in self.upload_status[platform]:
            self.upload_status[platform][file_type] = success
            self.upload_progress[platform][file_type] = 100 if success else 0
            
            if success and kwargs:
                self.upload_results[platform][file_type] = kwargs
    
    def update_progress(self, platform: str, file_type: str, percent: int):
        """
        Update progress for a specific file upload
        
        Args:
            platform: 'telegram' or 'whatsapp'
            file_type: 'image', 'audio', or 'video'
            percent: Progress percentage
        """
        if platform in self.upload_progress and file_type in self.upload_progress[platform]:
            self.upload_progress[platform][file_type] = percent
    
    def add_error(self, platform: str, file_type: str, error: str, **kwargs):
        """
        Add an error to the error list
        
        Args:
            platform: Platform where error occurred
            file_type: File type that failed
            error: Error message
            **kwargs: Additional error data
        """
        error_dict = {
            "platform": platform,
            "file_type": file_type,
            "error": error
        }
        error_dict.update(kwargs)
        self.errors.append(error_dict)
