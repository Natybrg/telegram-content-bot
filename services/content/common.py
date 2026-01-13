"""
פונקציות עזר משותפות לעיבוד תוכן
"""
import logging

logger = logging.getLogger(__name__)

# מצבי התקדמות מבוקשים
PROGRESS_STAGES = [0, 12, 43, 50, 67, 79, 80, 85, 99, 100]


def get_progress_stage(percent: float) -> int:
    """מחזיר את המצב הקרוב ביותר מבין המצבים המבוקשים"""
    closest = PROGRESS_STAGES[0]
    min_diff = abs(percent - closest)
    for stage in PROGRESS_STAGES:
        diff = abs(percent - stage)
        if diff < min_diff:
            min_diff = diff
            closest = stage
    return closest


def create_progress_bar(percent, length=10):
    """יוצר progress bar ויזואלי"""
    filled = int(length * percent / 100)
    return f"[{'█' * filled}{'░' * (length - filled)}] {percent}%"


def _import_cleanup():
    """Lazy import of cleanup functions to avoid circular import"""
    from plugins.content_creator.cleanup import schedule_cleanup, cleanup_session_files
    return schedule_cleanup, cleanup_session_files
