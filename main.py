"""
Main Entry Point
Initializes and runs the Telegram Bot, Userbot, and services
"""
import asyncio
import hashlib
import logging
from pathlib import Path
from pyrogram import Client, idle
from services.user_states import state_manager
from core.context import AppContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# משתנים גלובליים לגישה מהפלאגינים
bot = None
userbot = None


async def periodic_session_cleanup():
    """
    ניקוי תקופתי של סשנים ישנים וקבצים (כל שעה)
    """
    while True:
        try:
            await asyncio.sleep(3600)  # כל שעה
            deleted_count = state_manager.cleanup_old_sessions(max_age_hours=24)
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old session(s)")
            
            # ניקוי תקופתי של רשימות קבצים
            files_cleaned = state_manager.cleanup_files_periodically(max_files_per_session=50)
            if files_cleaned > 0:
                logger.info(f"🧹 Cleaned {files_cleaned} old file references")
        except Exception as e:
            logger.error(f"❌ Error in periodic cleanup: {e}", exc_info=True)


async def main():
    """Main async entry point"""
    global bot, userbot
    
    try:
        # Validate configuration
        from core import validate_config
        validate_config()
        logger.info("✅ Configuration validated successfully")
        
        # Check FFmpeg availability
        from services.media.ffmpeg_utils import check_ffmpeg_available
        if not await check_ffmpeg_available():
            raise RuntimeError("FFmpeg is not installed or not in PATH. Please install FFmpeg to continue.")
        logger.info("✅ FFmpeg availability verified")
        
        # Log configuration info
        logger.info("Current Configuration:")
        from core import get_config_info
        for key, value in get_config_info().items():
            logger.info(f"  {key}: {value}")
        
        logger.info("🚀 Starting Bot System...")
        
        # Initialize Bot Client
        from core import (
            BOT_SESSION_NAME, API_ID, API_HASH, BOT_TOKEN,
            USERBOT_SESSION_NAME, PHONE_NUMBER, ROOT_DIR
        )
        bot = Client(
            name=BOT_SESSION_NAME,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
            workdir=str(ROOT_DIR)
        )
        
        # Initialize Userbot Client
        userbot = Client(
            name=USERBOT_SESSION_NAME,
            api_id=API_ID,
            api_hash=API_HASH,
            phone_number=PHONE_NUMBER,
            workdir=str(ROOT_DIR)
        )
        
        logger.info("📱 Starting Bot Client...")
        await bot.start()
        logger.info("✅ Bot Client started successfully")
        
        logger.info("👤 Starting Userbot Client...")
        await userbot.start()
        logger.info("✅ Userbot Client started successfully")
        
        # Register clients in AppContext
        context = AppContext()
        context.set_bot(bot)
        context.set_userbot(userbot)
        logger.info("✅ AppContext initialized with bot and userbot")
        
        # Get bot info
        bot_info = await bot.get_me()
        logger.info(f"🤖 Bot: @{bot_info.username} ({bot_info.first_name})")
        
        # Get userbot info
        userbot_info = await userbot.get_me()
        logger.info(f"👤 Userbot: @{userbot_info.username if userbot_info.username else userbot_info.first_name}")
        
        # Log userbot account details
        logger.info("=" * 60)
        logger.info("📋 Userbot Account Information:")
        logger.info(f"   • ID: {userbot_info.id}")
        logger.info(f"   • Username: @{userbot_info.username}" if userbot_info.username else f"   • Username: (none)")
        logger.info(f"   • Phone: {userbot_info.phone_number}" if userbot_info.phone_number else f"   • Phone: (hidden)")
        logger.info(f"   • First Name: {userbot_info.first_name}")
        if userbot_info.last_name:
            logger.info(f"   • Last Name: {userbot_info.last_name}")
        
        # Log session information
        logger.info("📁 Session Information:")
        session_file_path = Path(ROOT_DIR) / f"{USERBOT_SESSION_NAME}.session"
        if session_file_path.exists():
            session_file_size = session_file_path.stat().st_size
            logger.info(f"   • Session File: {session_file_path.name}")
            logger.info(f"   • Session Path: {session_file_path}")
            logger.info(f"   • Session Size: {session_file_size:,} bytes")
            
            # Calculate hash of session file (first 1KB for quick hash)
            try:
                with open(session_file_path, 'rb') as f:
                    first_kb = f.read(1024)
                    session_hash = hashlib.md5(first_kb).hexdigest()[:12]
                    logger.info(f"   • Session Hash (first 1KB): {session_hash}")
            except Exception as e:
                logger.warning(f"   • Could not calculate session hash: {e}")
        else:
            # Check if using session string instead
            logger.info(f"   • Session File: Not found (using session string or in-memory)")
            # Try to get session string from client if available
            if hasattr(userbot, 'storage') and hasattr(userbot.storage, 'dc_id'):
                logger.info(f"   • Session Type: In-memory/Pyrogram storage")
        
        logger.info("=" * 60)
        
        logger.info("✅ Both clients are running!")
        logger.info("⏳ Press Ctrl+C to stop...")
        
        # Start processing queue worker
        from services.processing_queue import processing_queue
        asyncio.create_task(processing_queue.process_queue())
        logger.info("🔄 Processing queue worker started")
        
        # Start periodic cleanup task for old sessions
        asyncio.create_task(periodic_session_cleanup())
        
        # Keep the clients running
        await idle()
        
    except ValueError as e:
        logger.error(f"❌ Configuration Error: {e}")
        logger.error("Please check your .env file and make sure all required values are set")
        return
    except KeyboardInterrupt:
        logger.info("\n⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("👋 Shutting down clients...")
        try:
            if 'bot' in locals():
                await bot.stop()
                logger.info("✅ Bot stopped")
            if 'userbot' in locals():
                await userbot.stop()
                logger.info("✅ Userbot stopped")
        except Exception as e:
            logger.error(f"Error stopping clients: {e}")
        logger.info("🏁 Shutdown complete")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

