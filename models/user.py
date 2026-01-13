"""
User Models
Data models for user state and session management
"""
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Any


class UserState:
    """מצבים אפשריים של משתמש"""
    IDLE = "idle"  # לא פעיל
    WAITING_IMAGE = "waiting_image"  # ממתין לתמונה
    WAITING_MP3 = "waiting_mp3"  # ממתין לקובץ MP3
    WAITING_DETAILS = "waiting_details"  # ממתין ל-8 שורות פרטים
    WAITING_VIDEO_ONLY_DETAILS = "waiting_video_only_details"  # ממתין ל-3 שורות לוידאו בלבד
    WAITING_INSTAGRAM_URL = "waiting_instagram_url"  # ממתין לקישור אינסטגרם
    WAITING_INSTAGRAM_TEXT = "waiting_instagram_text"  # ממתין לטקסט לאינסטגרם
    WAITING_INSTAGRAM_TEMPLATE_EDIT = "waiting_instagram_template_edit"  # ממתין לעריכת תבניות אינסטגרם
    PROCESSING = "processing"  # מעבד את התוכן
    EDITING_TEMPLATE = "editing_template"  # עורך תבנית
    UPDATING_COOKIES = "updating_cookies"  # מעדכן קובץ cookies
    ADDING_CHANNEL = "adding_channel"  # מוסיף ערוץ/קבוצה למאגר


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
    song_name: Optional[str] = None  # שם שיר
    artist_name: Optional[str] = None  # שם זמר
    year: Optional[str] = None  # שנה
    composer: Optional[str] = None  # שם מלחין
    arranger: Optional[str] = None  # שם מעבד
    mixer: Optional[str] = None  # שם מיקס
    youtube_url: Optional[str] = None  # קישור ליוטיוב
    need_video: bool = False  # כן/לא (האם צריך וידאו)
    
    # קבצים שנוצרו
    processed_image_path: Optional[str] = None  # תמונה עם קרדיטים
    processed_mp3_path: Optional[str] = None  # MP3 עם תגיות
    video_high_path: Optional[str] = None  # וידאו איכותי
    video_medium_path: Optional[str] = None  # וידאו בינוני
    
    # אינסטגרם
    instagram_url: Optional[str] = None  # קישור לאינסטגרם
    instagram_file_path: Optional[str] = None  # נתיב לקובץ שהורד מאינסטגרם
    instagram_media_type: Optional[str] = None  # סוג המדיה (video/image)
    instagram_text: Optional[str] = None  # טקסט להעלאה
    instagram_download_time: Optional[datetime] = None  # זמן סיום ההורדה
    instagram_timeout_task: Optional[Any] = None  # טיימר לניקוי אוטומטי
    
    # מטא-דאטה
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    files_to_cleanup: list = field(default_factory=list)
    
    # מעקב הודעות למחיקה בסיום
    messages_to_delete: list = field(default_factory=list)  # רשימת Message objects
    
    def update_state(self, new_state: str):
        """עדכון מצב המשתמש"""
        self.state = new_state
        self.updated_at = datetime.now()
    
    def add_file_for_cleanup(self, file_path: str):
        """הוספת קובץ לרשימת הניקוי"""
        if file_path and file_path not in self.files_to_cleanup:
            self.files_to_cleanup.append(file_path)
    
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
