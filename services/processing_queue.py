"""
Processing Queue - תור עיבוד למשתמשים
"""
import asyncio
import logging
from typing import Optional, Callable, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class QueueItem:
    """פריט בתור"""
    def __init__(self, user_id: int, callback: Callable, message, added_at: datetime, status_msg=None):
        self.user_id = user_id
        self.callback = callback
        self.message = message
        self.added_at = added_at
        self.status_msg = status_msg

class ProcessingQueue:
    """תור FIFO משופר לעיבוד משתמשים"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current_user_id: Optional[int] = None
        self.is_processing = False
        # מפה של user_id -> QueueItem לצורך ביטול
        self.waiting_users: Dict[int, QueueItem] = {}
    
    async def add_to_queue(self, user_id: int, callback: Callable, message, status_msg=None):
        """הוספת משימה לתור"""
        # בדיקה אם המשתמש כבר בתור
        if user_id in self.waiting_users or user_id == self.current_user_id:
            if status_msg:
                try:
                    await status_msg.edit_text(
                        "⚠️ **כבר יש לך תור פעיל!**\n\n"
                        "השתמש ב-/cancel_queue לביטול התור הנוכחי"
                    )
                except:
                    await message.reply_text(
                        "⚠️ **כבר יש לך תור פעיל!**\n\n"
                        "השתמש ב-/cancel_queue לביטול התור הנוכחי"
                    )
            else:
                await message.reply_text(
                    "⚠️ **כבר יש לך תור פעיל!**\n\n"
                    "השתמש ב-/cancel_queue לביטול התור הנוכחי"
                )
            return
        
        queue_size = self.queue.qsize()
        
        if queue_size > 0 and status_msg:
            # עדכון status_msg עם מידע על התור
            queue_status = self.get_queue_status(user_id)
            # יצירת הודעה על התור
            queue_text = (
                "📊 **מצב התור**\n\n"
                f"👥 **סה\"כ בתור:** {queue_status['queue_size'] + 1} משתמשים\n"
                f"📍 **המיקום שלך:** {queue_status['queue_size'] + 1}\n"
                f"⏱️ **זמן משוער:** ~{(queue_status['queue_size'] + 1) * 2} דקות\n\n"
                f"⏳ **ממתין בתור...**\n"
                f"[░░░░░░░░░░] 0%"
            )
            try:
                await status_msg.edit_text(queue_text)
            except Exception as e:
                logger.warning(f"Failed to update status_msg with queue info: {e}")
                await message.reply_text(
                    f"⏳ **נמצא בתור...**\n"
                    f"מיקום: {queue_size + 1}\n"
                    f"זמן משוער: ~{queue_size * 2} דקות\n\n"
                    f"💡 שלח /cancel_queue לביטול\n"
                    f"📊 שלח /queue_status לבדיקת מצב התור"
                )
        
        item = QueueItem(user_id, callback, message, datetime.now(), status_msg)
        self.waiting_users[user_id] = item
        await self.queue.put(item)
        logger.info(f"📋 User {user_id} added to queue. Queue size: {queue_size + 1}")
    
    async def cancel_queue(self, user_id: int) -> bool:
        """ביטול מקום בתור"""
        if user_id == self.current_user_id:
            logger.warning(f"⚠️ Cannot cancel - User {user_id} is currently being processed")
            return False
        
        if user_id not in self.waiting_users:
            logger.warning(f"⚠️ User {user_id} not in queue")
            return False
        
        # הסרה מהמפה
        del self.waiting_users[user_id]
        logger.info(f"🚫 User {user_id} cancelled their queue position")
        return True
    
    def get_queue_status(self, user_id: int) -> dict:
        """קבלת מצב התור"""
        queue_size = self.queue.qsize()
        
        status = {
            "queue_size": queue_size,
            "is_processing": self.is_processing,
            "current_user_id": self.current_user_id,
            "user_in_queue": user_id in self.waiting_users,
            "user_position": None,
            "estimated_wait_minutes": None
        }
        
        # חישוב מיקום המשתמש בתור
        if user_id in self.waiting_users:
            position = 1
            for item in list(self.waiting_users.values()):
                if item.user_id == user_id:
                    status["user_position"] = position
                    status["estimated_wait_minutes"] = position * 2
                    break
                position += 1
        
        return status
    
    async def process_queue(self):
        """לולאת עיבוד התור"""
        logger.info("🔄 Processing queue worker started")
        
        while True:
            try:
                item = await self.queue.get()
                
                # בדיקה אם המשתמש ביטל את התור
                if item.user_id not in self.waiting_users:
                    logger.info(f"⏭️ Skipping cancelled user {item.user_id}")
                    self.queue.task_done()
                    continue
                
                # הסרה מרשימת המתנה
                del self.waiting_users[item.user_id]
                
                self.current_user_id = item.user_id
                self.is_processing = True
                
                logger.info(f"▶️ Processing user {item.user_id}")
                
                # עדכון status_msg שמגיע תורו (אם קיים)
                if item.status_msg:
                    try:
                        await item.status_msg.edit_text(
                            "⚙️ **מצב עיבוד**\n\n"
                            "🎯 **הגיע תורך!**\n"
                            "מתחיל עיבוד התוכן שלך עכשיו...\n\n"
                            f"⏳ **מתחיל עיבוד...**\n"
                            f"[░░░░░░░░░░] 0%"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update status_msg: {e}")
                        try:
                            await item.message.reply_text(
                                "🎯 **הגיע תורך!**\n"
                                "מתחיל עיבוד התוכן שלך עכשיו...\n\n"
                                "⏳ אנא המתן..."
                            )
                        except:
                            pass
                else:
                    # אם אין status_msg, שולחים הודעה רגילה
                    try:
                        await item.message.reply_text(
                            "🎯 **הגיע תורך!**\n"
                            "מתחיל עיבוד התוכן שלך עכשיו...\n\n"
                            "⏳ אנא המתן..."
                        )
                    except Exception as e:
                        logger.error(f"Failed to send 'your turn' message: {e}")
                
                # עיבוד התוכן
                try:
                    await item.callback()
                except Exception as e:
                    logger.error(f"❌ Error processing user {item.user_id}: {e}", exc_info=True)
                    if item.status_msg:
                        try:
                            from plugins.content_creator import create_progress_bar
                            await item.status_msg.edit_text(
                                f"❌ **שגיאה בעיבוד!**\n\n"
                                f"פרטי שגיאה: {str(e)}\n\n"
                                f"שלח /cancel להתחלה מחדש"
                            )
                        except:
                            try:
                                await item.message.reply_text(f"❌ שגיאה בעיבוד: {str(e)}")
                            except:
                                pass
                    else:
                        try:
                            await item.message.reply_text(f"❌ שגיאה בעיבוד: {str(e)}")
                        except:
                            pass
                
                self.current_user_id = None
                self.is_processing = False
                logger.info(f"✅ Finished processing user {item.user_id}")
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Error in queue worker: {e}", exc_info=True)
                self.is_processing = False
                self.current_user_id = None
                await asyncio.sleep(1)

processing_queue = ProcessingQueue()
