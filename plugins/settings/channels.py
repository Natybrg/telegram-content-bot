"""
Channel Management Plugin
Handlers for adding, managing, and toggling channels/groups
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.channels import channels_manager
from services.user_states import state_manager, UserState
from services.rate_limiter import rate_limit
from core import is_authorized_user
import logging

logger = logging.getLogger(__name__)


# מיפוי שמות תבניות לשמות תצוגה (לשימוש ב-toggle)
TEMPLATE_NAMES = {
    "telegram_image": "📤 תמונה טלגרם",
    "telegram_audio": "🎵 MP3 טלגרם",
    "telegram_video": "🎬 וידאו טלגרם",
    "whatsapp_image": "📱 תמונה וואטסאפ",
    "whatsapp_audio": "🎵 MP3 וואטסאפ",
    "whatsapp_video": "🎬 וידאו וואטסאפ",
    "telegram_instagram": "📱 אינסטגרם טלגרם",
    "whatsapp_instagram": "📱 אינסטגרם וואטסאפ",
    "whatsapp_status": "📱 סטטוס וואטסאפ"
}


async def get_channel_display_name(client: Client, platform: str, channel_ref: str) -> str:
    """
    מחזיר שם תצוגה לערוץ/קבוצה - תמיד מנסה להחזיר שם, לא ID/peer_id_b64
    
    Args:
        client: Pyrogram Client
        platform: 'telegram' או 'whatsapp'
        channel_ref: peer_id_b64 (עבור telegram) או שם קבוצה (עבור whatsapp) או ID ישן
    
    Returns:
        שם תצוגה (שם הערוץ - תמיד, לא ID/peer_id_b64)
    """
    if platform == "telegram":
        # קודם נבדוק במאגר - אולי יש שם שם
        from services.channels import channels_manager
        repository = channels_manager.get_repository("telegram")
        for item in repository:
            if isinstance(item, dict):
                if item.get("peer_id_b64") == channel_ref or item.get("legacy_id") == channel_ref:
                    stored_title = item.get("title")
                    if stored_title and stored_title != "Unknown Channel":
                        return stored_title
        
        # אם לא נמצא במאגר, ננסה לקבל מה-API
        try:
            # בדיקה אם זה peer_id_b64 (Base64 string ארוך)
            import base64
            if len(channel_ref) > 20 and not channel_ref.lstrip('-').isdigit():
                # זה נראה כמו Base64 - נפענח אותו
                try:
                    peer_id_bytes = base64.b64decode(channel_ref.encode("utf-8"))
                    chat = await client.get_chat(peer_id_bytes)
                    if chat.title:
                        return chat.title
                except:
                    pass
            
            # ניסיון עם ID/username רגיל (backward compatibility)
            chat_id = int(channel_ref) if channel_ref.lstrip('-').isdigit() else channel_ref
            chat = await client.get_chat(chat_id)
            # החזרת שם הערוץ (title) אם קיים
            if chat.title:
                return chat.title
        except Exception as e:
            logger.debug(f"⚠️ Could not get channel name for {channel_ref[:20] if len(channel_ref) > 20 else channel_ref}: {e}")
            # אם נכשל, נחזיר "ערוץ לא ידוע" במקום ID
            return "ערוץ לא ידוע"
    
    # אם זה WhatsApp, נחזיר את השם המקורי (כי זה כבר שם קבוצה)
    return channel_ref


@Client.on_callback_query(filters.regex("^add_channels$"))
@rate_limit(max_requests=50, window=60)
async def add_channels_menu(client: Client, query: CallbackQuery):
    """תפריט הוספת ערוצים/קבוצות"""
    logger.info(f"📋 User {query.from_user.id} opened add channels menu")
    
    # קבלת רשימת ערוצים/קבוצות קיימים
    telegram_channels = channels_manager.get_repository("telegram")
    whatsapp_groups = channels_manager.get_repository("whatsapp")
    logger.debug(f"📊 Repository: {len(telegram_channels)} Telegram, {len(whatsapp_groups)} WhatsApp")
    
    keyboard = [
        [InlineKeyboardButton("📱 טלגרם", callback_data="add_channel_telegram")],
        [InlineKeyboardButton("💬 וואטסאפ", callback_data="add_channel_whatsapp")],
    ]
    
    # הוספת כפתורים לערוצים/קבוצות קיימים (להסרה)
    if telegram_channels:
        keyboard.append([InlineKeyboardButton("📋 ניהול ערוצי טלגרם", callback_data="manage_channels_telegram")])
    if whatsapp_groups:
        keyboard.append([InlineKeyboardButton("📋 ניהול קבוצות וואטסאפ", callback_data="manage_channels_whatsapp")])
    
    keyboard.append([InlineKeyboardButton("🔙 חזור", callback_data="back_to_settings")])
    
    text = "➕ **הוספת ערוצים/קבוצות**\n\n"
    text += f"**ערוצי טלגרם במאגר:** {len(telegram_channels)}\n"
    if telegram_channels:
        # קבלת שמות ערוצים
        channel_names = []
        for ch_item in telegram_channels[:5]:
            try:
                # עבור פורמט חדש (dict עם peer_id_b64 ו-title)
                if isinstance(ch_item, dict):
                    display_name = ch_item.get("title", "Unknown Channel")
                    peer_id_b64 = ch_item.get("peer_id_b64")
                    if peer_id_b64:
                        # ננסה לקבל שם עדכני מה-API
                        try:
                            display_name = await get_channel_display_name(client, "telegram", peer_id_b64)
                        except:
                            pass  # נשתמש ב-title מהמאגר
                else:
                    # פורמט ישן (string) - backward compatibility
                    display_name = await get_channel_display_name(client, "telegram", ch_item)
                
                if len(display_name) > 30:
                    display_name = display_name[:30] + "..."
                channel_names.append(f"`{display_name}`")
            except Exception as e:
                logger.debug(f"⚠️ Could not get channel name: {e}")
                # Fallback - נשתמש ב-title או peer_id_b64
                if isinstance(ch_item, dict):
                    display_name = ch_item.get("title", ch_item.get("peer_id_b64", "Unknown")[:20] + "...")
                else:
                    display_name = str(ch_item)[:30] + "..." if len(str(ch_item)) > 30 else str(ch_item)
                channel_names.append(f"`{display_name}`")
        text += "ערוצים: " + ", ".join(channel_names)
        if len(telegram_channels) > 5:
            text += f" +{len(telegram_channels) - 5} נוספים"
        text += "\n"
    text += f"\n**קבוצות וואטסאפ במאגר:** {len(whatsapp_groups)}\n"
    if whatsapp_groups:
        # קבלת שמות קבוצות - תמיכה גם ב-dicts (מיגרציה)
        group_names = []
        for g_item in whatsapp_groups[:5]:
            try:
                # עבור פורמט חדש (dict) - backward compatibility
                if isinstance(g_item, dict):
                    display_name = g_item.get("title", g_item.get("peer_id_b64", "Unknown Group"))
                else:
                    # פורמט ישן (string) - שם הקבוצה
                    display_name = str(g_item)
                
                if len(display_name) > 30:
                    display_name = display_name[:30] + "..."
                group_names.append(f"`{display_name}`")
            except Exception as e:
                logger.debug(f"⚠️ Could not get group name: {e}")
                # Fallback
                if isinstance(g_item, dict):
                    display_name = g_item.get("title", g_item.get("peer_id_b64", "Unknown")[:20] + "...")
                else:
                    display_name = str(g_item)[:30] + "..." if len(str(g_item)) > 30 else str(g_item)
                group_names.append(f"`{display_name}`")
        text += "קבוצות: " + ", ".join(group_names)
        if len(whatsapp_groups) > 5:
            text += f" +{len(whatsapp_groups) - 5} נוספים"
        text += "\n"
    text += "\nבחר פעולה:"
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()
    logger.debug(f"✅ Add channels menu displayed to user {query.from_user.id}")


@Client.on_callback_query(filters.regex("^add_channel_(telegram|whatsapp)$"))
async def add_channel_prompt(client: Client, query: CallbackQuery):
    """הנחיה להוספת ערוץ/קבוצה"""
    platform = query.data.replace("add_channel_", "")
    logger.info(f"➕ User {query.from_user.id} starting to add {platform} channel/group")
    
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.ADDING_CHANNEL)
    session.adding_channel_platform = platform
    logger.debug(f"📝 User {query.from_user.id} state changed to ADDING_CHANNEL for {platform}")
    
    if platform == "telegram":
        help_text = (
            "📱 **הוספת ערוץ טלגרם**\n\n"
            "**שלב 1:** העבר הודעה מהערוץ אל הבוט הזה\n\n"
            "**איך לעשות זאת:**\n"
            "1. פתח את הערוץ בטלגרם\n"
            "2. בחר הודעה כלשהי מהערוץ\n"
            "3. לחץ על 'העבר' (Forward)\n"
            "4. בחר את הבוט הזה (הצ'אט הפרטי עם הבוט)\n"
            "5. שלח את ההודעה\n\n"
            "📤 **העבר הודעה מהערוץ אל הבוט עכשיו:**\n\n"
            "💡 **למה?** זה יטען את הערוץ ל-storage ויאפשר לבדוק שהכל תקין."
        )
    else:  # whatsapp
        help_text = (
            "💬 **הוספת קבוצת וואטסאפ**\n\n"
            "שלח את שם הקבוצה בדיוק כפי שהוא מופיע בוואטסאפ.\n\n"
            "**חשוב:**\n"
            "• שם הקבוצה חייב להתאים בדיוק\n"
            "• כולל אימוג'ים, מספרים ורווחים\n\n"
            "📤 **שלח את שם הקבוצה עכשיו:**"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור", callback_data="add_channels")]
    ])
    
    await query.message.edit_text(help_text, reply_markup=keyboard)
    await query.answer()


@Client.on_callback_query(filters.regex("^cancel_add_channel$"))
async def cancel_add_channel(client: Client, query: CallbackQuery):
    """ביטול הוספת ערוץ/קבוצה (legacy - לא בשימוש יותר, חזור משתמש ב-add_channels)"""
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.IDLE)
    if hasattr(session, 'adding_channel_platform'):
        delattr(session, 'adding_channel_platform')
    
    # חזרה לתפריט הוספת ערוצים/קבוצות
    await add_channels_menu(client, query)


@Client.on_message(filters.forwarded & filters.private, group=-3)
@rate_limit(max_requests=50, window=60)
async def handle_forwarded_channel_message(client: Client, message: Message):
    """מטפל בהודעות מועברות מהערוץ - group=-3 נותן עדיפות גבוהה מאוד"""
    user = message.from_user
    
    logger.info(f"📨 [FORWARDED] Received forwarded message from user {user.id}")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.debug(f"⛔ User {user.id} not authorized, skipping forwarded handler")
        return
    
    session = state_manager.get_session(user.id)
    logger.info(f"📊 [FORWARDED] User {user.id} state: {session.state}")
    
    # בדיקה אם המשתמש במצב הוספת ערוץ טלגרם
    if session.state != UserState.ADDING_CHANNEL:
        logger.debug(f"ℹ️ User {user.id} not in ADDING_CHANNEL state (current: {session.state}), skipping forwarded handler")
        return
    
    if not hasattr(session, 'adding_channel_platform'):
        logger.debug(f"ℹ️ User {user.id} has no adding_channel_platform attribute, skipping")
        return
    
    if session.adding_channel_platform != "telegram":
        logger.debug(f"ℹ️ User {user.id} not adding telegram channel (platform: {session.adding_channel_platform}), skipping")
        return
    
    logger.info(f"✅ [ADD_CHANNEL] User {user.id} forwarded message from channel - processing...")
    
    # תגובה מיידית למשתמש
    processing_msg = await message.reply_text("⏳ **מעבד הודעה מועברת...**")
    
    try:
        from core.context import get_context
        from pyrogram.errors import PeerIdInvalid, ChatAdminRequired
        
        # קבלת userbot
        context = get_context()
        userbot = context.get_userbot()
        
        if not userbot:
            await processing_msg.edit_text(
                "❌ **Userbot לא זמין!**\n\n"
                "אין אפשרות לבדוק את הערוץ.",
            )
            return
        
        # קבלת פרטי הערוץ מההודעה המועברת
        logger.debug(f"🔍 [ADD_CHANNEL] Message details: forward_from_chat={message.forward_from_chat}, forward_from={message.forward_from}")
        
        if not message.forward_from_chat:
            logger.warning(f"⚠️ [ADD_CHANNEL] No forward_from_chat in message - cannot identify channel")
            await processing_msg.edit_text(
                "⚠️ **שגיאה:** לא ניתן לזהות את הערוץ מההודעה המועברת.\n\n"
                "**אפשרויות:**\n"
                "• נסה להעביר הודעה אחרת מהערוץ\n"
                "• ודא שהערוץ לא פרטי מדי (privacy settings)\n"
                "• נסה להעביר הודעה ציבורית מהערוץ\n\n"
                "💡 **טיפ:** נסה להעביר הודעה שפורסמה לאחרונה בערוץ"
            )
            return
        
        channel_chat = message.forward_from_chat
        # חילוץ ID - וידוא שזה מספר שלם
        raw_channel_id = channel_chat.id
        channel_id = str(raw_channel_id)
        channel_title = channel_chat.title or channel_id
        
        # לוג מפורט לבדיקה
        logger.info(f"📊 [ADD_CHANNEL] Channel from forwarded message: {channel_title}")
        logger.info(f"📊 [ADD_CHANNEL] Raw channel ID (int): {raw_channel_id}")
        logger.info(f"📊 [ADD_CHANNEL] Channel ID (str): {channel_id}")
        logger.info(f"📊 [ADD_CHANNEL] Channel ID length: {len(channel_id)}")
        
        # וידוא שה-ID תקין (לא נוספו ספרות)
        if len(channel_id) > 20:  # ערוצים פרטיים הם בדרך כלל 13-15 ספרות (כולל המינוס)
            logger.warning(f"⚠️ [ADD_CHANNEL] Channel ID seems too long: {channel_id} (length: {len(channel_id)})")
        
        # יצירת peer_id_b64 - ננסה כמה דרכים
        import base64
        peer_id_b64 = None
        creation_method = None
        
        # ניסיון 1: דרך dialogs (הכי אמין)
        try:
            logger.info(f"🔄 [ADD_CHANNEL] Attempting to get peer_id from dialogs...")
            async for dialog in userbot.get_dialogs():
                if dialog.chat.id == raw_channel_id:
                    chat_obj = dialog.chat
                    if hasattr(chat_obj, 'peer_id'):
                        peer_id_b64 = base64.b64encode(chat_obj.peer_id).decode("utf-8")
                        creation_method = "dialogs"
                        logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from dialogs: {peer_id_b64[:20]}...")
                        break
        except Exception as e:
            logger.debug(f"⚠️ [ADD_CHANNEL] Failed to get from dialogs: {e}")
        
        # ניסיון 2: דרך get_chat עם ID
        if not peer_id_b64:
            try:
                logger.info(f"🔄 [ADD_CHANNEL] Attempting to get peer_id from get_chat with ID...")
                chat_obj = await userbot.get_chat(raw_channel_id)
                if hasattr(chat_obj, 'peer_id'):
                    peer_id_b64 = base64.b64encode(chat_obj.peer_id).decode("utf-8")
                    creation_method = "get_chat"
                    logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from get_chat: {peer_id_b64[:20]}...")
            except Exception as e:
                logger.debug(f"⚠️ [ADD_CHANNEL] Failed to get from get_chat: {e}")
        
        # ניסיון 3: דרך שליחת הודעה זמנית (אם יש הרשאות)
        # אם ההודעה נשלחה בהצלחה, זה אומר שהערוץ זמין!
        message_sent_successfully = False
        if not peer_id_b64:
            try:
                logger.info(f"🔄 [ADD_CHANNEL] Attempting to load peer by sending message to {raw_channel_id}...")
                temp_msg = await userbot.send_message(raw_channel_id, "⏳")
                logger.info(f"✅ [ADD_CHANNEL] Message sent successfully! Message ID: {temp_msg.id}")
                message_sent_successfully = True  # אם ההודעה נשלחה, הערוץ זמין!
                
                # המתנה קצרה כדי לוודא שהערוץ נטען ל-storage
                import asyncio
                await asyncio.sleep(0.5)
                
                # שימוש ב-resolve_peer דרך Pyrogram - הכי אמין!
                logger.info(f"🔄 [ADD_CHANNEL] Extracting peer_id using resolve_peer...")
                try:
                    # שימוש ב-resolve_peer - זה מחזיר את ה-peer_id bytes ישירות
                    from pyrogram import raw
                    peer = await userbot.resolve_peer(raw_channel_id)
                    logger.info(f"📊 [ADD_CHANNEL] Resolved peer type: {type(peer).__name__}")
                    
                    # peer הוא InputPeerChannel או InputPeerChannelFromMessage
                    # נצטרך לחלץ את ה-peer_id bytes
                    if isinstance(peer, raw.types.InputPeerChannel):
                        # יצירת peer_id bytes מ-channel_id ו-access_hash
                        import struct
                        # פורמט peer_id: channel_id (long) + access_hash (long)
                        peer_id_bytes = struct.pack('>qq', peer.channel_id, peer.access_hash)
                        peer_id_b64 = base64.b64encode(peer_id_bytes).decode("utf-8")
                        creation_method = "send_message+resolve_peer"
                        logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from resolve_peer: {peer_id_b64[:20]}...")
                    elif isinstance(peer, raw.types.InputPeerChannelFromMessage):
                        # זה peer מתוך הודעה - נשתמש ב-channel_id ו-access_hash
                        import struct
                        peer_id_bytes = struct.pack('>qq', peer.peer.channel_id, peer.peer.access_hash)
                        peer_id_b64 = base64.b64encode(peer_id_bytes).decode("utf-8")
                        creation_method = "send_message+resolve_peer_from_message"
                        logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from resolve_peer (from message): {peer_id_b64[:20]}...")
                    else:
                        logger.warning(f"⚠️ [ADD_CHANNEL] Unexpected peer type: {type(peer).__name__}")
                        # Fallback - ננסה דרך get_chat
                        logger.info(f"🔄 [ADD_CHANNEL] Trying get_chat as fallback...")
                        chat_obj = await userbot.get_chat(raw_channel_id)
                        if hasattr(chat_obj, 'peer_id'):
                            peer_id_b64 = base64.b64encode(chat_obj.peer_id).decode("utf-8")
                            creation_method = "send_message+get_chat"
                            logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from get_chat: {peer_id_b64[:20]}...")
                except Exception as peer_error:
                    logger.error(f"❌ [ADD_CHANNEL] Failed to extract peer_id via resolve_peer: {peer_error}", exc_info=True)
                    # Fallback אחרון - ננסה דרך get_chat
                    try:
                        logger.info(f"🔄 [ADD_CHANNEL] Trying get_chat as final fallback...")
                        chat_obj = await userbot.get_chat(raw_channel_id)
                        if hasattr(chat_obj, 'peer_id'):
                            peer_id_b64 = base64.b64encode(chat_obj.peer_id).decode("utf-8")
                            creation_method = "send_message+get_chat_fallback"
                            logger.info(f"✅ [ADD_CHANNEL] Created peer_id_b64 from get_chat (fallback): {peer_id_b64[:20]}...")
                    except Exception as get_chat_error:
                        logger.error(f"❌ [ADD_CHANNEL] get_chat also failed: {get_chat_error}")
                
                # מחיקת ההודעה הזמנית
                try:
                    await temp_msg.delete()
                    logger.info(f"✅ [ADD_CHANNEL] Temporary message deleted")
                except Exception as delete_error:
                    logger.warning(f"⚠️ [ADD_CHANNEL] Failed to delete temporary message: {delete_error}")
            except Exception as e:
                logger.error(f"❌ [ADD_CHANNEL] Failed to create peer_id_b64 via send_message: {e}", exc_info=True)
        
        if not peer_id_b64:
            logger.error(f"❌ [ADD_CHANNEL] All methods failed to create peer_id_b64 for channel {channel_id}")
        
        # בדיקות - אם ההודעה נשלחה בהצלחה, זה אומר שהערוץ זמין!
        results = []
        issues_found = []
        solutions = []
        checks_passed = {
            'peer_id_created': peer_id_b64 is not None,
            'message_sent': message_sent_successfully,
            'is_member': False,
            'can_send': False
        }
        
        # בדיקה 1: יצירת peer_id_b64
        results.append("📋 **בדיקה 1:** יצירת peer_id_b64")
        if peer_id_b64:
            results.append(f"✅ **peer_id_b64 נוצר בהצלחה:** `{peer_id_b64[:20]}...`")
            if creation_method:
                results.append(f"   • **שיטה:** {creation_method}")
            results.append("💡 **הערה:** הערוץ נטען ב-storage")
        else:
            results.append("⚠️ **לא ניתן ליצור peer_id_b64**")
            results.append("   • ניסינו: dialogs, get_chat, send_message")
            if not message_sent_successfully:
                issues_found.append("❌ **שגיאה ביצירת peer_id_b64**")
                solutions.append("💡 **פתרון:** ודא שה-userbot חבר בערוץ ובעל הרשאות פרסום")
        
        # בדיקה 2: שליחת הודעה (הכי חשוב - אם נשלחה, הערוץ זמין!)
        results.append("\n📋 **בדיקה 2:** שליחת הודעה")
        if message_sent_successfully:
            results.append("✅ **הודעה נשלחה בהצלחה!**")
            results.append("   • זה אומר שהערוץ זמין וניתן לשלוח אליו ✅")
            checks_passed['can_send'] = True
            checks_passed['is_member'] = True  # אם נשלחה הודעה, זה אומר שהוא חבר
        else:
            results.append("❌ **לא ניתן לשלוח הודעה**")
            if not peer_id_b64:
                results.append("   • לא נוצר peer_id_b64 ולא נשלחה הודעה")
                issues_found.append("❌ **הערוץ לא נגיש**")
                solutions.append("💡 **פתרון:** ודא שה-userbot חבר בערוץ ובעל הרשאות פרסום")
        
        # בדיקה 3: חברות בערוץ (רק אם יש peer_id_b64)
        if peer_id_b64 and not message_sent_successfully:
            results.append("\n📋 **בדיקה 3:** חברות בערוץ")
            try:
                # שימוש ב-peer_id bytes לבדיקת חברות
                peer_id_bytes = base64.b64decode(peer_id_b64.encode("utf-8"))
                member = await userbot.get_chat_member(peer_id_bytes, "me")
                results.append(f"✅ ה-userbot חבר בערוץ")
                results.append(f"   - סטטוס: {member.status.name}")
                checks_passed['is_member'] = True
                if member.status.name in ['ADMINISTRATOR', 'OWNER']:
                    results.append(f"   - הרשאות: מנהל/בעלים ✅")
            except Exception as e:
                results.append(f"⚠️ לא ניתן לבדוק חברות: {str(e)}")
        elif not peer_id_b64:
            results.append("\n📋 **בדיקה 3:** חברות בערוץ")
            results.append("⏭️ דילוג - לא ניתן ליצור peer_id_b64")
        
        # החלטה: האם לשמור את הערוץ?
        # נשמור אם:
        # 1. ההודעה נשלחה בהצלחה (זה אומר שהערוץ זמין!) - או
        # 2. peer_id_b64 נוצר בהצלחה
        should_save = message_sent_successfully or checks_passed['peer_id_created']
        
        # בניית דוח
        report = f"📊 **דוח בדיקת ערוץ:** `{channel_id}`\n\n"
        report += f"**שם הערוץ:** {channel_title}\n\n"
        report += "\n".join(results)
        
        if issues_found:
            report += "\n\n⚠️ **בעיות שנמצאו:**\n"
            report += "\n".join(issues_found)
        
        if solutions:
            report += "\n\n💡 **פתרונות מוצעים:**\n"
            report += "\n".join(solutions)
        
        # החלטה על שמירה
        if should_save:
            # וידוא שיש title תקין - אם לא, ננסה לקבל אותו מה-API
            final_title = channel_title
            if not final_title or final_title == channel_id or final_title == str(raw_channel_id):
                try:
                    # ננסה לקבל שם עדכני מה-API
                    if userbot:
                        chat = await userbot.get_chat(raw_channel_id)
                        if chat.title:
                            final_title = chat.title
                except:
                    pass  # נשתמש ב-channel_title המקורי
            
            # הוספה למאגר - נשמור גם עם peer_id_b64 (אם יש) וגם עם ID רגיל
            if peer_id_b64:
                # שמירה עם peer_id_b64 (עדיף)
                logger.debug(f"💾 Adding telegram channel to repository: {final_title} (peer_id_b64: {peer_id_b64[:20]}...)")
                channels_manager.add_channel("telegram", peer_id_b64, title=final_title, legacy_id=channel_id)
                logger.info(f"✅ Successfully added telegram channel: {final_title} (peer_id_b64: {peer_id_b64[:20]}...)")
            else:
                # שמירה עם ID רגיל (אם ההודעה נשלחה, זה אומר שהערוץ זמין!)
                logger.debug(f"💾 Adding telegram channel to repository: {final_title} (ID: {channel_id})")
                channels_manager.add_channel("telegram", channel_id, title=final_title, legacy_id=channel_id)
                logger.info(f"✅ Successfully added telegram channel: {final_title} (ID: {channel_id})")
            
            if message_sent_successfully:
                report += "\n\n✅ **הערוץ זמין!** הודעה נשלחה בהצלחה - הערוץ מוכן לשימוש."
            elif not issues_found:
                report += "\n\n✅ **הכל תקין!** הערוץ מוכן לשימוש."
            else:
                report += "\n\n⚠️ **הערוץ נשמר למרות בעיות** - ייתכן שלא יעבוד עד שתתקן את הבעיות."
            
            report += "\n\n💾 **הערוץ נשמר במאגר**"
            if peer_id_b64:
                report += f"\n   • **peer_id_b64:** `{peer_id_b64[:20]}...`"
            report += f"\n   • **ID רגיל:** `{channel_id}`"
            report += "\n   • **שניהם יישמשו בשליחה**"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ הוסף עוד", callback_data="add_channels")],
                [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")]
            ])
        else:
            # לא נשמור - יש בעיות קריטיות
            report += "\n\n❌ **הערוץ לא נשמר במאגר**\n\n"
            report += "**סיבה:** לא ניתן לשלוח הודעה ולא ניתן ליצור peer_id_b64.\n\n"
            report += "**מה לעשות:**\n"
            report += "1. ודא שה-userbot חבר בערוץ\n"
            report += "2. ודא שה-userbot בעל הרשאות פרסום\n"
            report += "3. נסה שוב להעביר הודעה מהערוץ"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 נסה שוב", callback_data="add_channel_telegram")],
                [InlineKeyboardButton("🔙 חזור", callback_data="add_channels")]
            ])
        
        await processing_msg.edit_text(report, reply_markup=keyboard)
        
        # איפוס מצב רק אם שמרו
        if should_save:
            session.update_state(UserState.IDLE)
            if hasattr(session, 'adding_channel_platform'):
                delattr(session, 'adding_channel_platform')
            logger.info(f"✅ User {user.id} added telegram channel: {channel_title} ({channel_id})")
        else:
            # לוג מפורט עם וידוא שה-ID לא השתנה
            logger.warning(f"⚠️ User {user.id} tried to add channel {channel_id} (length: {len(channel_id)}) but checks failed - not saved")
            logger.warning(f"⚠️ Channel title: {channel_title}, Raw ID was: {raw_channel_id}")
        
    except Exception as e:
        logger.error(f"❌ Error handling forwarded channel message: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(
                f"❌ **שגיאה בעיבוד הודעה מועברת**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )
        except:
            await message.reply_text(
                f"❌ **שגיאה בעיבוד הודעה מועברת**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )


@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue", "test", "test_channel"]), group=-2)
@rate_limit(max_requests=50, window=60)
async def handle_add_channel(client: Client, message: Message):
    """מטפל בהוספת ערוץ/קבוצה - group=-2 נותן עדיפות גבוהה מאוד (לפני handle_template_edit)"""
    user = message.from_user
    logger.info(f"🔍 [ADD_CHANNEL] Handler triggered for user {user.id}, text: {message.text[:50]}")
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        logger.debug(f"⛔ User {user.id} not authorized, skipping")
        return
    
    session = state_manager.get_session(user.id)
    logger.info(f"📊 [ADD_CHANNEL] User {user.id} state: {session.state}")
    
    # בדיקה אם המשתמש במצב עריכת תבנית - אם כן, לא לטפל כאן
    if session.state == UserState.EDITING_TEMPLATE:
        logger.debug(f"User {user.id} is editing template, skipping add channel handler")
        return
    
    # בדיקה אם המשתמש במצב הוספת ערוץ/קבוצה
    if session.state != UserState.ADDING_CHANNEL:
        logger.debug(f"ℹ️ User {user.id} not in ADDING_CHANNEL state (current: {session.state}), skipping")
        return
    
    logger.info(f"✅ [ADD_CHANNEL] User {user.id} is in ADDING_CHANNEL state, processing...")
    
    if not hasattr(session, 'adding_channel_platform'):
        logger.warning(f"⚠️ User {user.id} in ADDING_CHANNEL state but no platform attribute")
        session.update_state(UserState.IDLE)
        await message.reply_text("❌ שגיאה: לא נמצאה פלטפורמה. המצב אופס.")
        return
    
    platform = session.adding_channel_platform
    
    # אם זה טלגרם, נדרוש העברת הודעה
    if platform == "telegram":
        await message.reply_text(
            "⚠️ **להוספת ערוץ טלגרם, יש להעביר הודעה מהערוץ אל הבוט**\n\n"
            "**איך לעשות זאת:**\n"
            "1. פתח את הערוץ בטלגרם\n"
            "2. בחר הודעה כלשהי מהערוץ\n"
            "3. לחץ על 'העבר' (Forward)\n"
            "4. בחר את הבוט הזה (הצ'אט הפרטי עם הבוט)\n"
            "5. שלח את ההודעה\n\n"
            "💡 **למה?** זה יטען את הערוץ ל-storage ויאפשר לבדוק שהכל תקין.\n\n"
            "לבטול: שלח /cancel"
        )
        return
    
    # אם זה WhatsApp, נמשיך עם הלוגיקה הישנה
    channel_id = message.text.strip()
    logger.info(f"➕ User {user.id} adding {platform} channel/group: {channel_id[:50]}")
    
    # תגובה מיידית למשתמש
    processing_msg = await message.reply_text("⏳ **מעבד...**")
    
    try:
        # בדיקה שהקלט לא ריק
        if not channel_id or not channel_id.strip():
            await processing_msg.edit_text(
                "⚠️ **הקלט ריק!**\n\n"
                "אנא שלח שם קבוצה תקין.\n\n"
                "לבטול: שלח /cancel"
            )
            return
        
        # הוספה למאגר
        logger.debug(f"💾 Adding {platform} channel/group to repository: {channel_id}")
        channels_manager.add_channel(platform, channel_id)
        logger.info(f"✅ Successfully added {platform} channel/group: {channel_id}")
        
        # איפוס מצב
        session.update_state(UserState.IDLE)
        if hasattr(session, 'adding_channel_platform'):
            delattr(session, 'adding_channel_platform')
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף עוד", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")]
        ])
        
        platform_name = "וואטסאפ"
        await processing_msg.edit_text(
            f"✅ **קבוצה נוספה בהצלחה!**\n\n"
            f"**פלטפורמה:** {platform_name}\n"
            f"**שם:** {channel_id}\n\n"
            f"💾 **נשמר במאגר**\n\n"
            f"כעת תוכל לקשר אותה לתבניות דרך תפריט עריכת תבניות.",
            reply_markup=keyboard
        )
        logger.info(f"✅ User {user.id} added {platform} channel/group: {channel_id}")
        
    except Exception as e:
        logger.error(f"❌ Error adding channel: {e}", exc_info=True)
        try:
            await processing_msg.edit_text(
                f"❌ **שגיאה בהוספת ערוץ/קבוצה**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )
        except:
            await message.reply_text(
                f"❌ **שגיאה בהוספת ערוץ/קבוצה**\n\n"
                f"**פרטי השגיאה:**\n`{str(e)}`\n\n"
                f"נסה שוב או שלח /cancel לביטול"
            )


@Client.on_callback_query(filters.regex("^edit_channels_(.+)$"))
async def edit_template_channels(client: Client, query: CallbackQuery):
    """תפריט עריכת ערוצים/קבוצות לתבנית"""
    template_name = query.data.replace("edit_channels_", "")
    logger.info(f"📢 User {query.from_user.id} editing channels for template: {template_name}")
    
    if template_name not in TEMPLATE_NAMES:
        logger.warning(f"❌ User {query.from_user.id} tried to edit channels for unknown template: {template_name}")
        await query.answer("❌ תבנית לא קיימת", show_alert=True)
        return
    
    platform = channels_manager.get_template_platform(template_name)
    template_display_name = TEMPLATE_NAMES[template_name]
    logger.debug(f"📊 Template {template_name} platform: {platform}")
    
    # קבלת כל הערוצים/קבוצות במאגר לפלטפורמה הזו
    repository = channels_manager.get_repository(platform)
    logger.debug(f"📋 Repository for {platform}: {len(repository)} items")
    
    if not repository:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף ערוצים/קבוצות", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור", callback_data=f"template_view_{template_name}")]
        ])
        await query.message.edit_text(
            f"📢 **עריכת ערוצים/קבוצות - {template_display_name}**\n\n"
            f"אין ערוצים/קבוצות במאגר עבור {platform}.\n"
            f"הוסף ערוצים/קבוצות תחילה.",
            reply_markup=keyboard
        )
        await query.answer()
        return
    
    # קבלת סטטוס כל הערוצים/קבוצות
    channels_status = channels_manager.get_all_template_channels_status(template_name, platform)
    logger.debug(f"📊 Channels status: {channels_status}")
    
    # בניית כפתורים - כל ערוץ/קבוצה עם X או V
    # שימוש ב-index במקום channel_id מלא כדי להימנע מ-callback_data גדול מדי
    buttons = []
    for index, channel_item in enumerate(repository):
        # חילוץ peer_id_b64 או שם קבוצה
        if platform == "telegram":
            if isinstance(channel_item, dict):
                channel_ref = channel_item.get("peer_id_b64") or channel_item.get("legacy_id", "")
                display_name = channel_item.get("title", "Unknown Channel")
                # ננסה לקבל שם עדכני מה-API
                try:
                    display_name = await get_channel_display_name(client, platform, channel_ref)
                except:
                    pass  # נשתמש ב-title מהמאגר
            else:
                # backward compatibility - string
                channel_ref = channel_item
                display_name = await get_channel_display_name(client, platform, channel_ref)
        else:
            # whatsapp - תמיכה גם ב-dicts (מיגרציה)
            if isinstance(channel_item, dict):
                # פורמט חדש (dict) - נשתמש ב-peer_id_b64 או title
                channel_ref = channel_item.get("peer_id_b64") or channel_item.get("title", "")
                display_name = channel_item.get("title", "Unknown Group")
                # ננסה לקבל שם עדכני מה-API
                try:
                    display_name = await get_channel_display_name(client, platform, channel_ref)
                except:
                    pass  # נשתמש ב-title מהמאגר
            else:
                # פורמט ישן (string) - שם הקבוצה
                channel_ref = channel_item
                display_name = await get_channel_display_name(client, platform, channel_ref)
        
        # קבלת סטטוס - צריך להשתמש ב-peer_id_b64 או שם קבוצה
        is_active = channels_status.get(channel_ref, False)
        # קיצור שם אם ארוך מדי
        if len(display_name) > 25:
            display_name = display_name[:25] + "..."
        button_text = f"{'✅' if is_active else '❌'} {display_name}"
        # שימוש ב-index במקום channel_id מלא (מוגבל ל-64 בתים)
        # קיצור template_name אם ארוך מדי
        short_template = template_name[:15] if len(template_name) > 15 else template_name
        callback_data = f"tg_{short_template}_{platform[0]}_{index}"  # platform[0] = 't' או 'w'
        # בדיקה שאורך callback_data לא עולה על 64 בתים
        callback_bytes = len(callback_data.encode('utf-8'))
        if callback_bytes > 64:
            logger.error(f"❌ Callback data too long: {callback_bytes} bytes")
            # קיצור נוסף
            short_template = template_name[:10] if len(template_name) > 10 else template_name
            callback_data = f"tg_{short_template}_{platform[0]}_{index}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton("🔙 חזור", callback_data=f"template_view_{template_name}")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    active_count = sum(1 for status in channels_status.values() if status)
    
    try:
        await query.message.edit_text(
            f"📢 **עריכת ערוצים/קבוצות - {template_display_name}**\n\n"
            f"**פעילים:** {active_count}/{len(repository)}\n\n"
            f"לחץ על ערוץ/קבוצה כדי להפעיל/לכבות:",
            reply_markup=keyboard
        )
        await query.answer()
    except Exception as e:
        logger.error(f"❌ Error displaying edit channels menu: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בתצוגת התפריט", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^tg_(.+)_(t|w)_([0-9]+)$"))
async def toggle_template_channel(client: Client, query: CallbackQuery):
    """החלפת סטטוס ערוץ/קבוצה עבור תבנית"""
    logger.info(f"🔄 User {query.from_user.id} toggling channel status")
    logger.debug(f"📊 Callback data: {query.data}")
    
    try:
        import re
        # הפורמט החדש: tg_{template_name}_{platform_letter}_{index}
        # דוגמה: tg_telegram_image_t_0 (t = telegram, w = whatsapp)
        match = re.match(r"^tg_(.+)_(t|w)_([0-9]+)$", query.data)
        if not match:
            raise ValueError(f"Invalid callback data format: {query.data}")
        
        short_template = match.group(1)
        platform_letter = match.group(2)
        index = int(match.group(3))
        
        # המרת platform_letter ל-platform מלא
        platform = "telegram" if platform_letter == "t" else "whatsapp"
        
        # מציאת template_name המלא - חיפוש לפי התחלה
        template_name = None
        for full_name in TEMPLATE_NAMES.keys():
            if full_name.startswith(short_template):
                template_name = full_name
                break
        
        if not template_name:
            # ניסיון נוסף - אולי short_template הוא שם מלא
            if short_template in TEMPLATE_NAMES:
                template_name = short_template
            else:
                logger.warning(f"❌ Could not find template matching: {short_template}")
                await query.answer("❌ תבנית לא נמצאה", show_alert=True)
                return
        
        logger.debug(f"📊 Parsed: short_template={short_template}, template={template_name}, platform={platform}, index={index}")
        
        # קבלת channel_id מה-index
        repository = channels_manager.get_repository(platform)
        if index >= len(repository):
            logger.error(f"❌ Index {index} out of range for {platform} repository (length: {len(repository)})")
            await query.answer("❌ שגיאה: ערוץ/קבוצה לא נמצא", show_alert=True)
            return
        
        channel_item = repository[index]
        
        # חילוץ peer_id_b64 או שם קבוצה
        if platform == "telegram":
            if isinstance(channel_item, dict):
                channel_id = channel_item.get("peer_id_b64", channel_item.get("legacy_id", ""))
            else:
                # backward compatibility - string
                channel_id = channel_item
        else:
            # whatsapp - תמיכה גם ב-dicts (מיגרציה)
            if isinstance(channel_item, dict):
                channel_id = channel_item.get("peer_id_b64") or channel_item.get("title", "")
            else:
                # פורמט ישן (string) - שם הקבוצה
                channel_id = channel_item
        
        logger.debug(f"📊 Channel ID from index {index}: {channel_id[:50] if len(channel_id) > 50 else channel_id}")
        
        # החלפת סטטוס
        current_status = channels_manager.is_template_channel_active(template_name, platform, channel_id)
        new_status = not current_status
        logger.info(f"🔄 Toggling {platform} channel/group '{channel_id[:50] if len(channel_id) > 50 else channel_id}' for template '{template_name}': {current_status} → {new_status}")
        
        channels_manager.set_template_channel_active(platform, channel_id, template_name, new_status)
        logger.info(f"✅ Successfully toggled channel status to {new_status}")
        
        # רענון התפריט - קריאה ישירה ל-edit_template_channels עם query מזויף
        class FakeQuery:
            def __init__(self, original_query, new_data):
                self.data = new_data
                self.from_user = original_query.from_user
                self.message = original_query.message
                self.answer = original_query.answer
        
        fake_query = FakeQuery(query, f"edit_channels_{template_name}")
        
        try:
            await edit_template_channels(client, fake_query)
            await query.answer(f"{'✅ הופעל' if new_status else '❌ בוטל'}")
        except Exception as e:
            logger.error(f"❌ Error refreshing menu after toggle: {e}", exc_info=True)
            await query.answer(f"{'✅ הופעל' if new_status else '❌ בוטל'} (תפריט לא עודכן)", show_alert=False)
        
    except Exception as e:
        logger.error(f"❌ Error toggling channel: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בהחלפת סטטוס", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^manage_channels_(telegram|whatsapp)$"))
async def manage_channels_menu(client: Client, query: CallbackQuery):
    """תפריט ניהול ערוצים/קבוצות במאגר"""
    platform = query.data.replace("manage_channels_", "")
    repository = channels_manager.get_repository(platform)
    
    if not repository:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ הוסף ערוצים/קבוצות", callback_data="add_channels")],
            [InlineKeyboardButton("🔙 חזור", callback_data="add_channels")]
        ])
        platform_name = "טלגרם" if platform == "telegram" else "וואטסאפ"
        await query.message.edit_text(
            f"📋 **ניהול ערוצים/קבוצות - {platform_name}**\n\n"
            f"אין ערוצים/קבוצות במאגר.",
            reply_markup=keyboard
        )
        await query.answer()
        return
    
    # בניית כפתורים - כל ערוץ/קבוצה עם כפתור הסרה
    # שימוש ב-index במקום channel_id מלא כדי להימנע מ-callback_data גדול מדי
    buttons = []
    for index, channel_item in enumerate(repository):
        # חילוץ peer_id_b64 או שם קבוצה
        if platform == "telegram":
            if isinstance(channel_item, dict):
                channel_ref = channel_item.get("peer_id_b64") or channel_item.get("legacy_id", "")
                display_name = channel_item.get("title", "Unknown Channel")
                # ננסה לקבל שם עדכני מה-API
                try:
                    display_name = await get_channel_display_name(client, platform, channel_ref)
                except:
                    pass  # נשתמש ב-title מהמאגר
            else:
                # backward compatibility - string
                channel_ref = channel_item
                display_name = await get_channel_display_name(client, platform, channel_ref)
        else:
            # whatsapp - תמיכה גם ב-dicts (מיגרציה)
            if isinstance(channel_item, dict):
                # פורמט חדש (dict) - נשתמש ב-peer_id_b64 או title
                channel_ref = channel_item.get("peer_id_b64") or channel_item.get("title", "")
                display_name = channel_item.get("title", "Unknown Group")
                # ננסה לקבל שם עדכני מה-API
                try:
                    display_name = await get_channel_display_name(client, platform, channel_ref)
                except:
                    pass  # נשתמש ב-title מהמאגר
            else:
                # פורמט ישן (string) - שם הקבוצה
                channel_ref = channel_item
                display_name = await get_channel_display_name(client, platform, channel_ref)
        # קיצור שם אם ארוך מדי
        if len(display_name) > 40:
            display_name = display_name[:40] + "..."
        button_text = f"🗑️ {display_name}"
        # שימוש ב-index במקום channel_id מלא
        callback_data = f"remove_{platform}_{index}"
        # בדיקה שאורך callback_data לא עולה על 64 בתים
        if len(callback_data.encode('utf-8')) > 64:
            logger.error(f"❌ Callback data too long: {len(callback_data.encode('utf-8'))} bytes")
            callback_data = f"rm_{platform}_{index}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    buttons.append([InlineKeyboardButton("🔙 חזור", callback_data="add_channels")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    platform_name = "טלגרם" if platform == "telegram" else "וואטסאפ"
    
    try:
        await query.message.edit_text(
            f"📋 **ניהול ערוצים/קבוצות - {platform_name}**\n\n"
            f"**סה\"כ:** {len(repository)}\n\n"
            f"לחץ על ערוץ/קבוצה להסרה מהמאגר:",
            reply_markup=keyboard
        )
        await query.answer()
    except Exception as e:
        logger.error(f"❌ Error displaying manage channels menu: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בתצוגת התפריט", show_alert=True)
        except:
            pass


@Client.on_callback_query(filters.regex("^remove_(telegram|whatsapp)_([0-9]+)$"))
async def remove_channel(client: Client, query: CallbackQuery):
    """הסרת ערוץ/קבוצה מהמאגר"""
    try:
        import re
        # הפורמט: remove_{platform}_{index}
        match = re.match(r"^remove_(telegram|whatsapp)_([0-9]+)$", query.data)
        if not match:
            raise ValueError(f"Invalid callback data format: {query.data}")
        
        platform = match.group(1)
        index = int(match.group(2))
        
        logger.debug(f"📊 Parsed: platform={platform}, index={index}")
        
        # קבלת channel_id מה-index
        repository = channels_manager.get_repository(platform)
        if index >= len(repository):
            logger.error(f"❌ Index {index} out of range for {platform} repository (length: {len(repository)})")
            await query.answer("❌ שגיאה: ערוץ/קבוצה לא נמצא", show_alert=True)
            return
        
        channel_item = repository[index]
        
        # חילוץ peer_id_b64 או שם קבוצה
        if platform == "telegram":
            if isinstance(channel_item, dict):
                channel_id = channel_item.get("peer_id_b64") or channel_item.get("legacy_id", "")
            else:
                # backward compatibility - string
                channel_id = channel_item
        else:
            # whatsapp - תמיכה גם ב-dicts (מיגרציה)
            if isinstance(channel_item, dict):
                channel_id = channel_item.get("peer_id_b64") or channel_item.get("title", "")
            else:
                # פורמט ישן (string) - שם הקבוצה
                channel_id = channel_item
        
        logger.info(f"🗑️ Removing {platform} channel/group: {channel_id[:50] if len(channel_id) > 50 else channel_id}")
        
        channels_manager.remove_channel(platform, channel_id)
        logger.info(f"✅ Removed {platform} channel/group: {channel_id[:50] if len(channel_id) > 50 else channel_id}")
        
        # רענון התפריט - יצירת query מזויף
        class FakeQuery:
            def __init__(self, original_query, new_data):
                self.data = new_data
                self.from_user = original_query.from_user
                self.message = original_query.message
                self.answer = original_query.answer
        
        fake_query = FakeQuery(query, f"manage_channels_{platform}")
        
        try:
            await manage_channels_menu(client, fake_query)
            await query.answer(f"✅ הוסר: {channel_id[:30] if len(channel_id) > 30 else channel_id}")
        except Exception as e:
            logger.error(f"❌ Error refreshing menu after remove: {e}", exc_info=True)
            await query.answer(f"✅ הוסר: {channel_id[:30]} (תפריט לא עודכן)", show_alert=False)
        
    except Exception as e:
        logger.error(f"❌ Error removing channel: {e}", exc_info=True)
        try:
            await query.answer("❌ שגיאה בהסרת ערוץ/קבוצה", show_alert=True)
        except:
            pass


logger.info("✅ Channel management handlers loaded")
