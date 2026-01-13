"""
Smart Channel Sender
שליחה חכמה לערוצים/קבוצות עם אופטימיזציה
משתמש ב-peer_id (Base64) במקום ID - פתרון יציב ל-Pyrogram
"""

import base64
import logging
from typing import List, Dict, Optional, Tuple
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid, ChannelInvalid, UsernameInvalid

logger = logging.getLogger(__name__)


def decode_peer_id(peer_id_b64: str):
    """
    מפענח peer_id מ-Base64 או מחזיר ID רגיל
    
    Args:
        peer_id_b64: peer_id ב-Base64 או ID רגיל (int/str)
    
    Returns:
        peer_id כ-bytes (אם base64) או int/str (אם ID רגיל)
    """
    # בדיקה אם זה ID רגיל (מתחיל ב- או מספר)
    if peer_id_b64.startswith('-') or peer_id_b64.lstrip('-').isdigit():
        try:
            # זה ID רגיל - מחזירים אותו כ-int או str
            peer_id_int = int(peer_id_b64)
            logger.debug(f"📊 [PEER_ID] Using regular channel ID: {peer_id_int}")
            return peer_id_int
        except ValueError:
            # לא מספר תקין - ננסה base64
            pass
    
    # ננסה לפרש כ-base64
    try:
        decoded = base64.b64decode(peer_id_b64.encode("utf-8"), validate=True)
        logger.debug(f"📊 [PEER_ID] Decoded base64 peer_id: {len(decoded)} bytes")
        return decoded
    except Exception as e:
        # אם זה לא base64 תקין, ננסה להשתמש ב-ID ישירות
        logger.warning(f"⚠️ [PEER_ID] Failed to decode as base64, using as-is: {e}")
        # אם זה לא מספר, נחזיר את המחרוזת המקורית
        return peer_id_b64


async def send_to_telegram_channels(
    client: Client,
    file_path: str,
    file_type: str,  # 'photo', 'audio', 'video'
    caption: str,
    channels: List[str],  # רשימת peer_id_b64
    first_channel_peer_id_b64: Optional[str] = None,  # ערוץ ראשון להעלאה
    protected_channels: Optional[List[str]] = None,  # ערוצים מוגנים (peer_id_b64)
    **kwargs  # פרמטרים נוספים (title, performer, duration, thumb, width, height)
) -> Dict[str, any]:
    """
    שליחה חכמה לטלגרם - העלאה פעם אחת, שימוש ב-file_id לשאר
    משתמש ב-peer_id (Base64) במקום ID
    
    Args:
        client: Pyrogram Client
        file_path: נתיב הקובץ המקומי
        file_type: סוג הקובץ ('photo', 'audio', 'video')
        caption: כותרת להודעה
        channels: רשימת peer_id_b64
        first_channel_peer_id_b64: peer_id_b64 של ערוץ ראשון להעלאה (אם None, משתמש בערוץ הראשון ברשימה)
        protected_channels: רשימת peer_id_b64 של ערוצים מוגנים שלא יוסרו גם אם הבדיקה נכשלת
        **kwargs: פרמטרים נוספים (title, performer, duration, thumb, width, height)
    
    Returns:
        מילון עם תוצאות: {'success': bool, 'uploaded_to': str, 'file_id': str, 'sent_to': List[str], 'errors': List[str]}
    """
    if not channels:
        return {'success': False, 'error': 'No channels provided'}
    
    # בחירת ערוץ ראשון להעלאה
    upload_channel_peer_id_b64 = None
    if first_channel_peer_id_b64:
        upload_channel_peer_id_b64 = first_channel_peer_id_b64
        logger.debug(f"🔍 [TELEGRAM] Using first_channel_peer_id_b64: {upload_channel_peer_id_b64[:20]}...")
    else:
        upload_channel_peer_id_b64 = channels[0] if channels else None
        logger.debug(f"🔍 [TELEGRAM] Using first channel from list: {upload_channel_peer_id_b64[:20] if upload_channel_peer_id_b64 else 'None'}...")
    
    if not upload_channel_peer_id_b64:
        return {'success': False, 'error': 'No channel provided for upload'}
    
    # השוואה בטוחה בין ערוצים - ממירים למחרוזת כדי למנוע שגיאות השוואה
    other_channels = [ch for ch in channels if str(ch) != str(upload_channel_peer_id_b64)]
    
    results = {
        'success': False,
        'uploaded_to': upload_channel_peer_id_b64,
        'file_id': None,
        'sent_to': [],
        'errors': []
    }
    
    try:
        send_method = {
            'photo': client.send_photo,
            'audio': client.send_audio,
            'video': client.send_video
        }.get(file_type)
        
        if not send_method:
            return {'success': False, 'error': f'Unknown file type: {file_type}'}
        
        # שלב 1: העלאה לערוץ הראשון
        logger.info(f"📤 [TELEGRAM] Uploading {file_type} to first channel: {upload_channel_peer_id_b64[:20]}...")
        
        # פענוח peer_id - ננסה גם peer_id_b64 וגם ID רגיל
        peer_id = None
        legacy_id = None
        
        try:
            peer_id = decode_peer_id(upload_channel_peer_id_b64)
            # אם זה ID רגיל (int), נשמור אותו גם כ-legacy_id
            if isinstance(peer_id, int):
                legacy_id = peer_id
                logger.debug(f"📊 [TELEGRAM] Using regular channel ID: {peer_id}")
            else:
                logger.debug(f"📊 [TELEGRAM] Using peer_id (bytes/str): {type(peer_id).__name__}")
                # ננסה לחלץ legacy_id מהמאגר או מהמחרוזת המקורית
                # קודם ננסה מהמאגר
                try:
                    from services.channels import channels_manager
                    repository = channels_manager.get_repository("telegram")
                    for item in repository:
                        if isinstance(item, dict) and item.get("peer_id_b64") == upload_channel_peer_id_b64:
                            if item.get("legacy_id"):
                                legacy_id = int(item["legacy_id"])
                                logger.debug(f"📊 [TELEGRAM] Found legacy_id from repository: {legacy_id}")
                                break
                except Exception as e:
                    logger.debug(f"⚠️ [TELEGRAM] Could not get legacy_id from repository: {e}")
                
                # אם לא מצאנו במאגר, ננסה מהמחרוזת המקורית
                if legacy_id is None:
                    if upload_channel_peer_id_b64.startswith('-') or upload_channel_peer_id_b64.lstrip('-').isdigit():
                        try:
                            legacy_id = int(upload_channel_peer_id_b64)
                            logger.debug(f"📊 [TELEGRAM] Extracted legacy_id from string: {legacy_id}")
                        except ValueError:
                            pass
        except Exception as e:
            error_msg = f"Failed to decode peer_id: {e}"
            logger.error(f"❌ [TELEGRAM] {error_msg}")
            results['errors'].append(error_msg)
            return results
        
        # בניית פרמטרים - נשתמש ב-legacy_id אם יש (למניעת שגיאות השוואה)
        if legacy_id is not None:
            params = {
                'chat_id': legacy_id,  # שימוש ב-ID רגיל (int) - עדיף
                file_type: file_path
            }
        else:
            params = {
                'chat_id': peer_id,  # שימוש ב-peer_id (bytes, int או str)
                file_type: file_path
            }
        
        # הוספת caption רק אם הוא לא ריק
        if caption and caption.strip():
            params['caption'] = caption
            logger.debug(f"📝 Adding caption to {file_type} ({len(caption)} characters)")
        else:
            logger.warning(f"⚠️ Caption is empty or None for {file_type} - sending without caption")
        
        params.update(kwargs)
        
        # שליחה והעלאה - ננסה גם peer_id_b64 וגם ID רגיל
        logger.info(f"📤 [TELEGRAM] Sending {file_type} to channel (peer_id_b64: {upload_channel_peer_id_b64[:20]}...)")
        sent_message = None
        upload_successful = False
        
        try:
            sent_message: Message = await send_method(**params)
            upload_successful = True
            logger.info(f"✅ [TELEGRAM] Successfully sent using primary method")
        except Exception as upload_error:
            error_msg = f"Failed to upload to channel: {upload_error}"
            logger.warning(f"⚠️ [TELEGRAM] Primary method failed: {upload_error}")
            
            # אם נכשל עם legacy_id, ננסה עם resolve_peer (אם זה bytes)
            if legacy_id is not None and isinstance(peer_id, bytes):
                try:
                    logger.info(f"🔄 [TELEGRAM] Trying with resolve_peer (after legacy_id failed)")
                    # שימוש ב-resolve_peer להמרת bytes ל-peer object
                    from pyrogram import raw
                    resolved_peer = await client.resolve_peer(peer_id)
                    # resolve_peer מחזיר InputPeerChannel - נשתמש ב-ID שלו
                    if isinstance(resolved_peer, raw.types.InputPeerChannel):
                        # ננסה להשתמש ב-ID דרך get_chat עם ה-ID הרגיל
                        try:
                            # נשתמש ב-ID הרגיל מהמאגר או מהמחרוזת המקורית
                            chat_id_to_use = legacy_id  # כבר יש לנו את זה
                            chat = await client.get_chat(chat_id_to_use)
                            params['chat_id'] = chat.id
                            sent_message: Message = await send_method(**params)
                            upload_successful = True
                            logger.info(f"✅ [TELEGRAM] Successfully sent using resolve_peer + get_chat")
                        except Exception as get_chat_error:
                            logger.warning(f"⚠️ [TELEGRAM] get_chat after resolve_peer failed: {get_chat_error}")
                    else:
                        logger.warning(f"⚠️ [TELEGRAM] Unexpected peer type from resolve_peer: {type(resolved_peer)}")
                except Exception as resolve_error:
                    logger.warning(f"⚠️ [TELEGRAM] resolve_peer failed: {resolve_error}")
            # אם נכשל עם bytes, ננסה עם legacy_id (אם יש)
            elif isinstance(peer_id, bytes) and legacy_id is None:
                # ננסה לחלץ legacy_id מה-channel_id אם אפשר
                if upload_channel_peer_id_b64.startswith('-') or upload_channel_peer_id_b64.lstrip('-').isdigit():
                    try:
                        legacy_id = int(upload_channel_peer_id_b64)
                        logger.info(f"🔄 [TELEGRAM] Trying with legacy ID: {legacy_id}")
                        params['chat_id'] = legacy_id
                        sent_message: Message = await send_method(**params)
                        upload_successful = True
                        logger.info(f"✅ [TELEGRAM] Successfully sent using legacy ID")
                    except Exception as legacy_error:
                        logger.warning(f"⚠️ [TELEGRAM] Legacy ID also failed: {legacy_error}")
            
            # אם עדיין נכשל, ננסה את הערוץ הראשון ברשימה
            if not upload_successful and first_channel_peer_id_b64 and upload_channel_peer_id_b64 == first_channel_peer_id_b64 and channels:
                fallback_channel = channels[0]
                if fallback_channel != upload_channel_peer_id_b64:
                    logger.info(f"🔄 [TELEGRAM] Trying fallback channel: {fallback_channel[:20]}...")
                    try:
                        fallback_peer_id = decode_peer_id(fallback_channel)
                        params['chat_id'] = fallback_peer_id
                        sent_message: Message = await send_method(**params)
                        upload_channel_peer_id_b64 = fallback_channel
                        results['uploaded_to'] = upload_channel_peer_id_b64
                        # השוואה בטוחה בין ערוצים - ממירים למחרוזת כדי למנוע שגיאות השוואה
                        other_channels = [ch for ch in channels if str(ch) != str(upload_channel_peer_id_b64)]
                        upload_successful = True
                        logger.info(f"✅ [TELEGRAM] Successfully uploaded to fallback channel")
                    except Exception as fallback_error:
                        logger.error(f"❌ [TELEGRAM] Fallback channel also failed: {fallback_error}")
                        results['errors'].append(f"Fallback also failed: {fallback_error}")
            
            if not upload_successful:
                # ננסה לטעון את הערוץ ל-storage לפני שנכשל סופית
                if legacy_id is not None:
                    try:
                        logger.info(f"🔄 [TELEGRAM] Attempting to load channel to storage: {legacy_id}")
                        chat = await client.get_chat(legacy_id)
                        logger.info(f"✅ [TELEGRAM] Channel loaded to storage: {chat.title if hasattr(chat, 'title') else 'N/A'}")
                        # ננסה שוב עם ה-ID הרגיל אחרי שהערוץ נטען
                        params['chat_id'] = legacy_id
                        sent_message: Message = await send_method(**params)
                        upload_successful = True
                        logger.info(f"✅ [TELEGRAM] Successfully sent after loading channel to storage")
                    except PeerIdInvalid:
                        logger.error(f"❌ [TELEGRAM] Channel {legacy_id} is not accessible (PeerIdInvalid)")
                        logger.error(f"💡 [TELEGRAM] פתרון: שלח הודעה מה-userbot לערוץ {legacy_id} כדי לטעון אותו ל-storage")
                        logger.error(f"💡 [TELEGRAM] או וודא שה-userbot חבר בערוץ {legacy_id}")
                    except Exception as load_error:
                        logger.warning(f"⚠️ [TELEGRAM] Failed to load channel to storage: {load_error}")
                
                if not upload_successful:
                    error_msg = f"Failed to upload to channel: {upload_error}"
                    logger.error(f"❌ [TELEGRAM] {error_msg}")
                    results['errors'].append(error_msg)
                    
                    # הודעה ברורה יותר אם זה ערוץ מוגן
                    if protected_channels and upload_channel_peer_id_b64 in protected_channels:
                        logger.error(f"⚠️ [TELEGRAM] הערוץ הקבוע לא נגיש. ודא שהיוזרבוט חבר בערוץ ובעל הרשאות פרסום.")
                    
                    return results
        
        if not sent_message:
            return {'success': False, 'error': 'Failed to send message'}
        
        # חילוץ file_id
        if file_type == 'photo' and sent_message.photo:
            file_id = sent_message.photo.file_id
        elif file_type == 'audio' and sent_message.audio:
            file_id = sent_message.audio.file_id
        elif file_type == 'video' and sent_message.video:
            file_id = sent_message.video.file_id
        else:
            return {'success': False, 'error': 'Could not extract file_id from sent message'}
        
        results['file_id'] = file_id
        results['sent_to'].append(upload_channel_peer_id_b64)
        logger.info(f"✅ [TELEGRAM] Uploaded to channel, file_id: {file_id[:20]}...")
        
        # שלב 2: שליחה לשאר הערוצים עם file_id
        if other_channels:
            logger.info(f"📤 [TELEGRAM] Sending to {len(other_channels)} additional channels using file_id")
            
            for channel_peer_id_b64 in other_channels:
                try:
                    # פענוח peer_id - ננסה גם peer_id_b64 וגם ID רגיל
                    peer_id = decode_peer_id(channel_peer_id_b64)
                    legacy_id = None
                    
                    # אם זה ID רגיל, נשמור אותו
                    if isinstance(peer_id, int):
                        legacy_id = peer_id
                    # אם זה bytes, ננסה לחלץ ID רגיל מהמחרוזת המקורית
                    elif isinstance(peer_id, bytes):
                        # ננסה לחלץ ID רגיל מהמחרוזת המקורית אם אפשר
                        if channel_peer_id_b64.startswith('-') or channel_peer_id_b64.lstrip('-').isdigit():
                            try:
                                legacy_id = int(channel_peer_id_b64)
                                logger.debug(f"📊 [TELEGRAM] Extracted legacy ID from bytes peer_id: {legacy_id}")
                            except ValueError:
                                pass
                    
                    # ננסה קודם עם ID רגיל אם יש (למניעת שגיאות השוואה)
                    if legacy_id is not None:
                        params = {
                            'chat_id': legacy_id,  # שימוש ב-ID רגיל (int)
                            file_type: file_id  # שימוש ב-file_id במקום נתיב
                        }
                    else:
                        params = {
                            'chat_id': peer_id,  # שימוש ב-peer_id (bytes, int או str)
                            file_type: file_id  # שימוש ב-file_id במקום נתיב
                        }
                    
                    # הוספת caption רק אם הוא לא ריק
                    if caption and caption.strip():
                        params['caption'] = caption
                        logger.debug(f"📝 Adding caption to {file_type} using file_id ({len(caption)} characters)")
                    else:
                        logger.warning(f"⚠️ Caption is empty or None for {file_type} - sending without caption")
                    
                    params.update(kwargs)
                    
                    # ננסה לשלוח - אם נכשל, ננסה עם peer_id המקורי
                    try:
                        await send_method(**params)
                        results['sent_to'].append(channel_peer_id_b64)
                        logger.info(f"✅ [TELEGRAM] Sent to channel (peer_id_b64: {channel_peer_id_b64[:20]}...) using file_id")
                    except Exception as send_error:
                        # אם נכשל עם ID רגיל, ננסה עם peer_id המקורי (bytes)
                        if legacy_id is not None and isinstance(peer_id, bytes):
                            try:
                                logger.info(f"🔄 [TELEGRAM] Trying with bytes peer_id for channel")
                                params['chat_id'] = peer_id
                                await send_method(**params)
                                results['sent_to'].append(channel_peer_id_b64)
                                logger.info(f"✅ [TELEGRAM] Sent to channel using bytes peer_id")
                            except Exception as bytes_error:
                                raise send_error  # נזרוק את השגיאה המקורית
                        else:
                            raise send_error
                    
                except Exception as e:
                    error_msg = f"Failed to send to channel: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(f"❌ [TELEGRAM] {error_msg}")
        
        results['success'] = True
        logger.info(f"✅ [TELEGRAM] Successfully sent to {len(results['sent_to'])} channels")
        
    except Exception as e:
        error_msg = f"Failed to upload to first channel: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(f"❌ [TELEGRAM] {error_msg}", exc_info=True)
        results['success'] = False
    
    return results


async def send_to_whatsapp_groups(
    whatsapp_delivery,
    file_path: str,
    file_type: str,  # 'image', 'audio', 'video'
    caption: str,
    groups: List[str],  # רשימת קבוצות
    telegram_user_id: Optional[int] = None,
    telegram_fallback_callback = None,
    session = None  # session object למילוי תבנית status אם נדרש
) -> Dict[str, any]:
    """
    שליחה לוואטסאפ - העלאה מחדש לכל קבוצה (כדי להימנע מ-"Forwarded")
    
    Args:
        whatsapp_delivery: WhatsAppDelivery instance
        file_path: נתיב הקובץ המקומי
        file_type: סוג הקובץ ('image', 'audio', 'video')
        caption: כותרת להודעה
        groups: רשימת קבוצות לשליחה
        telegram_user_id: מזהה משתמש טלגרם (לצורך fallback)
        telegram_fallback_callback: callback function לטלגרם fallback
        session: session object למילוי תבנית status אם נדרש
    
    Returns:
        מילון עם תוצאות: {'success': bool, 'sent_to': List[str], 'errors': List[str]}
    """
    if not groups:
        return {'success': False, 'error': 'No groups provided'}
    
    results = {
        'success': False,
        'sent_to': [],
        'errors': []
    }
    
    logger.info(f"📱 [WHATSAPP] Sending {file_type} to {len(groups)} groups (re-uploading for each)")
    
    # הערה: אם רוצים לחסוך bandwidth, אפשר להשתמש ב-msg.forward(chatId)
    # אבל זה יוסיף את הסימון "Forwarded"
    
    import asyncio
    loop = asyncio.get_event_loop()
    
    from services.templates import template_manager
    
    for group in groups:
        try:
            logger.info(f"📤 [WHATSAPP] Sending to group: {group}")
            
            # בדיקה אם זה "הסטטוס שלי" - אם כן, נשתמש בתבנית whatsapp_status
            current_caption = caption
            if group == "הסטטוס שלי" and session:
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
                    # נמשיך עם התבנית הרגילה
            
            # send_file היא sync, אז נריץ אותה ב-executor
            result = await loop.run_in_executor(
                None,
                whatsapp_delivery.send_file,
                file_path,
                group,
                current_caption,
                file_type,
                telegram_user_id,
                telegram_fallback_callback
            )
            
            if result.get('success'):
                results['sent_to'].append(group)
                logger.info(f"✅ [WHATSAPP] Successfully sent to {group}")
            else:
                error_msg = f"Failed to send to {group}: {result.get('error', 'Unknown error')}"
                results['errors'].append(error_msg)
                logger.error(f"❌ [WHATSAPP] {error_msg}")
                
        except Exception as e:
            error_msg = f"Failed to send to {group}: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(f"❌ [WHATSAPP] {error_msg}", exc_info=True)
    
    results['success'] = len(results['sent_to']) > 0
    
    if results['success']:
        logger.info(f"✅ [WHATSAPP] Successfully sent to {len(results['sent_to'])}/{len(groups)} groups")
    else:
        logger.error(f"❌ [WHATSAPP] Failed to send to any group")
    
    return results
