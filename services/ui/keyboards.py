from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard():
    """מחזיר את המקלדת הקבועה עם כפתורי הגדרות וביטול"""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("⚙️ הגדרות"), KeyboardButton("❌ ביטול")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
