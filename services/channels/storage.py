"""
Channels Storage
שמירה וטעינה של מאגר ערוצים/קבוצות מ-JSON
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ChannelsStorage:
    """מנהל שמירה וטעינה של מאגר ערוצים/קבוצות"""
    
    def __init__(self, file_path: str = "channels.json"):
        self.file_path = Path(file_path)
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """טוען נתונים מקובץ, או יוצר מבנה ברירת מחדל"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # וידוא שהמבנה תקין
                    return self._validate_structure(data)
            except Exception as e:
                logger.error(f"Failed to load channels: {e}")
                return self._get_default_structure()
        return self._get_default_structure()
    
    def _get_default_structure(self) -> Dict[str, Any]:
        """מחזיר מבנה ברירת מחדל"""
        return {
            "repository": {
                "telegram": [],  # רשימת ערוצי טלגרם ציבוריים
                "whatsapp": []   # רשימת קבוצות וואטסאפ
            },
            "template_links": {
                # כל תבנית יכולה להיות מקושרת לערוצים/קבוצות מהמאגר
                # "telegram_image": {"telegram": ["channel1", "channel2"], "whatsapp": []},
                # "whatsapp_image": {"telegram": [], "whatsapp": ["group1", "group2"]}
            }
        }
    
    def _validate_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """מוודא שהמבנה תקין"""
        default = self._get_default_structure()
        
        # וידוא שיש repository
        if "repository" not in data:
            data["repository"] = default["repository"]
        else:
            if "telegram" not in data["repository"]:
                data["repository"]["telegram"] = []
            if "whatsapp" not in data["repository"]:
                data["repository"]["whatsapp"] = []
        
        # וידוא שיש template_links
        if "template_links" not in data:
            data["template_links"] = {}
        
        return data
    
    def save(self):
        """שומר נתונים לקובץ"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            logger.info(f"Channels data saved to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save channels: {e}")
    
    def get_repository(self, platform: str) -> List[str]:
        """מחזיר את רשימת הערוצים/קבוצות במאגר לפלטפורמה מסוימת"""
        return self.data["repository"].get(platform, []).copy()
    
    def add_to_repository(self, platform: str, channel_id: str):
        """מוסיף ערוץ/קבוצה למאגר"""
        if platform not in ["telegram", "whatsapp"]:
            raise ValueError(f"Invalid platform: {platform}")
        
        if channel_id not in self.data["repository"][platform]:
            self.data["repository"][platform].append(channel_id)
            self.save()
            logger.info(f"Added {platform} channel/group: {channel_id}")
        else:
            logger.warning(f"{platform} channel/group already exists: {channel_id}")
    
    def remove_from_repository(self, platform: str, channel_id: str):
        """מסיר ערוץ/קבוצה מהמאגר"""
        if platform not in ["telegram", "whatsapp"]:
            raise ValueError(f"Invalid platform: {platform}")
        
        if channel_id in self.data["repository"][platform]:
            self.data["repository"][platform].remove(channel_id)
            # הסרה גם מכל הקישורים לתבניות
            self._remove_from_all_template_links(platform, channel_id)
            self.save()
            logger.info(f"Removed {platform} channel/group: {channel_id}")
        else:
            logger.warning(f"{platform} channel/group not found: {channel_id}")
    
    def _remove_from_all_template_links(self, platform: str, channel_id: str):
        """מסיר ערוץ/קבוצה מכל הקישורים לתבניות"""
        for template_name, links in self.data["template_links"].items():
            if platform in links and channel_id in links[platform]:
                links[platform].remove(channel_id)
    
    def get_template_links(self, template_name: str) -> Dict[str, List[str]]:
        """מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית מסוימת"""
        return self.data["template_links"].get(template_name, {
            "telegram": [],
            "whatsapp": []
        }).copy()
    
    def set_template_link(self, template_name: str, platform: str, channel_id: str, active: bool):
        """מגדיר אם ערוץ/קבוצה פעיל עבור תבנית מסוימת"""
        if template_name not in self.data["template_links"]:
            self.data["template_links"][template_name] = {
                "telegram": [],
                "whatsapp": []
            }
        
        if platform not in self.data["template_links"][template_name]:
            self.data["template_links"][template_name][platform] = []
        
        links = self.data["template_links"][template_name][platform]
        
        if active:
            if channel_id not in links:
                links.append(channel_id)
        else:
            if channel_id in links:
                links.remove(channel_id)
        
        self.save()
        logger.info(f"Template '{template_name}' link updated: {platform}/{channel_id} = {active}")
    
    def get_active_channels_for_template(self, template_name: str, platform: str) -> List[str]:
        """מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית ופלטפורמה מסוימת"""
        links = self.get_template_links(template_name)
        return links.get(platform, [])

