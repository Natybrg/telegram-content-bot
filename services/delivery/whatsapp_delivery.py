"""
WhatsApp Delivery Service
שירות לשליחת תוכן לוואטסאפ
"""
import logging
import os
import asyncio
from typing import Dict, Any, List, Optional, Callable

import config
from services.whatsapp import WhatsAppDelivery
from services.channels import channels_manager, send_to_whatsapp_groups
from services.templates import template_manager

logger = logging.getLogger(__name__)


async def send_content_to_whatsapp(
    client,
    session,
    file_path: str,
    file_type: str,  # 'image', 'audio', 'video'
    template_name: str,
    template_vars: Dict[str, Any],
    groups: Optional[List[str]] = None,
    telegram_user_id: Optional[int] = None,
    telegram_fallback_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    שולח תוכן לוואטסאפ
    
    Args:
        client: Pyrogram Client (לצורך fallback)
        session: אובייקט סשן המשתמש
        file_path: נתיב הקובץ המקומי
        file_type: סוג הקובץ ('image', 'audio', 'video')
        template_name: שם התבנית (למשל 'whatsapp_image', 'whatsapp_audio', 'whatsapp_video')
        template_vars: משתנים לתבנית
        groups: רשימת קבוצות (אם None, יאוסף מהמאגר)
        telegram_user_id: מזהה משתמש טלגרם (לצורך fallback)
        telegram_fallback_callback: callback function לטלגרם fallback
        
    Returns:
        מילון עם תוצאות: {'success': bool, 'sent_to': List[str], 'errors': List[str]}
    """
    if not config.WHATSAPP_ENABLED:
        logger.info("ℹ️ [WHATSAPP] שליחה לוואטסאפ מנוטרלת")
        return {'success': False, 'error': 'WhatsApp disabled', 'sent_to': [], 'errors': []}
    
    try:
        # איסוף רשימת קבוצות אם לא סופקו
        if groups is None:
            groups = []
            template_groups = channels_manager.get_template_channels(template_name, "whatsapp")
            if template_groups:
                groups.extend(template_groups)
            groups = list(dict.fromkeys(groups))  # הסרת כפילויות
        
        if not groups:
            logger.info(f"ℹ️ [WHATSAPP] אין קבוצות לשליחה עבור {template_name}")
            return {'success': False, 'error': 'No groups available', 'sent_to': [], 'errors': []}
        
        logger.info(f"📱 [WHATSAPP] שולח {file_type} ל-{len(groups)} קבוצות")
        
        # יצירת caption מהתבנית
        # בדיקה אם זה "הסטטוס שלי" - אם כן, נשתמש בתבנית whatsapp_status
        current_caption = template_manager.render(template_name, **template_vars)
        if "הסטטוס שלי" in groups and session:
            try:
                # יצירת תבנית status עם המידע מה-session
                current_caption = template_manager.render(
                    "whatsapp_status",
                    song_name=session.song_name if hasattr(session, 'song_name') else "",
                    artist_name=session.artist_name if hasattr(session, 'artist_name') else "",
                    youtube_url=session.youtube_url if hasattr(session, 'youtube_url') else ""
                )
                logger.info("📱 [WHATSAPP] Using whatsapp_status template for status")
            except Exception as e:
                logger.warning(f"⚠️ [WHATSAPP] Failed to render status template, using default: {e}")
        
        # ניסיון לאתחל WhatsApp
        try:
            whatsapp = WhatsAppDelivery(dry_run=config.WHATSAPP_DRY_RUN)
        except Exception as whatsapp_init_error:
            logger.warning(f"⚠️ [WHATSAPP] לא ניתן לאתחל WhatsApp: {whatsapp_init_error}")
            logger.info("💡 [WHATSAPP] המשך בלי וואטסאפ")
            return {
                'success': False,
                'error': f"WhatsApp service not ready: {str(whatsapp_init_error)}",
                'sent_to': [],
                'errors': [str(whatsapp_init_error)]
            }
        
        try:
            # שליחה
            result = await send_to_whatsapp_groups(
                whatsapp_delivery=whatsapp,
                file_path=file_path,
                file_type=file_type,
                caption=current_caption,
                groups=groups,
                telegram_user_id=telegram_user_id,
                telegram_fallback_callback=telegram_fallback_callback,
                session=session
            )
            
            if result.get('success') and result.get('sent_to'):
                logger.info(f"✅ [WHATSAPP] נשלח ל-{len(result['sent_to'])} קבוצות")
            else:
                logger.warning(f"⚠️ [WHATSAPP] שליחה נכשלה: {result.get('errors', [])}")
            
            return result
            
        finally:
            if 'whatsapp' in locals():
                whatsapp.close()
                logger.info("✅ [WHATSAPP] שליחה הושלמה")
        
    except Exception as e:
        logger.error(f"❌ [WHATSAPP] שגיאה בשליחה: {e}", exc_info=True)
        return {'success': False, 'error': str(e), 'sent_to': [], 'errors': [str(e)]}
