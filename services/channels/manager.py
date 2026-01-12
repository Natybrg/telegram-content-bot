"""
Channels Manager
מנהל ערוצים וקבוצות - לוגיקה מרכזית
"""

import logging
from typing import List, Dict
from .storage import ChannelsStorage

logger = logging.getLogger(__name__)


class ChannelsManager:
    """מנהל ערוצים וקבוצות"""
    
    def __init__(self):
        self.storage = ChannelsStorage()
    
    # ========== ניהול מאגר ==========
    
    def get_repository(self, platform: str) -> List[str]:
        """מחזיר את רשימת הערוצים/קבוצות במאגר"""
        return self.storage.get_repository(platform)
    
    def add_channel(self, platform: str, channel_id: str):
        """מוסיף ערוץ/קבוצה למאגר"""
        self.storage.add_to_repository(platform, channel_id)
    
    def remove_channel(self, platform: str, channel_id: str):
        """מסיר ערוץ/קבוצה מהמאגר"""
        self.storage.remove_from_repository(platform, channel_id)
    
    def is_in_repository(self, platform: str, channel_id: str) -> bool:
        """בודק אם ערוץ/קבוצה נמצא במאגר"""
        return channel_id in self.storage.get_repository(platform)
    
    # ========== ניהול קישורים לתבניות ==========
    
    def get_template_channels(self, template_name: str, platform: str) -> List[str]:
        """מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית"""
        return self.storage.get_active_channels_for_template(template_name, platform)
    
    def set_template_channel_active(self, template_name: str, platform: str, channel_id: str, active: bool):
        """מגדיר אם ערוץ/קבוצה פעיל עבור תבנית"""
        # וידוא שהערוץ/קבוצה נמצא במאגר
        if not self.is_in_repository(platform, channel_id):
            raise ValueError(f"Channel/group '{channel_id}' not in repository")
        
        self.storage.set_template_link(template_name, platform, channel_id, active)
    
    def is_template_channel_active(self, template_name: str, platform: str, channel_id: str) -> bool:
        """בודק אם ערוץ/קבוצה פעיל עבור תבנית"""
        active_channels = self.get_template_channels(template_name, platform)
        return channel_id in active_channels
    
    def get_all_template_channels_status(self, template_name: str, platform: str) -> Dict[str, bool]:
        """מחזיר את סטטוס כל הערוצים/קבוצות במאגר עבור תבנית"""
        repository = self.get_repository(platform)
        active_channels = self.get_template_channels(template_name, platform)
        
        return {
            channel_id: channel_id in active_channels
            for channel_id in repository
        }
    
    # ========== פונקציות עזר ==========
    
    def get_template_platform(self, template_name: str) -> str:
        """מחזיר את הפלטפורמה של התבנית (telegram או whatsapp)"""
        if template_name.startswith("telegram_"):
            return "telegram"
        elif template_name.startswith("whatsapp_"):
            return "whatsapp"
        else:
            raise ValueError(f"Cannot determine platform for template: {template_name}")


# אינסטנס גלובלי
channels_manager = ChannelsManager()

