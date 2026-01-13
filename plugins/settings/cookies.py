"""
YouTube Cookies Management Plugin
Handlers for updating YouTube cookies file
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.media.utils import update_cookies
from services.user_states import state_manager, UserState
from services.rate_limiter import rate_limit
from core import is_authorized_user, ROOT_DIR
import logging
import os

logger = logging.getLogger(__name__)


@Client.on_callback_query(filters.regex("^update_cookies$"))
@rate_limit(max_requests=50, window=60)
async def update_cookies_menu(client: Client, query: CallbackQuery):
    """תפריט עדכון cookies"""
    cookies_path = ROOT_DIR / "cookies.txt"
    cookies_exists = cookies_path.exists()
    
    help_text = (
        "🍪 **עדכון קובץ Cookies**\n\n"
        "קובץ cookies משמש להורדות מ-YouTube.\n\n"
        "**הוראות:**\n"
        "1. הורד את קובץ ה-cookies שלך מהדפדפן\n"
        "2. שלח את הקובץ כאן\n\n"
        "**פורמט:**\n"
        "• Netscape HTTP Cookie File\n"
        "• שם קובץ: `cookies.txt`\n\n"
    )
    
    if cookies_exists:
        file_size = cookies_path.stat().st_size
        help_text += f"**סטטוס:** ✅ קובץ קיים ({file_size} bytes)\n\n"
    else:
        help_text += "**סטטוס:** ⚠️ אין קובץ cookies\n\n"
    
    help_text += "📤 **שלח את קובץ cookies עכשיו:**"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור", callback_data="back_to_settings")],
        [InlineKeyboardButton("❌ סגור", callback_data="close")]
    ])
    
    # עדכון מצב המשתמש
    session = state_manager.get_session(query.from_user.id)
    session.update_state(UserState.UPDATING_COOKIES)
    
    await query.message.edit_text(help_text, reply_markup=keyboard)
    await query.answer()


@Client.on_message(filters.document & filters.private & ~filters.command(["start", "help", "status", "cancel", "settings", "queue_status", "cancel_queue"]), group=0)
@rate_limit(max_requests=10, window=60)
async def handle_cookies_file(client: Client, message: Message):
    """מטפל בקבלת קובץ cookies"""
    user = message.from_user
    
    # בדיקת הרשאה
    if not is_authorized_user(user.id):
        return
    
    session = state_manager.get_session(user.id)
    
    # בדיקה אם המשתמש במצב עדכון cookies
    if session.state != UserState.UPDATING_COOKIES:
        return
    
    try:
        # בדיקה שהקובץ הוא cookies.txt או עם סיומת .txt
        file_name = message.document.file_name if message.document else None
        if not file_name or not file_name.endswith('.txt'):
            await message.reply_text(
                "⚠️ **קובץ לא תקין!**\n\n"
                "אנא שלח קובץ עם סיומת `.txt`\n"
                "שם הקובץ צריך להיות `cookies.txt`"
            )
            return
        
        # הורדת הקובץ
        downloads_dir = ROOT_DIR / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        temp_cookies_path = downloads_dir / f"temp_cookies_{user.id}.txt"
        
        downloaded_path = await message.download(file_name=str(temp_cookies_path))
        
        # עדכון cookies
        cookies_dest = ROOT_DIR / "cookies.txt"
        success = await update_cookies(str(downloaded_path), str(cookies_dest))
        
        # מחיקת קובץ זמני
        try:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except:
            pass
        
        if success:
            session.update_state(UserState.IDLE)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="back_to_settings")],
                [InlineKeyboardButton("❌ סגור", callback_data="close")]
            ])
            await message.reply_text(
                "✅ **קובץ cookies עודכן בהצלחה!**\n\n"
                "הקובץ נשמר ונשתמש בו להורדות מ-YouTube.",
                reply_markup=keyboard
            )
            logger.info(f"✅ User {user.id} updated cookies file")
        else:
            await message.reply_text(
                "❌ **שגיאה בעדכון cookies!**\n\n"
                "הקובץ לא תקין או יש בעיה בשמירה.\n"
                "נסה שוב או שלח /cancel לביטול"
            )
    
    except Exception as e:
        logger.error(f"❌ Error handling cookies file: {e}", exc_info=True)
        await message.reply_text(
            "❌ שגיאה בעיבוד הקובץ\n"
            "נסה שוב או שלח /cancel לביטול"
        )


logger.info("✅ Cookies handlers loaded")
