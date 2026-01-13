"""
Channels Storage
שמירה וטעינה של מאגר ערוצים/קבוצות מ-JSON
משתמש ב-peer_id (Base64) במקום ID - פתרון יציב ל-Pyrogram
"""

import json
import base64
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

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
                "telegram": [],  # רשימת ערוצי טלגרם - כל ערך הוא dict עם peer_id_b64 ו-title
                "whatsapp": []   # רשימת קבוצות וואטסאפ (נשאר string - שם קבוצה)
            },
            "template_links": {
                # כל תבנית יכולה להיות מקושרת לערוצים/קבוצות מהמאגר
                # "telegram_image": {"telegram": ["peer_id_b64_1", "peer_id_b64_2"], "whatsapp": []},
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
        
        # מיגרציה: אם יש ערכים ישנים (strings), נמיר אותם
        # זה יקרה רק פעם אחת
        self._migrate_old_format(data)
        
        return data
    
    def _migrate_old_format(self, data: Dict[str, Any]):
        """מיגרציה מפורמט ישן (ID) לפורמט חדש (peer_id_b64)"""
        migrated = False
        
        # בדיקה אם יש ערכים ישנים (strings במקום dicts)
        for platform in ["telegram", "whatsapp"]:
            if platform in data.get("repository", {}):
                new_list = []
                for item in data["repository"][platform]:
                    if isinstance(item, str):
                        # זה פורמט ישן - נשמור אותו כ-is_legacy
                        # המיגרציה המלאה תיעשה בסקריפט נפרד
                        new_list.append({
                            "peer_id_b64": None,  # ימולא במיגרציה
                            "title": item,  # נשמור את ה-ID/שם כ-title זמני
                            "legacy_id": item,  # שמירת ה-ID הישן למיגרציה
                            "is_legacy": True
                        })
                        migrated = True
                    elif isinstance(item, dict):
                        # זה כבר פורמט חדש
                        new_list.append(item)
                    else:
                        logger.warning(f"Unknown format in repository[{platform}]: {item}")
                        continue
                
                if migrated:
                    data["repository"][platform] = new_list
                    logger.info(f"Migrated {platform} repository to new format (legacy items marked)")
        
        # מיגרציה של template_links
        if "template_links" in data:
            for template_name, links in data["template_links"].items():
                if "telegram" in links:
                    new_telegram = []
                    for item in links["telegram"]:
                        if isinstance(item, str):
                            # זה peer_id_b64 או legacy ID
                            # נבדוק אם זה Base64 (אורך טיפוסי)
                            if len(item) > 20 and not item.lstrip('-').isdigit():
                                # זה נראה כמו Base64
                                new_telegram.append(item)
                            else:
                                # זה legacy ID - נשמור אותו כמו שהוא, המיגרציה תטופל בסקריפט
                                new_telegram.append(item)
                        else:
                            new_telegram.append(item)
                    links["telegram"] = new_telegram
        
        if migrated:
            self.save()
            logger.info("Migration completed - legacy items marked for full migration")
    
    def save(self):
        """שומר נתונים לקובץ"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            logger.info(f"Channels data saved to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save channels: {e}")
    
    def get_repository(self, platform: str) -> List[Dict[str, Any]]:
        """
        מחזיר את רשימת הערוצים/קבוצות במאגר לפלטפורמה מסוימת
        
        Returns:
            עבור telegram: רשימת dicts עם peer_id_b64 ו-title
            עבור whatsapp: רשימת strings (שמות קבוצות)
        """
        if platform == "telegram":
            return self.data["repository"].get(platform, []).copy()
        else:
            # whatsapp - נשאר string
            return self.data["repository"].get(platform, []).copy()
    
    def add_to_repository(self, platform: str, peer_id_b64: str, title: Optional[str] = None, legacy_id: Optional[str] = None):
        """
        מוסיף ערוץ/קבוצה למאגר
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
            title: שם הערוץ (אופציונלי, עבור תצוגה)
            legacy_id: ID ישן (אופציונלי, למיגרציה)
        """
        if platform not in ["telegram", "whatsapp"]:
            raise ValueError(f"Invalid platform: {platform}")
        
        if platform == "telegram":
            # עבור telegram - שמירה כ-dict
            channel_entry = {
                "peer_id_b64": peer_id_b64,
                "title": title or "Unknown Channel"
            }
            if legacy_id:
                channel_entry["legacy_id"] = legacy_id
            
            # בדיקה אם כבר קיים (לפי peer_id_b64 או legacy_id)
            existing_by_peer_id = [ch for ch in self.data["repository"][platform] 
                                  if isinstance(ch, dict) and ch.get("peer_id_b64") == peer_id_b64]
            
            existing_by_legacy = []
            if legacy_id:
                existing_by_legacy = [ch for ch in self.data["repository"][platform] 
                                     if isinstance(ch, dict) and ch.get("legacy_id") == legacy_id]
            
            # בדיקה גם אם peer_id_b64 שווה ל-legacy_id של ערוץ אחר
            existing_by_peer_as_legacy = []
            if peer_id_b64 and not peer_id_b64.lstrip('-').isdigit():
                # אם peer_id_b64 הוא לא ID רגיל, נבדוק אם הוא קיים כ-legacy_id
                existing_by_peer_as_legacy = [ch for ch in self.data["repository"][platform] 
                                            if isinstance(ch, dict) and ch.get("legacy_id") == peer_id_b64]
            
            # בדיקה גם אם legacy_id קיים כ-peer_id_b64 של ערוץ אחר
            existing_by_legacy_as_peer = []
            if legacy_id and not legacy_id.lstrip('-').isdigit():
                # אם legacy_id הוא לא ID רגיל, נבדוק אם הוא קיים כ-peer_id_b64
                existing_by_legacy_as_peer = [ch for ch in self.data["repository"][platform] 
                                             if isinstance(ch, dict) and ch.get("peer_id_b64") == legacy_id]
            
            if existing_by_peer_id or existing_by_legacy or existing_by_peer_as_legacy or existing_by_legacy_as_peer:
                existing_channel = (existing_by_peer_id or existing_by_legacy or existing_by_peer_as_legacy or existing_by_legacy_as_peer)[0]
                existing_title = existing_channel.get("title", "Unknown Channel")
                logger.warning(f"{platform} channel already exists: {existing_title} (peer_id_b64: {peer_id_b64[:20] if len(peer_id_b64) > 20 else peer_id_b64}...)")
                return  # לא מוסיפים כפילות
            else:
                self.data["repository"][platform].append(channel_entry)
                self.save()
                logger.info(f"Added {platform} channel: {title or peer_id_b64[:20]}... (peer_id_b64: {peer_id_b64[:20]}...)")
        else:
            # עבור whatsapp - נשאר string
            if peer_id_b64 not in self.data["repository"][platform]:
                self.data["repository"][platform].append(peer_id_b64)
                self.save()
                logger.info(f"Added {platform} group: {peer_id_b64}")
            else:
                logger.warning(f"{platform} group already exists: {peer_id_b64}")
    
    def remove_from_repository(self, platform: str, peer_id_b64: str):
        """
        מסיר ערוץ/קבוצה מהמאגר
        
        Args:
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
        """
        if platform not in ["telegram", "whatsapp"]:
            raise ValueError(f"Invalid platform: {platform}")
        
        if platform == "telegram":
            # עבור telegram - חיפוש לפי peer_id_b64
            original_count = len(self.data["repository"][platform])
            self.data["repository"][platform] = [
                ch for ch in self.data["repository"][platform]
                if not (isinstance(ch, dict) and ch.get("peer_id_b64") == peer_id_b64)
            ]
            
            if len(self.data["repository"][platform]) < original_count:
                # הסרה גם מכל הקישורים לתבניות
                self._remove_from_all_template_links(platform, peer_id_b64)
                self.save()
                logger.info(f"Removed {platform} channel: {peer_id_b64[:20]}...")
            else:
                logger.warning(f"{platform} channel not found: {peer_id_b64[:20]}...")
        else:
            # עבור whatsapp - נשאר string
            if peer_id_b64 in self.data["repository"][platform]:
                self.data["repository"][platform].remove(peer_id_b64)
                # הסרה גם מכל הקישורים לתבניות
                self._remove_from_all_template_links(platform, peer_id_b64)
                self.save()
                logger.info(f"Removed {platform} group: {peer_id_b64}")
            else:
                logger.warning(f"{platform} group not found: {peer_id_b64}")
    
    def _remove_from_all_template_links(self, platform: str, peer_id_b64: str):
        """מסיר ערוץ/קבוצה מכל הקישורים לתבניות"""
        for template_name, links in self.data["template_links"].items():
            if platform in links:
                if platform == "telegram":
                    # עבור telegram - הסרה לפי peer_id_b64
                    links[platform] = [item for item in links[platform] if item != peer_id_b64]
                else:
                    # עבור whatsapp - נשאר string
                    if peer_id_b64 in links[platform]:
                        links[platform].remove(peer_id_b64)
    
    def get_template_links(self, template_name: str) -> Dict[str, List[str]]:
        """
        מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית מסוימת
        
        Returns:
            מילון עם 'telegram' ו-'whatsapp', כל אחד מכיל רשימת peer_id_b64 (עבור telegram) או שמות קבוצות (עבור whatsapp)
        """
        return self.data["template_links"].get(template_name, {
            "telegram": [],
            "whatsapp": []
        }).copy()
    
    def set_template_link(self, template_name: str, platform: str, peer_id_b64: str, active: bool):
        """
        מגדיר אם ערוץ/קבוצה פעיל עבור תבנית מסוימת
        
        Args:
            template_name: שם התבנית
            platform: 'telegram' או 'whatsapp'
            peer_id_b64: peer_id ב-Base64 (עבור telegram) או שם קבוצה (עבור whatsapp)
            active: True אם פעיל, False אחרת
        """
        if template_name not in self.data["template_links"]:
            self.data["template_links"][template_name] = {
                "telegram": [],
                "whatsapp": []
            }
        
        if platform not in self.data["template_links"][template_name]:
            self.data["template_links"][template_name][platform] = []
        
        links = self.data["template_links"][template_name][platform]
        
        if active:
            if peer_id_b64 not in links:
                links.append(peer_id_b64)
        else:
            if peer_id_b64 in links:
                links.remove(peer_id_b64)
        
        self.save()
        logger.info(f"Template '{template_name}' link updated: {platform}/{peer_id_b64[:20] if len(peer_id_b64) > 20 else peer_id_b64}... = {active}")
    
    def get_active_channels_for_template(self, template_name: str, platform: str) -> List[str]:
        """
        מחזיר את רשימת הערוצים/קבוצות הפעילים עבור תבנית ופלטפורמה מסוימת
        
        Returns:
            רשימת peer_id_b64 (עבור telegram) או שמות קבוצות (עבור whatsapp)
        """
        links = self.get_template_links(template_name)
        return links.get(platform, [])
