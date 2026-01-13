"""
Instagram Story Downloader
מוריד סטורי ורילס מאינסטגרם באמצעות instagrapi
"""
import logging
import os
from pathlib import Path
from typing import Optional, Tuple
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, PleaseWaitFewMinutes, ChallengeRequired
from core import ROOT_DIR, DOWNLOADS_PATH

logger = logging.getLogger(__name__)

# נתיב לשמירת סשן
SESSION_FILE = ROOT_DIR / "instagram_session.json"


class InstagramDownloader:
    """מנהל הורדת סטורי ורילס מאינסטגרם"""
    
    def __init__(self):
        self.client = None
        self.username = os.getenv("IG_USERNAME", "")
        self.password = os.getenv("IG_PASSWORD", "")
        self._ensure_credentials()
    
    def _ensure_credentials(self):
        """בודק שיש פרטי התחברות"""
        if not self.username or not self.password:
            logger.warning("⚠️ IG_USERNAME or IG_PASSWORD not set in .env file")
    
    def _load_session(self) -> bool:
        """טוען סשן קיים אם קיים"""
        if SESSION_FILE.exists():
            try:
                self.client.load_settings(str(SESSION_FILE))
                logger.info("✅ Loaded existing Instagram session")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to load session: {e}")
                return False
        return False
    
    def _save_session(self):
        """שומר סשן לקובץ"""
        try:
            self.client.dump_settings(str(SESSION_FILE))
            logger.info("✅ Saved Instagram session")
        except Exception as e:
            logger.error(f"❌ Failed to save session: {e}")
    
    def _login(self) -> bool:
        """מתחבר לאינסטגרם"""
        if not self.username or not self.password:
            raise ValueError("IG_USERNAME and IG_PASSWORD must be set in .env file")
        
        try:
            self.client = Client()
            
            # ניסיון לטעון סשן קיים
            if self._load_session():
                try:
                    # בדיקה שהסשן עדיין תקף
                    self.client.account_info()
                    logger.info("✅ Instagram session is valid")
                    return True
                except (LoginRequired, ChallengeRequired):
                    logger.info("⚠️ Session expired, logging in again...")
            
            # התחברות חדשה
            logger.info(f"🔐 Logging in to Instagram as {self.username}...")
            self.client.login(self.username, self.password)
            self._save_session()
            logger.info("✅ Successfully logged in to Instagram")
            return True
            
        except PleaseWaitFewMinutes as e:
            logger.error(f"❌ Instagram rate limit: {e}")
            raise
        except ChallengeRequired as e:
            logger.error(f"❌ Instagram challenge required: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to login to Instagram: {e}")
            raise
    
    def _ensure_logged_in(self):
        """מוודא שהמשתמש מחובר"""
        if self.client is None:
            self._login()
        else:
            try:
                # בדיקה שהסשן עדיין תקף
                self.client.account_info()
            except (LoginRequired, ChallengeRequired):
                logger.info("⚠️ Session expired, re-logging in...")
                self._login()
    
    def download_story_from_url(self, url: str, download_path: Optional[Path] = None) -> Tuple[str, str]:
        """
        מוריד סטורי מקישור
        
        Args:
            url: קישור לסטורי
            download_path: תיקיית הורדה (אופציונלי)
        
        Returns:
            Tuple[file_path, media_type] - נתיב לקובץ וסוג המדיה (video/image)
        
        Raises:
            ValueError: אם הקישור לא תקין
            Exception: אם ההורדה נכשלה
        """
        if not download_path:
            download_path = DOWNLOADS_PATH
        
        download_path = Path(download_path)
        download_path.mkdir(parents=True, exist_ok=True)
        
        # וידוא התחברות
        self._ensure_logged_in()
        
        try:
            # חילוץ Story PK מהקישור
            logger.info(f"🔍 Extracting story PK from URL: {url}")
            story_pk = self.client.story_pk_from_url(url)
            
            if not story_pk:
                raise ValueError(f"Could not extract story PK from URL: {url}")
            
            logger.info(f"✅ Story PK: {story_pk}")
            
            # קבלת מידע על הסטורי
            story_info = self.client.story_info(story_pk)
            
            if not story_info:
                raise ValueError(f"Could not fetch story info for PK: {story_pk}")
            
            # בדיקה אם זה וידאו או תמונה
            is_video = story_info.media_type == 2  # 2 = video, 1 = image
            
            # הורדת המדיה
            if is_video:
                logger.info("📹 Downloading story video...")
                file_path = self.client.story_download(story_pk, download_path)
                media_type = "video"
            else:
                logger.info("🖼️ Downloading story image...")
                file_path = self.client.story_download(story_pk, download_path)
                media_type = "image"
            
            if not file_path or not Path(file_path).exists():
                raise ValueError(f"Downloaded file not found: {file_path}")
            
            logger.info(f"✅ Story downloaded: {file_path}")
            return str(file_path), media_type
            
        except Exception as e:
            logger.error(f"❌ Error downloading story: {e}", exc_info=True)
            raise
    
    def download_reel_from_url(self, url: str, download_path: Optional[Path] = None) -> Tuple[str, str]:
        """
        מוריד רילס מקישור
        
        Args:
            url: קישור לרילס
            download_path: תיקיית הורדה (אופציונלי)
        
        Returns:
            Tuple[file_path, media_type] - נתיב לקובץ וסוג המדיה (תמיד video)
        
        Raises:
            ValueError: אם הקישור לא תקין
            Exception: אם ההורדה נכשלה
        """
        if not download_path:
            download_path = DOWNLOADS_PATH
        
        download_path = Path(download_path)
        download_path.mkdir(parents=True, exist_ok=True)
        
        # וידוא התחברות
        self._ensure_logged_in()
        
        try:
            # חילוץ Media ID מהקישור
            logger.info(f"🔍 Extracting media ID from URL: {url}")
            media_id = self.client.media_id_from_url(url)
            
            if not media_id:
                raise ValueError(f"Could not extract media ID from URL: {url}")
            
            logger.info(f"✅ Media ID: {media_id}")
            
            # הורדת הרילס
            logger.info("📹 Downloading reel...")
            file_path = self.client.video_download(media_id, download_path)
            
            if not file_path or not Path(file_path).exists():
                raise ValueError(f"Downloaded file not found: {file_path}")
            
            logger.info(f"✅ Reel downloaded: {file_path}")
            return str(file_path), "video"
            
        except Exception as e:
            logger.error(f"❌ Error downloading reel: {e}", exc_info=True)
            raise


# יצירת מופע גלובלי
instagram_downloader = InstagramDownloader()


def download_instagram_story(url: str, download_path: Optional[Path] = None) -> Tuple[str, str]:
    """
    פונקציה נוחה להורדת סטורי
    
    Args:
        url: קישור לסטורי
        download_path: תיקיית הורדה (אופציונלי)
    
    Returns:
        Tuple[file_path, media_type] - נתיב לקובץ וסוג המדיה
    """
    return instagram_downloader.download_story_from_url(url, download_path)


def download_instagram_reel(url: str, download_path: Optional[Path] = None) -> Tuple[str, str]:
    """
    פונקציה נוחה להורדת רילס
    
    Args:
        url: קישור לרילס
        download_path: תיקיית הורדה (אופציונלי)
    
    Returns:
        Tuple[file_path, media_type] - נתיב לקובץ וסוג המדיה
    """
    return instagram_downloader.download_reel_from_url(url, download_path)


def is_instagram_story_url(url: str) -> bool:
    """בודק אם הקישור הוא לסטורי"""
    return "instagram.com/stories/" in url.lower() or "instagram.com/s/" in url.lower()


def is_instagram_reel_url(url: str) -> bool:
    """בודק אם הקישור הוא לרילס"""
    return "instagram.com/reel/" in url.lower() or "instagram.com/p/" in url.lower()

