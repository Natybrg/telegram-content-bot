"""
Channels Manager
מנהל ערוצים וקבוצות - לוגיקה מרכזית
משתמש ב-peer_id (Base64) במקום ID
"""

import logging
from typing import List, Dict, Optional
from .storage import ChannelsStorage

logger = logging.getLogger(__name__)


class ChannelsManager:
    """מנהל ערוצים וקבוצות"""
    
    def __init__(self):
        self.storage = ChannelsStorage()
    
    # ========== ניהול מאגר ==========
    
    def get_repository(self, platform: str) -> List:
        """
        מחזיר את רשימת הערוצים/קבוצות במאגר
        
        Returns:
            עבור telegram: רשימת dicts עם peer_id_b64 ו-title
            עבור whatsapp: רשימת strings (שמות קבוצות)
        """
        return self.storage.get_repository(platform)
    
    def get_telegram_peer_ids(self, platform: str = "telegram") -> List[str]:
        """
        מחזיר רשימת peer_id_b64 או ID רגיל עבור ערוצי טלגרם
        
        Returns:
            רשימת peer_id_b64 (strings) או ID רגיל (strings)
        """
        if platform != "telegram":
            return []
        
        repository = self.get_repository(platform)
        peer_ids = []
        
        for item in repository:
            if isinstance(item, dict):
                # נשתמש ב-peer_id_b64 אם יש, אחרת ב-legacy_id
                if "peer_id_b64" in item and item["peer_id_b64"]:
                    peer_ids.append(item["peer_id_b64"])
                elif "legacy_id" in item and item["legacy_id"]:
                    # נשתמש ב-legacy_id אם אין peer_id_b64
                    peer_ids.append(str(item["legacy_id"]))
            elif isinstance(item, str):
                # זה legacy או Base64 string ישיר
                peer_ids.append(item)
        
        return peer_ids
    
    def add_channel(self, platform: str, peer_id_b64: str, title: Optional[str] = None, legacy_id: Optional[str] = None):
        """
        מוסיף ערוץ/קבוצה למאגר
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
            title: שם הערוץ (אופציונלי, עבור תצוגה)
            legacy_id: ID ישן (אופציונלי, למיגרציה)
        """
        self.storage.add_to_repository(platform, peer_id_b64, title, legacy_id)
    
    def remove_channel(self, platform: str, peer_id_b64: str):
        """
        מסיר ערוץ/קבוצה מהמאגר
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
        """
        self.storage.remove_from_repository(platform, peer_id_b64)
    
    def is_in_repository(self, platform: str, peer_id_b64: str) -> bool:
        """
        בודק אם ערוץ/קבוצה נמצא במאגר
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
        
        Returns:
            True אם נמצא, False אחרת
        """
        repository = self.get_repository(platform)
        
        if platform == "telegram":
            # עבור telegram - חיפוש לפי peer_id_b64
            for item in repository:
                if isinstance(item, dict) and item.get("peer_id_b64") == peer_id_b64:
                    return True
                elif isinstance(item, str) and item == peer_id_b64:
                    return True
            return False
        else:
            # עבור whatsapp - תמיכה גם ב-dicts (מיגרציה)
            for item in repository:
                if isinstance(item, dict):
                    # פורמט חדש (dict) - נבדוק לפי peer_id_b64 או title
                    if item.get("peer_id_b64") == peer_id_b64 or item.get("title") == peer_id_b64:
                        return True
                elif isinstance(item, str):
                    # פורמט ישן (string) - שם הקבוצה
                    if item == peer_id_b64:
                        return True
            return False
    
    def get_channel_title(self, platform: str, peer_id_b64: str) -> Optional[str]:
        """
        מחזיר את שם הערוץ/קבוצה
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
        
        Returns:
            שם הערוץ/קבוצה או None
        """
        if platform == "telegram":
            repository = self.get_repository(platform)
            for item in repository:
                if isinstance(item, dict) and item.get("peer_id_b64") == peer_id_b64:
                    return item.get("title")
        return None
    
    # ========== ניהול קישורים לתבניות ==========
    
    def get_template_channels(self, template_name: str, platform: str) -> List[str]:
        """
        מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית
        
        Returns:
            רשימת peer_id_b64 (עבור telegram) או שמות קבוצות (עבור whatsapp)
        """
        return self.storage.get_active_channels_for_template(template_name, platform)
    
    def set_template_channel_active(self, platform: str, peer_id_b64: str, template_name: str, active: bool):
        """
        מגדיר אם ערוץ/קבוצה פעיל עבור תבנית
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
            template_name: שם התבנית
            active: True אם פעיל, False אחרת
        """
        # וידוא שהערוץ/קבוצה נמצא במאגר
        if not self.is_in_repository(platform, peer_id_b64):
            raise ValueError(f"Channel/group '{peer_id_b64[:20] if len(peer_id_b64) > 20 else peer_id_b64}...' not in repository")
        
        self.storage.set_template_link(template_name, platform, peer_id_b64, active)
    
    def is_template_channel_active(self, template_name: str, platform: str, peer_id_b64: str) -> bool:
        """
        בודק אם ערוץ/קבוצה פעיל עבור תבנית
        
        Args:
            template_name: שם התבנית
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
        
        Returns:
            True אם פעיל, False אחרת
        """
        active_channels = self.get_template_channels(template_name, platform)
        return peer_id_b64 in active_channels
    
    def get_all_template_channels_status(self, template_name: str, platform: str) -> Dict[str, bool]:
        """
        מחזיר את סטטוס כל הערוצים/קבוצות במאגר עבור תבנית
        
        Returns:
            מילון: {peer_id_b64: bool} עבור telegram, {group_name: bool} עבור whatsapp
        """
        repository = self.get_repository(platform)
        active_channels = self.get_template_channels(template_name, platform)
        
        result = {}
        
        if platform == "telegram":
            for item in repository:
                if isinstance(item, dict) and "peer_id_b64" in item:
                    peer_id_b64 = item["peer_id_b64"]
                    result[peer_id_b64] = peer_id_b64 in active_channels
                elif isinstance(item, str):
                    result[item] = item in active_channels
        else:
            # whatsapp - תמיכה גם ב-dicts (מיגרציה)
            for group_item in repository:
                if isinstance(group_item, dict):
                    # פורמט חדש (dict) - נשתמש ב-title או peer_id_b64
                    group_ref = group_item.get("peer_id_b64") or group_item.get("title", "")
                    if group_ref:
                        result[group_ref] = group_ref in active_channels
                elif isinstance(group_item, str):
                    # פורמט ישן (string) - שם הקבוצה
                    result[group_item] = group_item in active_channels
        
        return result
    
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
