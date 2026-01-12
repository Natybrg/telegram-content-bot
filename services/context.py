"""
Application Context Service
מנהל את ההקשר הגלובלי של האפליקציה (bot, userbot, וכו')
פותר את בעיית התלות ההפוכה בין plugins ל-main
"""
import logging
from typing import Optional
from pyrogram import Client

logger = logging.getLogger(__name__)


class AppContext:
    """
    Singleton service locator להחזקת משתנים גלובליים
    """
    _instance: Optional['AppContext'] = None
    _bot: Optional[Client] = None
    _userbot: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_bot(self, bot: Client) -> None:
        """מגדיר את ה-bot client"""
        self._bot = bot
        logger.info("✅ AppContext: Bot client registered")
    
    def set_userbot(self, userbot: Client) -> None:
        """מגדיר את ה-userbot client"""
        self._userbot = userbot
        logger.info("✅ AppContext: Userbot client registered")
    
    def get_bot(self) -> Optional[Client]:
        """מחזיר את ה-bot client"""
        return self._bot
    
    def get_userbot(self) -> Optional[Client]:
        """מחזיר את ה-userbot client"""
        return self._userbot
    
    def is_ready(self) -> bool:
        """בודק אם ה-context מוכן (bot ו-userbot מאותחלים)"""
        return self._bot is not None and self._userbot is not None


# פונקציה עזר לגישה נוחה
def get_context() -> AppContext:
    """מחזיר את ה-AppContext instance"""
    return AppContext()

