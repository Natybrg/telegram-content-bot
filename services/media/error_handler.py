"""
Error Handler Decorator for Media Functions
Decorator לטיפול אחיד בשגיאות בפונקציות media
"""
import logging
import subprocess
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def handle_media_errors(func: Callable) -> Callable:
    """
    Decorator לטיפול אחיד בשגיאות בפונקציות media
    
    מטפל ב:
    - FileNotFoundError
    - subprocess.CalledProcessError (FFmpeg errors)
    - Exception כללי
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except FileNotFoundError as e:
            logger.error(f"❌ File not found: {e}")
            return None
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"❌ FFmpeg error: {error_msg}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error in {func.__name__}: {e}", exc_info=True)
            return None
    
    return wrapper

