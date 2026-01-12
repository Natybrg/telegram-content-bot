"""
Channels Manager
מנהל ערוצים וקבוצות לבוט
"""

from .manager import channels_manager
from .sender import send_to_telegram_channels, send_to_whatsapp_groups

__all__ = ['channels_manager', 'send_to_telegram_channels', 'send_to_whatsapp_groups']

