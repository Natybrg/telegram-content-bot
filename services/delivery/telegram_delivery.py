"""
Telegram Delivery Service
שירות לשליחת תוכן לטלגרם
"""
import logging
import os
from typing import Dict, Any, List, Optional
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid

from services.channels import channels_manager, send_to_telegram_channels
from services.templates import template_manager
from core.context import get_context

logger = logging.getLogger(__name__)


async def send_content_to_telegram(
    client: Client,
    session,
    file_path: str,
    file_type: str,  # 'photo', 'audio', 'video'
    template_name: str,
    template_vars: Dict[str, Any],
    channels: Optional[List[str]] = None,
    first_channel_id: Optional[str] = None,
    protected_channels: Optional[List[str]] = None,
    **kwargs  # פרמטרים נוספים (title, performer, duration, thumb, width, height)
) -> Dict[str, Any]:
    """
    שולח תוכן לטלגרם
    
    Args:
        client: Pyrogram Client
        session: אובייקט סשן המשתמש
        file_path: נתיב הקובץ המקומי
        file_type: סוג הקובץ ('photo', 'audio', 'video')
        template_name: שם התבנית (למשל 'telegram_image', 'telegram_audio', 'telegram_video')
        template_vars: משתנים לתבנית
        channels: רשימת ערוצים (אם None, יאוסף מהמאגר)
        first_channel_id: ערוץ ראשון להעלאה
        protected_channels: ערוצים מוגנים
        **kwargs: פרמטרים נוספים (width, height, thumb, title, performer, duration)
        
    Returns:
        מילון עם תוצאות: {'success': bool, 'sent_to': List[str], 'error': str}
    """
    try:
        # איסוף רשימת ערוצים אם לא סופקו
        if channels is None:
            channels = []
            template_channels = channels_manager.get_template_channels(template_name, "telegram")
            if template_channels:
                channels.extend(template_channels)
            channels = list(dict.fromkeys(channels))  # הסרת כפילויות
        
        if not channels:
            logger.info(f"ℹ️ [TELEGRAM] אין ערוצים להעלאה עבור {template_name}")
            return {'success': False, 'error': 'No channels available', 'sent_to': []}
        
        logger.info(f"📤 [TELEGRAM] שולח {file_type} ל-{len(channels)} ערוצים")
        
        # יצירת caption מהתבנית
        caption = template_manager.render(template_name, **template_vars)
        
        # בחירת client לפרסום (userbot אם זמין, אחרת bot)
        bot = client
        userbot = None
        try:
            context = get_context()
            userbot = context.get_userbot()
            if userbot:
                logger.info("✅ [TELEGRAM] Userbot זמין לקבצים גדולים")
            else:
                logger.warning("⚠️ [TELEGRAM] Userbot לא זמין - משתמש בבוט רגיל")
        except Exception as e:
            logger.warning(f"⚠️ [TELEGRAM] Could not access userbot: {e}")
        
        channel_client = userbot if userbot else bot
        client_type = "Userbot" if userbot else "Bot"
        logger.info(f"ℹ️ [TELEGRAM → CHANNEL] משתמש ב-{client_type} לפרסום")
        
        # טעינת ערוצים ל-storage לפני שליחה (חשוב מאוד!)
        logger.info(f"🔄 [TELEGRAM → CHANNEL] טוען ערוצים ל-storage של ה-{client_type}...")
        for channel_id in channels:
            try:
                logger.info(f"🔍 [TELEGRAM → CHANNEL] בודק ערוץ: {channel_id}")
                chat_obj = await channel_client.get_chat(channel_id)
                logger.info(f"✅ [TELEGRAM → CHANNEL] ערוץ {channel_id} נטען בהצלחה: {chat_obj.title if hasattr(chat_obj, 'title') else 'N/A'}")
            except PeerIdInvalid as e:
                logger.error(f"❌ [TELEGRAM → CHANNEL] ערוץ {channel_id} לא נגיש: PeerIdInvalid")
                logger.error(f"💡 [TELEGRAM → CHANNEL] פתרון: שלח הודעה מה-{client_type} לערוץ {channel_id} כדי לטעון אותו ל-storage")
                logger.error(f"💡 [TELEGRAM → CHANNEL] או וודא שה-{client_type} חבר בערוץ {channel_id}")
            except Exception as e:
                logger.error(f"❌ [TELEGRAM → CHANNEL] שגיאה בטעינת ערוץ {channel_id}: {e}")
        
        # שליחה
        result = await send_to_telegram_channels(
            client=channel_client,
            file_path=file_path,
            file_type=file_type,
            caption=caption,
            channels=channels,
            first_channel_id=first_channel_id or (channels[0] if channels else None),
            protected_channels=protected_channels or [],
            **kwargs
        )
        
        if result.get('success'):
            logger.info(f"✅ [TELEGRAM] נשלח ל-{len(result.get('sent_to', []))} ערוצים")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ [TELEGRAM] שגיאה: {error_msg}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [TELEGRAM] שגיאה בשליחה: {e}", exc_info=True)
        return {'success': False, 'error': str(e), 'sent_to': []}
