"""
Delivery Services

Handles delivery of content to various platforms (Telegram, WhatsApp).
"""

from .telegram_fallback import (
    send_failed_file_to_telegram,
    create_telegram_fallback_callback,
    send_failed_whatsapp_files_to_user
)
from .telegram_delivery import send_content_to_telegram
from .whatsapp_delivery import send_content_to_whatsapp

__all__ = [
    'send_failed_file_to_telegram',
    'create_telegram_fallback_callback',
    'send_failed_whatsapp_files_to_user',
    'send_content_to_telegram',
    'send_content_to_whatsapp',
]
