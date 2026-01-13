"""
Core Package
Application core components
"""

__version__ = "2.0.0"

# Import and re-export core components
from .config import (
    ROOT_DIR,
    API_ID,
    API_HASH,
    BOT_TOKEN,
    PHONE_NUMBER,
    LOG_CHANNEL_ID,
    ADMIN_ID,
    is_authorized_user,
    BOT_SESSION_NAME,
    USERBOT_SESSION_NAME,
    DOWNLOADS_PATH,
    PLUGINS_PATH,
    SERVICES_PATH,
    MAX_FILE_SIZE_MB,
    MAX_FILE_SIZE_BYTES,
    TELEGRAM_MAX_FILE_SIZE_MB,
    TELEGRAM_MAX_FILE_SIZE_BYTES,
    WHATSAPP_ENABLED,
    WHATSAPP_CHAT_NAME,
    WHATSAPP_DRY_RUN,
    WHATSAPP_SERVICE_URL,
    WHATSAPP_MAX_FILE_SIZE_MB,
    WHATSAPP_MAX_FILE_SIZE_BYTES,
    AUDIO_CONTENT_CHANNEL_ID,
    VIDEO_CONTENT_CHANNEL_ID,
    PUBLISH_TO_CHANNELS,
    validate_config,
    get_config_info,
)

from .executor import ExecutorManager, executor_manager
from .context import AppContext, get_context

__all__ = [
    # Config
    "ROOT_DIR",
    "API_ID",
    "API_HASH",
    "BOT_TOKEN",
    "PHONE_NUMBER",
    "LOG_CHANNEL_ID",
    "ADMIN_ID",
    "is_authorized_user",
    "BOT_SESSION_NAME",
    "USERBOT_SESSION_NAME",
    "DOWNLOADS_PATH",
    "PLUGINS_PATH",
    "SERVICES_PATH",
    "MAX_FILE_SIZE_MB",
    "MAX_FILE_SIZE_BYTES",
    "TELEGRAM_MAX_FILE_SIZE_MB",
    "TELEGRAM_MAX_FILE_SIZE_BYTES",
    "WHATSAPP_ENABLED",
    "WHATSAPP_CHAT_NAME",
    "WHATSAPP_DRY_RUN",
    "WHATSAPP_SERVICE_URL",
    "WHATSAPP_MAX_FILE_SIZE_MB",
    "WHATSAPP_MAX_FILE_SIZE_BYTES",
    "AUDIO_CONTENT_CHANNEL_ID",
    "VIDEO_CONTENT_CHANNEL_ID",
    "PUBLISH_TO_CHANNELS",
    "validate_config",
    "get_config_info",
    # Executor
    "ExecutorManager",
    "executor_manager",
    # Context
    "AppContext",
    "get_context",
]

