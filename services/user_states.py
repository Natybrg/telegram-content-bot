"""
User States Manager
ניהול מצבי משתמשים בתהליך יצירת תוכן
"""
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class UserState:
    """מצבים אפשריים של משתמש"""
    IDLE = "idle"                           # לא פעיל
    WAITING_IMAGE = "waiting_image"         # ממתין לתמונה
    WAITING_MP3 = "waiting_mp3"             # ממתין לקובץ MP3
    WAITING_DETAILS = "waiting_details"     # ממתין ל-8 שורות פרטים
    WAITING_VIDEO_ONLY_DETAILS = "waiting_video_only_details"  # ממתין ל-3 שורות לוידאו בלבד
    WAITING_INSTAGRAM_URL = "waiting_instagram_url"  # ממתין לקישור אינסטגרם
    WAITING_INSTAGRAM_TEXT = "waiting_instagram_text"  # ממתין לטקסט לאינסטגרם
    WAITING_INSTAGRAM_TEMPLATE_EDIT = "waiting_instagram_template_edit"  # ממתין לעריכת תבניות אינסטגרם
    PROCESSING = "processing"               # מעבד את התוכן
    EDITING_TEMPLATE = "editing_template"   # עורך תבנית
    UPDATING_COOKIES = "updating_cookies"   # מעדכן קובץ cookies
    ADDING_CHANNEL = "adding_channel"       # מוסיף ערוץ/קבוצה למאגר


@dataclass
class UserSession:
    """
    סשן משתמש - שומר את כל המידע שנאסף בתהליך
    """
    user_id: int
    state: str = UserState.IDLE
    image_file_id: Optional[str] = None
    image_path: Optional[str] = None
    mp3_file_id: Optional[str] = None
    mp3_path: Optional[str] = None
    
    # 8 שורות הפרטים
    song_name: Optional[str] = None         # שם שיר
    artist_name: Optional[str] = None       # שם זמר
    year: Optional[str] = None              # שנה
    composer: Optional[str] = None          # שם מלחין
    arranger: Optional[str] = None          # שם מעבד
    mixer: Optional[str] = None             # שם מיקס
    youtube_url: Optional[str] = None       # קישור ליוטיוב
    need_video: bool = False                # כן/לא (האם צריך וידאו)
    
    # קבצים שנוצרו
    processed_image_path: Optional[str] = None      # תמונה עם קרדיטים
    processed_mp3_path: Optional[str] = None        # MP3 עם תגיות
    video_high_path: Optional[str] = None           # וידאו איכותי
    video_medium_path: Optional[str] = None         # וידאו בינוני
    
    # אינסטגרם
    instagram_url: Optional[str] = None              # קישור לאינסטגרם
    instagram_file_path: Optional[str] = None        # נתיב לקובץ שהורד מאינסטגרם
    instagram_media_type: Optional[str] = None       # סוג המדיה (video/image)
    instagram_text: Optional[str] = None             # טקסט להעלאה
    instagram_download_time: Optional[datetime] = None  # זמן סיום ההורדה
    instagram_timeout_task: Optional[Any] = None      # טיימר לניקוי אוטומטי
    
    # מטא-דאטה
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    files_to_cleanup: list = field(default_factory=list)
    
    # מעקב הודעות למחיקה בסיום
    messages_to_delete: list = field(default_factory=list)  # רשימת Message objects
    
    def update_state(self, new_state: str):
        """עדכון מצב המשתמש"""
        logger.info(f"👤 User {self.user_id}: {self.state} → {new_state}")
        self.state = new_state
        self.updated_at = datetime.now()
    
    def add_file_for_cleanup(self, file_path: str):
        """הוספת קובץ לרשימת הניקוי"""
        if file_path and file_path not in self.files_to_cleanup:
            self.files_to_cleanup.append(file_path)
            logger.debug(f"📝 Added to cleanup list: {file_path}")
    
    def is_complete(self) -> bool:
        """בדיקה אם כל המידע נאסף"""
        return all([
            self.image_path,
            self.mp3_path,
            self.song_name,
            self.artist_name,
            self.year,
            self.composer,
            self.arranger,
            self.mixer,
            self.youtube_url
        ])
    
    def get_credits_text(self) -> str:
        """יוצר טקסט קרדיטים מהפרטים"""
        credits = []
        if self.song_name:
            credits.append(f"🎵 {self.song_name}")
        if self.artist_name:
            credits.append(f"🎤 {self.artist_name}")
        if self.year:
            credits.append(f"📅 {self.year}")
        if self.composer:
            credits.append(f"✍️ מלחין: {self.composer}")
        if self.arranger:
            credits.append(f"🎼 מעבד: {self.arranger}")
        if self.mixer:
            credits.append(f"🎚️ מיקס: {self.mixer}")
        
        return "\n".join(credits)
    
    def reset(self):
        """איפוס הסשן"""
        logger.info(f"🔄 Resetting session for user {self.user_id}")
        self.state = UserState.IDLE
        self.image_file_id = None
        self.image_path = None
        self.mp3_file_id = None
        self.mp3_path = None
        self.song_name = None
        self.artist_name = None
        self.year = None
        self.composer = None
        self.arranger = None
        self.mixer = None
        self.youtube_url = None
        self.need_video = False
        self.processed_image_path = None
        self.processed_mp3_path = None
        self.video_high_path = None
        self.video_medium_path = None
        self.instagram_url = None
        self.instagram_file_path = None
        self.instagram_media_type = None
        self.instagram_text = None
        self.instagram_download_time = None
        self.instagram_timeout_task = None
        self.files_to_cleanup = []
        self.messages_to_delete = []


class UserStateManager:
    """
    מנהל מצבי משתמשים
    Singleton pattern - מופע אחד לכל הבוט
    """
    _instance = None
    _sessions: Dict[int, UserSession] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserStateManager, cls).__new__(cls)
            cls._sessions = {}
        return cls._instance
    
    def get_session(self, user_id: int) -> UserSession:
        """קבלת סשן משתמש (יוצר חדש אם לא קיים)"""
        if user_id not in self._sessions:
            logger.info(f"✨ Creating new session for user {user_id}")
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]
    
    def delete_session(self, user_id: int):
        """מחיקת סשן משתמש"""
        if user_id in self._sessions:
            logger.info(f"🗑️ Deleting session for user {user_id}")
            del self._sessions[user_id]
    
    def reset_session(self, user_id: int):
        """איפוס סשן משתמש"""
        if user_id in self._sessions:
            self._sessions[user_id].reset()
        else:
            self._sessions[user_id] = UserSession(user_id=user_id)
    
    def get_all_sessions(self) -> Dict[int, UserSession]:
        """קבלת כל הסשנים"""
        return self._sessions
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """ניקוי סשנים ישנים"""
        now = datetime.now()
        to_delete = []
        
        for user_id, session in self._sessions.items():
            age = (now - session.updated_at).total_seconds() / 3600
            if age > max_age_hours:
                to_delete.append(user_id)
        
        for user_id in to_delete:
            logger.info(f"🧹 Cleaning up old session for user {user_id}")
            self.delete_session(user_id)
        
        return len(to_delete)
    
    def cleanup_files_periodically(self, max_files_per_session: int = 50):
        """
        ניקוי תקופתי של רשימת קבצים לניקוי - מונע memory leaks
        שומר רק את הקבצים האחרונים
        """
        cleaned_count = 0
        for user_id, session in self._sessions.items():
            if len(session.files_to_cleanup) > max_files_per_session:
                # שומר רק את הקבצים האחרונים
                old_count = len(session.files_to_cleanup)
                session.files_to_cleanup = session.files_to_cleanup[-max_files_per_session:]
                cleaned_count += (old_count - max_files_per_session)
                logger.debug(f"🧹 Cleaned {old_count - max_files_per_session} old file references from session {user_id}")
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned {cleaned_count} old file references from all sessions")
        
        return cleaned_count


# יצירת מופע גלובלי
state_manager = UserStateManager()

