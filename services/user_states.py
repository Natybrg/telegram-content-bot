"""
User States Manager
ניהול מצבי משתמשים בתהליך יצירת תוכן
"""
import logging
from typing import Dict
from datetime import datetime

# Import models from new models layer
from models import UserState, UserSession

logger = logging.getLogger(__name__)


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

