"""
Template Manager
מנהל תבניות טקסט לשימוש בבוט
"""

import json
from pathlib import Path
from typing import Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """
    מנקה markdown מתוכן - escape תווים מיוחדים של Telegram markdown
    לא עושה escape לקישורים (URLs) כדי שלא יוסיף backslash
    
    Args:
        text: הטקסט לניקוי
    
    Returns:
        טקסט עם תווים מיוחדים escaped (חוץ מקישורים)
    """
    import re
    
    # זיהוי קישורים (http/https/ftp וכו')
    url_pattern = r'(https?://[^\s]+|ftp://[^\s]+)'
    urls = re.findall(url_pattern, text)
    
    # החלפת קישורים ב-placeholder זמני (ללא תווים מיוחדים כדי שלא יעשה להם escape)
    placeholders = {}
    for i, url in enumerate(urls):
        # שימוש ב-placeholder ללא תווים מיוחדים (ללא underscores, נקודות וכו')
        placeholder = f"URLPLACEHOLDER{i}URLPLACEHOLDER"
        placeholders[placeholder] = url
        text = text.replace(url, placeholder, 1)
    
    # רשימת תווים מיוחדים ב-Telegram markdown v2
    # הערה: הסרנו '.' מהרשימה כדי לא לעשות escape לנקודות בקישורים
    # '|' הוסר כי הוא לא תו מיוחד ב-markdown v2 (רק בטבלאות, אבל אנחנו לא משתמשים בטבלאות)
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '{', '}', '!']
    
    # Escape כל תו מיוחד (חוץ מקישורים)
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    # החזרת קישורים למקום (ללא escape)
    for placeholder, url in placeholders.items():
        text = text.replace(placeholder, url)
    
    return text


class TemplateManager:
    """מנהל תבניות עם שמירה ב-JSON"""
    
    def __init__(self, file_path="templates.json"):
        self.file_path = Path(file_path)
        self.templates = self._load()
    
    def _load(self) -> Dict[str, str]:
        """טוען תבניות מקובץ, או יוצר ברירות מחדל"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load templates: {e}")
                return self._get_defaults()
        return self._get_defaults()
    
    def _get_defaults(self) -> Dict[str, str]:
        """מחזיר תבניות ברירת מחדל"""
        return {
            "telegram_image": "━━━━━━━━━━━━━━\n💬 **שם השיר:** {song_name}\n🎙 **אמן:** {artist_name}\n🎼 **לחן:** {composer}\n🖥 **עיבוד:** {arranger}\n🎛 **מיקס:** {mixer}\n🎥 **לצפיה ביוטיוב** 👇\n{youtube_url}\n━━━━━━━━━━━━━━\n\nקרדיט: [חסידי〽️יוזיק](https://t.me/Hasidim_music)",
            "telegram_audio": "~ חסידי〽️יוזיק\n👉@Hasidim_music 👈",
            "telegram_video": "[{artist_name} - {song_name}](youtube_url)\n🎥 איכות: 1080\n\n~ חסידי〽️יוזיק\n👉 @Hasidim_music_videos 👈",
            "telegram_instagram": "{text}\n\n~ חסידי〽️יוזיק\n👉 @Hasidim_music 👈",
            "whatsapp_image": "━━━━━━━━━━━━━━\n💬 *שם השיר:* {song_name}\n🎙 *אמן:* {artist_name}\n🎼 *לחן:* {composer}\n🖥 *עיבוד:* {arranger}\n🎛 *מיקס:* {mixer}\n🎥 *לצפיה ביוטיוב 👇*\n{youtube_url}\n━━━━━━━━━━━━━━\n\n> *חסידי〽️יוזיק • להצטרפות:*\nhttps://wa.me/message/Z23YZZO5Q66PC1",
            "whatsapp_audio": "> חסידי〽️יוזיק • שתפו 📲\nhttps://chat.whatsapp.com/Ijco9Y19CkE8G0TiBtY1fu",
            "whatsapp_video": "*{artist_name} - {song_name}*\nהקליפ המלא | צפו 🎥\n\n> *חסידי〽️יוזיק • שתפו 📲*\nhttps://chat.whatsapp.com/Ijco9Y19CkE8G0TiBtY1fu",
            "whatsapp_instagram": "{text}\n\n> *חסידי〽️יוזיק • שתפו 📲*\nhttps://chat.whatsapp.com/Ijco9Y19CkE8G0TiBtY1fu",
            "whatsapp_status": "*{song_name}* - {artist_name}\n🎵 עכשיו ב-WhatsApp Status\n\n{youtube_url}"
        }
    
    def save(self):
        """שומר תבניות לקובץ"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
            logger.info(f"Templates saved to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save templates: {e}")
    
    def get(self, name: str) -> str:
        """מחזיר תבנית לפי שם"""
        return self.templates.get(name, "")
    
    def set(self, name: str, content: str):
        """מעדכן תבנית ושומר"""
        if not content or not content.strip():
            logger.warning(f"Attempted to set empty template for '{name}'")
            raise ValueError(f"Template '{name}' cannot be empty")
        
        self.templates[name] = content
        self.save()
        logger.info(f"✅ Template '{name}' updated and saved successfully")
    
    def render(self, name: str, **kwargs: Any) -> str:
        """מרנדר תבנית עם משתנים"""
        template = self.get(name)
        try:
            # סניטיזציה של ערכי המשתנים (escape markdown)
            escaped_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str):
                    escaped_kwargs[key] = escape_markdown(value)
                else:
                    escaped_kwargs[key] = value
            # מטפל גם במשתנים שלא קיימים בתבנית
            return template.format(**escaped_kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in template '{name}': {e}")
            return template
    
    def get_all(self) -> Dict[str, str]:
        """מחזיר את כל התבניות"""
        return self.templates.copy()
    
    def reset_to_defaults(self):
        """מאפס את כל התבניות לברירת מחדל"""
        self.templates = self._get_defaults()
        self.save()
        logger.info("Templates reset to defaults")


# אינסטנס גלובלי
template_manager = TemplateManager()
