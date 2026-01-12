"""
Rate Limiting Service
מגביל מספר בקשות לכל משתמש בפרק זמן מסוים
"""
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, List, Union
from pyrogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

# Dictionary לשמירת בקשות משתמשים
user_requests: Dict[int, List[datetime]] = {}


def rate_limit(max_requests: int = 10, window: int = 60, skip_for_authorized: bool = True):
    """
    Decorator להגבלת מספר בקשות לכל משתמש
    תומך גם ב-Message וגם ב-CallbackQuery
    
    Args:
        max_requests: מספר מקסימלי של בקשות בחלון זמן (ברירת מחדל: 10)
        window: חלון זמן בשניות (ברירת מחדל: 60 שניות)
        skip_for_authorized: אם True, משתמשים מורשים לא מוגבלים (ברירת מחדל: True)
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(client, obj: Union[Message, CallbackQuery], *args, **kwargs):
            # קבלת user_id - תומך גם ב-Message וגם ב-CallbackQuery
            if isinstance(obj, CallbackQuery):
                user_id = obj.from_user.id if obj.from_user else None
                message_obj = obj.message  # CallbackQuery יש לו message
            elif isinstance(obj, Message):
                user_id = obj.from_user.id if obj.from_user else None
                message_obj = obj
            else:
                # אם זה משהו אחר, ממשיכים ללא rate limiting
                return await func(client, obj, *args, **kwargs)
            
            if not user_id:
                # אם אין user_id, ממשיכים ללא rate limiting
                return await func(client, obj, *args, **kwargs)
            
            # בדיקה אם המשתמש מורשה - אם כן, דילוג על rate limiting
            if skip_for_authorized:
                try:
                    from config import is_authorized_user
                    if is_authorized_user(user_id):
                        # משתמש מורשה - אין rate limiting
                        return await func(client, obj, *args, **kwargs)
                except:
                    pass  # אם יש שגיאה, ממשיכים עם rate limiting
            
            now = datetime.now()
            
            # אתחול רשימת בקשות למשתמש אם לא קיימת
            if user_id not in user_requests:
                user_requests[user_id] = []
            
            # ניקוי בקשות ישנות (מחוץ לחלון הזמן)
            user_requests[user_id] = [
                req_time for req_time in user_requests[user_id]
                if now - req_time < timedelta(seconds=window)
            ]
            
            # בדיקה אם חרג מהמגבלה
            if len(user_requests[user_id]) >= max_requests:
                remaining_time = window - (now - user_requests[user_id][0]).total_seconds()
                logger.warning(f"⛔ Rate limit exceeded for user {user_id}: {len(user_requests[user_id])}/{max_requests} requests in {window}s")
                try:
                    if isinstance(obj, CallbackQuery):
                        # ל-CallbackQuery נשלח answer
                        await obj.answer(
                            f"⚠️ יותר מדי בקשות! נסה שוב בעוד {int(remaining_time)} שניות.",
                            show_alert=True
                        )
                    else:
                        # ל-Message נשלח reply
                        await message_obj.reply_text(
                            f"⚠️ **יותר מדי בקשות!**\n\n"
                            f"נשלחו {len(user_requests[user_id])} בקשות ב-{window} שניות.\n"
                            f"נסה שוב בעוד {int(remaining_time)} שניות."
                        )
                except Exception as e:
                    logger.error(f"Error sending rate limit message: {e}")
                return
            
            # הוספת בקשה נוכחית
            user_requests[user_id].append(now)
            
            # הרצת הפונקציה המקורית
            return await func(client, obj, *args, **kwargs)
        
        return wrapper
    return decorator


def clear_user_requests(user_id: int = None):
    """
    מנקה בקשות ישנות של משתמש מסוים או של כל המשתמשים
    
    Args:
        user_id: ID של משתמש ספציפי (אם None, מנקה את כל המשתמשים)
    """
    if user_id:
        if user_id in user_requests:
            del user_requests[user_id]
            logger.debug(f"🧹 Cleared requests for user {user_id}")
    else:
        user_requests.clear()
        logger.debug("🧹 Cleared all user requests")

