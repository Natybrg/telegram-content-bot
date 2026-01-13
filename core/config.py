"""
Configuration Module
Loads environment variables and provides centralized configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
ROOT_DIR = Path(__file__).parent.parent.absolute()

# Telegram API Configuration
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")

# Admin & Logging Configuration
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))


def is_authorized_user(user_id: int) -> bool:
    """
    בדיקה האם המשתמש מורשה
    
    Args:
        user_id: מזהה המשתמש
        
    Returns:
        True if authorized, False otherwise
    """
    return user_id == ADMIN_ID


# Session Names
BOT_SESSION_NAME = os.getenv("BOT_SESSION_NAME", "telegram_bot")
USERBOT_SESSION_NAME = os.getenv("USERBOT_SESSION_NAME", "telegram_userbot")

# Paths Configuration
DOWNLOADS_PATH = ROOT_DIR / os.getenv("DOWNLOADS_PATH", "downloads")
PLUGINS_PATH = ROOT_DIR / "plugins"
SERVICES_PATH = ROOT_DIR / "services"

# File Size Limits
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 2000))  # Telegram max: 2GB
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TELEGRAM_MAX_FILE_SIZE_MB = 2048  # Telegram max: 2GB
TELEGRAM_MAX_FILE_SIZE_BYTES = TELEGRAM_MAX_FILE_SIZE_MB * 1024 * 1024

# WhatsApp Configuration
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_CHAT_NAME = os.getenv("WHATSAPP_CHAT_NAME", "")
WHATSAPP_DRY_RUN = os.getenv("WHATSAPP_DRY_RUN", "false").lower() == "true"
WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:3000")

# WhatsApp File Size Limits
WHATSAPP_MAX_FILE_SIZE_MB = 70
WHATSAPP_MAX_FILE_SIZE_BYTES = WHATSAPP_MAX_FILE_SIZE_MB * 1024 * 1024

# Telegram Channels Configuration
# ערוץ לפרסום תמונה + MP3 (תוכן אודיו)
_audio_channel = os.getenv("AUDIO_CONTENT_CHANNEL_ID", "")
AUDIO_CONTENT_CHANNEL_ID = int(_audio_channel) if _audio_channel else None
# ערוץ לפרסום וידאו
_video_channel = os.getenv("VIDEO_CONTENT_CHANNEL_ID", "")
VIDEO_CONTENT_CHANNEL_ID = int(_video_channel) if _video_channel else None
# האם לפרסם בערוצים
PUBLISH_TO_CHANNELS = os.getenv("PUBLISH_TO_CHANNELS", "false").lower() == "true"


def validate_config():
    """
    Validates that all required configuration values are set
    Raises ValueError if any required config is missing
    
    Returns:
        True if configuration is valid
        
    Raises:
        ValueError: If configuration is invalid
    """
    errors = []
    
    if not API_ID or API_ID == 0:
        errors.append("API_ID is not set in .env file")
    
    if not API_HASH:
        errors.append("API_HASH is not set in .env file")
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set in .env file")
    
    if not PHONE_NUMBER:
        errors.append("PHONE_NUMBER is not set in .env file")
    
    if not LOG_CHANNEL_ID or LOG_CHANNEL_ID == 0:
        errors.append("LOG_CHANNEL_ID is not set in .env file")
    
    if not ADMIN_ID or ADMIN_ID == 0:
        errors.append("ADMIN_ID is not set in .env file")
    
    if errors:
        error_message = "Configuration errors:\n" + "\n".join(f"  - {err}" for err in errors)
        raise ValueError(error_message)
    
    # Create necessary directories
    DOWNLOADS_PATH.mkdir(exist_ok=True)
    PLUGINS_PATH.mkdir(exist_ok=True)
    SERVICES_PATH.mkdir(exist_ok=True)
    
    return True


def get_config_info():
    """
    Returns a dictionary with current configuration (safe for logging)
    
    Returns:
        dict: Configuration information
    """
    return {
        "API_ID": "***" if API_ID else "Not Set",
        "API_HASH": "***" if API_HASH else "Not Set",
        "BOT_TOKEN": "***" if BOT_TOKEN else "Not Set",
        "PHONE_NUMBER": f"{PHONE_NUMBER[:4]}***" if PHONE_NUMBER else "Not Set",
        "LOG_CHANNEL_ID": LOG_CHANNEL_ID if LOG_CHANNEL_ID else "Not Set",
        "ADMIN_ID": ADMIN_ID if ADMIN_ID else "Not Set",
        "DOWNLOADS_PATH": str(DOWNLOADS_PATH),
        "MAX_FILE_SIZE_MB": MAX_FILE_SIZE_MB,
        "PUBLISH_TO_CHANNELS": PUBLISH_TO_CHANNELS,
        "AUDIO_CONTENT_CHANNEL": AUDIO_CONTENT_CHANNEL_ID if AUDIO_CONTENT_CHANNEL_ID else "Not Set",
        "VIDEO_CONTENT_CHANNEL": VIDEO_CONTENT_CHANNEL_ID if VIDEO_CONTENT_CHANNEL_ID else "Not Set",
    }


if __name__ == "__main__":
    # Test configuration
    try:
        validate_config()
        print("✅ Configuration validated successfully!")
        print("\nCurrent Configuration:")
        for key, value in get_config_info().items():
            print(f"  {key}: {value}")
    except ValueError as e:
        print(f"❌ Configuration Error:\n{e}")
