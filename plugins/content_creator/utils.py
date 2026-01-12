"""
פונקציות עזר לעדכוני התקדמות
"""
import logging
from typing import List
from pyrogram import Client
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# מצבי התקדמות מבוקשים: 0, 12, 43, 50, 67, 79, 80, 85, 99, 100
PROGRESS_STAGES = [0, 12, 43, 50, 67, 79, 80, 85, 99, 100]


def get_progress_stage(percent: float) -> int:
    """
    מחזיר את המצב הקרוב ביותר מבין המצבים המבוקשים
    """
    # מצא את המצב הקרוב ביותר
    closest = PROGRESS_STAGES[0]
    min_diff = abs(percent - closest)
    
    for stage in PROGRESS_STAGES:
        diff = abs(percent - stage)
        if diff < min_diff:
            min_diff = diff
            closest = stage
    
    return closest


def create_progress_bar(percent, length=10):
    """יוצר progress bar ויזואלי"""
    filled = int(length * percent / 100)
    return f"[{'█' * filled}{'░' * (length - filled)}] {percent}%"


def get_emoji_for_stage(stage_index):
    """מחזיר אמוג'י לפי אינדקס השלב (רוטציה)"""
    emojis = ["⏳", "⌛"]
    return emojis[stage_index % 2]


async def delete_old_messages(client: Client, messages: List[Message], keep_last: Message = None):
    """
    מוחק הודעות ישנות, משאיר רק את ההודעה האחרונה
    
    Args:
        client: Pyrogram Client
        messages: רשימת הודעות למחיקה
        keep_last: הודעה לשמירה (לא למחוק)
    """
    if not messages:
        return
    
    try:
        # מסנן את ההודעה האחרונה אם קיימת
        messages_to_delete = [msg for msg in messages if keep_last is None or msg.id != keep_last.id]
        
        if not messages_to_delete:
            return
        
        # מחלק ל-batches של 100 (מגבלת Telegram)
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(messages_to_delete), batch_size):
            batch = messages_to_delete[i:i + batch_size]
            try:
                # מקבץ לפי chat_id
                chat_messages = {}
                for msg in batch:
                    chat_id = msg.chat.id
                    if chat_id not in chat_messages:
                        chat_messages[chat_id] = []
                    chat_messages[chat_id].append(msg.id)
                
                # מוחק כל chat בנפרד
                for chat_id, msg_ids in chat_messages.items():
                    try:
                        await client.delete_messages(chat_id, msg_ids)
                        deleted_count += len(msg_ids)
                        logger.debug(f"🗑️ Deleted {len(msg_ids)} messages from chat {chat_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to delete messages from chat {chat_id}: {e}")
                        
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete batch: {e}")
        
        if deleted_count > 0:
            logger.info(f"🗑️ Deleted {deleted_count} old messages")
            
    except Exception as e:
        logger.error(f"❌ Error deleting messages: {e}", exc_info=True)

