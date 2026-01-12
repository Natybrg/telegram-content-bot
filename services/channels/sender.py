"""
Smart Channel Sender
שליחה חכמה לערוצים/קבוצות עם אופטימיזציה
"""

import logging
from typing import List, Dict, Optional, Tuple
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid, ChannelInvalid, UsernameInvalid
from services.templates import template_manager

logger = logging.getLogger(__name__)


async def validate_channel_access(client: Client, channel_id: str) -> bool:
    """
    בודק אם הערוץ נגיש לפני שליחה
    מנסה לטעון את הערוץ ל-storage אם הוא לא נמצא
    
    Args:
        client: Pyrogram Client
        channel_id: מזהה הערוץ (ID או username)
    
    Returns:
        True אם הערוץ נגיש, False אחרת
    """
    try:
        # ניסיון לפתור את ה-peer - אם זה נכשל, הערוץ לא נגיש
        chat_id = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
        
        # ניסיון ראשון - קריאה רגילה
        try:
            await client.get_chat(chat_id)
            return True
        except (PeerIdInvalid, ValueError) as e:
            # אם זה PeerIdInvalid, ננסה לטעון את הערוץ ל-storage
            error_str = str(e)
            if "Peer id invalid" in error_str or "ID not found" in error_str:
                logger.info(f"🔄 [TELEGRAM] Peer not in storage, trying to load: {channel_id}")
                logger.info(f"💡 [TELEGRAM] Tip: Make sure the userbot is a member of the channel and has sent at least one message to it")
                try:
                    # ניסיון לטעון את הערוץ ל-storage על ידי קריאה ל-get_chat שוב
                    # לפעמים צריך לנסות עם int/str שונים
                    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
                        # ננסה עם int
                        chat_id_int = int(chat_id)
                        chat_obj = await client.get_chat(chat_id_int)
                        logger.info(f"✅ [TELEGRAM] Successfully loaded peer to storage: {channel_id} (title: {chat_obj.title if hasattr(chat_obj, 'title') else 'N/A'})")
                        return True
                    elif isinstance(chat_id, int):
                        # ננסה עם str
                        chat_id_str = str(chat_id)
                        chat_obj = await client.get_chat(chat_id_str)
                        logger.info(f"✅ [TELEGRAM] Successfully loaded peer to storage: {channel_id} (title: {chat_obj.title if hasattr(chat_obj, 'title') else 'N/A'})")
                        return True
                except Exception as load_error:
                    logger.warning(f"⚠️ [TELEGRAM] Failed to load peer to storage: {load_error}")
                    logger.warning(f"💡 [TELEGRAM] Solution: Send a message to channel {channel_id} from the userbot to load it to storage")
                    # נמשיך עם השגיאה המקורית
                    pass
            
            logger.warning(f"⚠️ [TELEGRAM] Channel {channel_id} is not accessible: {e}")
            return False
        except (ChannelInvalid, UsernameInvalid) as e:
            logger.warning(f"⚠️ [TELEGRAM] Channel {channel_id} is not accessible: {e}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ [TELEGRAM] Error validating channel {channel_id}: {e}")
        return False


async def filter_valid_channels(client: Client, channels: List[str], protected_channels: Optional[List[str]] = None) -> List[str]:
    """
    מסנן ערוצים לא תקינים מהרשימה
    
    Args:
        client: Pyrogram Client
        channels: רשימת ערוצים
        protected_channels: רשימת ערוצים מוגנים שלא יוסרו גם אם הבדיקה נכשלת (למשל ערוצים קבועים)
    
    Returns:
        רשימת ערוצים תקינים + ערוצים מוגנים
    """
    if protected_channels is None:
        protected_channels = []
    
    valid_channels = []
    for channel in channels:
        if channel in protected_channels:
            # ערוץ מוגן - מוסיפים אותו תמיד, גם אם הבדיקה נכשלת
            valid_channels.append(channel)
            logger.debug(f"🛡️ [TELEGRAM] Protected channel added: {channel}")
        elif await validate_channel_access(client, channel):
            valid_channels.append(channel)
        else:
            logger.warning(f"⚠️ [TELEGRAM] Removing invalid channel from list: {channel}")
    return valid_channels


async def send_to_telegram_channels(
    client: Client,
    file_path: str,
    file_type: str,  # 'photo', 'audio', 'video'
    caption: str,
    channels: List[str],  # רשימת ערוצים (ID או username)
    first_channel_id: Optional[str] = None,  # ערוץ ראשון להעלאה (או LOG_CHANNEL_ID)
    protected_channels: Optional[List[str]] = None,  # ערוצים מוגנים שלא יוסרו גם אם הבדיקה נכשלת
    **kwargs  # פרמטרים נוספים (title, performer, duration, thumb, width, height)
) -> Dict[str, any]:
    """
    שליחה חכמה לטלגרם - העלאה פעם אחת, שימוש ב-file_id לשאר
    
    Args:
        client: Pyrogram Client
        file_path: נתיב הקובץ המקומי
        file_type: סוג הקובץ ('photo', 'audio', 'video')
        caption: כותרת להודעה
        channels: רשימת ערוצים לשליחה
        first_channel_id: ערוץ ראשון להעלאה (אם None, משתמש בערוץ הראשון ברשימה)
        **kwargs: פרמטרים נוספים (title, performer, duration, thumb, width, height)
    
    Returns:
        מילון עם תוצאות: {'success': bool, 'uploaded_to': str, 'file_id': str, 'sent_to': List[str], 'errors': List[str]}
    """
    if not channels:
        return {'success': False, 'error': 'No channels provided'}
    
    # בחירת ערוץ ראשון להעלאה לפני סינון
    # חשוב: הערוץ הראשון ברשימה יועלה תמיד, גם אם יש בעיות
    # זה מבטיח שהערוץ הראשון יועלה כמו באינסטגרם
    upload_channel = None
    if first_channel_id:
        # בדיקה אם first_channel_id תקין
        if await validate_channel_access(client, first_channel_id):
            upload_channel = first_channel_id
            logger.debug(f"🔍 [TELEGRAM] Using first_channel_id: {upload_channel}")
        else:
            logger.warning(f"⚠️ [TELEGRAM] first_channel_id {first_channel_id} is not accessible, using first channel from list")
            upload_channel = channels[0] if channels else None
    else:
        upload_channel = channels[0] if channels else None
        logger.debug(f"🔍 [TELEGRAM] Using first channel from list: {upload_channel}")
    
    # סינון ערוצים לא תקינים (אבל שומרים את הערוץ הראשון גם אם לא תקין)
    logger.info(f"🔍 [TELEGRAM] Validating {len(channels)} channels...")
    # הערוץ הראשון מוגן - לא יוסר גם אם לא תקין
    protected_for_upload = [upload_channel] if upload_channel else []
    if protected_channels:
        protected_for_upload.extend(protected_channels)
    valid_channels = await filter_valid_channels(client, channels, protected_channels=protected_for_upload)
    
    if not valid_channels:
        error_msg = "No valid channels found. Please check that the bot/userbot is a member of all channels."
        logger.error(f"❌ [TELEGRAM] {error_msg}")
        return {'success': False, 'error': error_msg, 'errors': [f"All {len(channels)} channels are invalid or inaccessible"]}
    
    if len(valid_channels) < len(channels):
        logger.warning(f"⚠️ [TELEGRAM] {len(channels) - len(valid_channels)} invalid channels were filtered out")
    
    channels = valid_channels
    
    # וידוא שהערוץ הראשון עדיין ברשימה (אם לא, נוסיף אותו)
    if upload_channel and upload_channel not in channels:
        logger.warning(f"⚠️ [TELEGRAM] First channel {upload_channel} was filtered out, adding it back")
        channels.insert(0, upload_channel)
    
    if not upload_channel:
        return {'success': False, 'error': 'No channel provided for upload'}
    
    other_channels = [ch for ch in channels if ch != upload_channel]
    
    results = {
        'success': False,
        'uploaded_to': upload_channel,
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
        logger.info(f"📤 [TELEGRAM] Uploading {file_type} to first channel: {upload_channel}")
        
        # בניית פרמטרים
        # Pyrogram יכול לקבל גם int וגם str ל-chat_id
        # אם זה ID מספרי, נמיר ל-int (אם אפשר)
        try:
            chat_id = int(upload_channel) if upload_channel.lstrip('-').isdigit() else upload_channel
        except:
            chat_id = upload_channel
        
        # בניית פרמטרים - וידוא שה-caption לא ריק
        params = {
            'chat_id': chat_id,
            file_type: file_path
        }
        
        # הוספת caption רק אם הוא לא ריק
        if caption and caption.strip():
            params['caption'] = caption
            logger.debug(f"📝 Adding caption to {file_type} ({len(caption)} characters)")
        else:
            logger.warning(f"⚠️ Caption is empty or None for {file_type} - sending without caption")
        
        params.update(kwargs)
        
        # שליחה והעלאה - עם fallback אם נכשל
        logger.info(f"📤 [TELEGRAM] Sending {file_type} to channel {chat_id} (type: {type(chat_id).__name__})")
        try:
            sent_message: Message = await send_method(**params)
        except (PeerIdInvalid, ChannelInvalid, UsernameInvalid, ValueError) as upload_error:
            # אם זה PeerIdInvalid או ValueError עם "Peer id invalid", ננסה לטעון את ה-peer ל-storage ואז לשלוח שוב
            is_peer_id_error = (
                isinstance(upload_error, PeerIdInvalid) or 
                (isinstance(upload_error, ValueError) and "Peer id invalid" in str(upload_error))
            )
            if is_peer_id_error:
                logger.warning(f"⚠️ [TELEGRAM] PeerIdInvalid error - trying to load peer to storage and retry...")
                original_chat_id = chat_id
                retry_success = False
                
                # ניסיון 1: עם הערך הנוכחי
                try:
                    logger.info(f"🔍 [TELEGRAM] Loading peer to storage (retry attempt 1): {chat_id} (type: {type(chat_id).__name__})")
                    chat_obj = await client.get_chat(chat_id)
                    logger.info(f"✅ [TELEGRAM] Peer loaded successfully: {chat_obj.title if hasattr(chat_obj, 'title') else chat_id}")
                    # ננסה לשלוח שוב
                    sent_message: Message = await send_method(**params)
                    retry_success = True
                    logger.info(f"✅ [TELEGRAM] Successfully sent after loading peer")
                except Exception as retry_error:
                    logger.warning(f"⚠️ [TELEGRAM] Retry attempt 1 failed: {retry_error}")
                    
                    # ניסיון 2: אם זה str, ננסה עם int
                    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
                        try:
                            chat_id_int = int(chat_id)
                            logger.info(f"🔄 [TELEGRAM] Trying with int (retry attempt 2): {chat_id_int}")
                            chat_obj = await client.get_chat(chat_id_int)
                            params['chat_id'] = chat_id_int
                            chat_id = chat_id_int
                            logger.info(f"✅ [TELEGRAM] Peer loaded successfully with int: {chat_obj.title if hasattr(chat_obj, 'title') else chat_id}")
                            sent_message: Message = await send_method(**params)
                            retry_success = True
                            logger.info(f"✅ [TELEGRAM] Successfully sent after loading peer with int")
                        except Exception as int_error:
                            logger.warning(f"⚠️ [TELEGRAM] Retry attempt 2 (int) failed: {int_error}")
                    
                    # ניסיון 3: אם זה int, ננסה עם str
                    elif isinstance(chat_id, int):
                        try:
                            chat_id_str = str(chat_id)
                            logger.info(f"🔄 [TELEGRAM] Trying with str (retry attempt 3): {chat_id_str}")
                            chat_obj = await client.get_chat(chat_id_str)
                            params['chat_id'] = chat_id_str
                            chat_id = chat_id_str
                            logger.info(f"✅ [TELEGRAM] Peer loaded successfully with str: {chat_obj.title if hasattr(chat_obj, 'title') else chat_id}")
                            sent_message: Message = await send_method(**params)
                            retry_success = True
                            logger.info(f"✅ [TELEGRAM] Successfully sent after loading peer with str")
                        except Exception as str_error:
                            logger.warning(f"⚠️ [TELEGRAM] Retry attempt 3 (str) failed: {str_error}")
                
                if not retry_success:
                    # נכשלנו - נמשיך עם הטיפול הרגיל בשגיאה
                    error_msg = f"Channel {upload_channel} is invalid or inaccessible: {upload_error}"
                    logger.error(f"❌ [TELEGRAM] {error_msg}")
                    # הודעה ברורה יותר אם זה ערוץ מוגן (קבוע)
                    if protected_channels and upload_channel in protected_channels:
                        logger.error(f"⚠️ [TELEGRAM] הערוץ הקבוע {upload_channel} לא נגיש. ודא שהיוזרבוט חבר בערוץ ובעל הרשאות פרסום.")
                    # אם first_channel_id נכשל, ננסה את הערוץ הראשון ברשימה
                    if first_channel_id and upload_channel == first_channel_id and channels:
                        fallback_channel = channels[0]
                        logger.info(f"🔄 [TELEGRAM] Trying fallback channel: {fallback_channel}")
                        if fallback_channel != upload_channel:
                            try:
                                chat_id = int(fallback_channel) if fallback_channel.lstrip('-').isdigit() else fallback_channel
                                params['chat_id'] = chat_id
                                sent_message: Message = await send_method(**params)
                                upload_channel = fallback_channel
                                results['uploaded_to'] = upload_channel
                                other_channels = [ch for ch in channels if ch != upload_channel]
                                logger.info(f"✅ [TELEGRAM] Successfully uploaded to fallback channel: {upload_channel}")
                                retry_success = True  # הצלחנו עם fallback
                            except Exception as fallback_error:
                                logger.error(f"❌ [TELEGRAM] Fallback channel also failed: {fallback_error}")
                                results['errors'].append(error_msg)
                                raise upload_error
                        else:
                            results['errors'].append(error_msg)
                            raise upload_error
                    else:
                        results['errors'].append(error_msg)
                        raise upload_error
                
                # אם retry הצליח, נמשיך עם הקוד הרגיל (חילוץ file_id וכו')
                if retry_success:
                    # נדלג על הטיפול בשגיאה ונמשיך עם הקוד הרגיל
                    pass
            else:
                error_msg = f"Channel {upload_channel} is invalid or inaccessible: {upload_error}"
                logger.error(f"❌ [TELEGRAM] {error_msg}")
                # הודעה ברורה יותר אם זה ערוץ מוגן (קבוע)
                if protected_channels and upload_channel in protected_channels:
                    logger.error(f"⚠️ [TELEGRAM] הערוץ הקבוע {upload_channel} לא נגיש. ודא שהיוזרבוט חבר בערוץ ובעל הרשאות פרסום.")
                # אם first_channel_id נכשל, ננסה את הערוץ הראשון ברשימה
            if first_channel_id and upload_channel == first_channel_id and channels:
                fallback_channel = channels[0]
                logger.info(f"🔄 [TELEGRAM] Trying fallback channel: {fallback_channel}")
                if fallback_channel != upload_channel:
                    try:
                        chat_id = int(fallback_channel) if fallback_channel.lstrip('-').isdigit() else fallback_channel
                        params['chat_id'] = chat_id
                        sent_message: Message = await send_method(**params)
                        upload_channel = fallback_channel
                        results['uploaded_to'] = upload_channel
                        other_channels = [ch for ch in channels if ch != upload_channel]
                        logger.info(f"✅ [TELEGRAM] Successfully uploaded to fallback channel: {upload_channel}")
                    except Exception as fallback_error:
                        logger.error(f"❌ [TELEGRAM] Fallback channel also failed: {fallback_error}")
                        results['errors'].append(error_msg)
                        raise upload_error
                else:
                    results['errors'].append(error_msg)
                    raise upload_error
            else:
                results['errors'].append(error_msg)
                raise upload_error
        except Exception as upload_error:
            error_msg = f"Failed to upload to {upload_channel}: {upload_error}"
            logger.warning(f"⚠️ [TELEGRAM] {error_msg}")
            # הודעה ברורה יותר אם זה ערוץ מוגן (קבוע)
            if protected_channels and upload_channel in protected_channels:
                logger.error(f"⚠️ [TELEGRAM] הערוץ הקבוע {upload_channel} לא נגיש. ודא שהיוזרבוט חבר בערוץ ובעל הרשאות פרסום.")
            # אם first_channel_id נכשל, ננסה את הערוץ הראשון ברשימה
            if first_channel_id and upload_channel == first_channel_id and channels:
                fallback_channel = channels[0]
                logger.info(f"🔄 [TELEGRAM] Trying fallback channel: {fallback_channel}")
                if fallback_channel != upload_channel:
                    try:
                        chat_id = int(fallback_channel) if fallback_channel.lstrip('-').isdigit() else fallback_channel
                        params['chat_id'] = chat_id
                        sent_message: Message = await send_method(**params)
                        upload_channel = fallback_channel
                        results['uploaded_to'] = upload_channel
                        other_channels = [ch for ch in channels if ch != upload_channel]
                        logger.info(f"✅ [TELEGRAM] Successfully uploaded to fallback channel: {upload_channel}")
                    except Exception as fallback_error:
                        logger.error(f"❌ [TELEGRAM] Fallback channel also failed: {fallback_error}")
                        results['errors'].append(error_msg)
                        raise upload_error
                else:
                    results['errors'].append(error_msg)
                    raise upload_error
            else:
                results['errors'].append(error_msg)
                raise upload_error
        
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
        results['sent_to'].append(upload_channel)
        logger.info(f"✅ [TELEGRAM] Uploaded to {upload_channel}, file_id: {file_id[:20]}...")
        
        # שלב 2: שליחה לשאר הערוצים עם file_id
        if other_channels:
            logger.info(f"📤 [TELEGRAM] Sending to {len(other_channels)} additional channels using file_id")
            
            for channel in other_channels:
                try:
                    # Pyrogram יכול לקבל גם int וגם str ל-chat_id
                    try:
                        chat_id = int(channel) if channel.lstrip('-').isdigit() else channel
                    except:
                        chat_id = channel
                    
                    # ניסיון לטעון את ה-peer ל-storage לפני השליחה
                    try:
                        await client.get_chat(chat_id)
                    except Exception:
                        pass  # נמשיך עם השליחה בכל מקרה
                    
                    params = {
                        'chat_id': chat_id,
                        file_type: file_id  # שימוש ב-file_id במקום נתיב
                    }
                    
                    # הוספת caption רק אם הוא לא ריק
                    if caption and caption.strip():
                        params['caption'] = caption
                        logger.debug(f"📝 Adding caption to {file_type} using file_id ({len(caption)} characters)")
                    else:
                        logger.warning(f"⚠️ Caption is empty or None for {file_type} - sending without caption")
                    
                    params.update(kwargs)
                    
                    await send_method(**params)
                    results['sent_to'].append(channel)
                    logger.info(f"✅ [TELEGRAM] Sent to {channel} using file_id")
                    
                except (PeerIdInvalid, ChannelInvalid, UsernameInvalid) as e:
                    error_msg = f"Channel {channel} is invalid or inaccessible: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(f"❌ [TELEGRAM] {error_msg}")
                except Exception as e:
                    error_msg = f"Failed to send to {channel}: {str(e)}"
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

