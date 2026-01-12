"""
WhatsApp Delivery Module - New Version
שליחת קבצים לוואטסאפ דרך whatsapp-web.js (Node.js service)
"""
import logging
import os
import time
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import config

logger = logging.getLogger(__name__)


class WhatsAppDeliveryError(Exception):
    """שגיאה בשליחת WhatsApp"""
    pass


class WhatsAppDelivery:
    """
    מנהל שליחת קבצים לוואטסאפ דרך Node.js service (whatsapp-web.js)
    """
    
    def __init__(self, dry_run: bool = False, service_url: str = None):
        """
        אתחול שירות שליחת WhatsApp
        
        Args:
            dry_run: אם True, לא ישלח בפועל (simulation mode)
            service_url: כתובת שרת Node.js (ברירת מחדל מ-config)
        """
        self.dry_run = dry_run
        self.service_url = (service_url or config.WHATSAPP_SERVICE_URL).rstrip('/')
        self.logs_dir = config.ROOT_DIR / "logs" / "whatsapp"
        self.screenshots_dir = self.logs_dir / "screenshots"
        self.artifacts_dir = self.logs_dir / "artifacts"
        
        # יצירת תיקיות לוגים
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📱 WhatsApp Delivery initialized (dry_run={dry_run}, service={service_url})")
        
        # בדיקת חיבור לשרת
        self._wait_for_service()
    
    def _wait_for_service(self, max_retries: int = 30, retry_delay: int = 2):
        """
        המתנה לזמינות השרת
        
        Args:
            max_retries: מספר ניסיונות מקסימלי
            retry_delay: זמן המתנה בין ניסיונות (שניות)
        """
        logger.info("🔍 Checking WhatsApp service availability...")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.service_url}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ready'):
                        logger.info("✅ WhatsApp service is ready!")
                        return
                    elif data.get('hasQR'):
                        logger.warning("⚠️ WhatsApp requires QR code scan!")
                        logger.info(f"📱 Please scan QR code or check: {self.service_url}/qr")
                    else:
                        logger.info(f"⏳ WhatsApp is initializing... ({attempt + 1}/{max_retries})")
            except requests.exceptions.RequestException as e:
                if attempt == 0:
                    logger.warning(f"⚠️ Cannot connect to WhatsApp service at {self.service_url}")
                    logger.info("💡 Make sure to start the Node.js server first:")
                    logger.info(f"   cd whatsapp_service && npm install && npm start")
                
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        
        raise WhatsAppDeliveryError(
            f"WhatsApp service is not ready after {max_retries} attempts. "
            f"Please check the Node.js server at {self.service_url}"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        קבלת סטטוס השרת
        
        Returns:
            מילון עם מצב השרת
        """
        try:
            response = requests.get(f"{self.service_url}/status", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"❌ Error getting status: {e}")
            return {"ready": False, "error": str(e)}
    
    def send_text(self, chat_name: str, message: str) -> bool:
        """
        שליחת הודעת טקסט
        
        Args:
            chat_name: שם הצ'אט/קבוצה
            message: טקסט ההודעה
            
        Returns:
            True אם ההודעה נשלחה בהצלחה
        """
        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would send text to '{chat_name}': {message[:50]}...")
            return True
        
        try:
            logger.info(f"💬 Sending text message to: {chat_name}")
            
            response = requests.post(
                f"{self.service_url}/send/text",
                json={
                    "chat": chat_name,
                    "message": message
                },
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                logger.info(f"✅ Text message sent successfully to: {chat_name}")
                return True
            else:
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"❌ Failed to send text: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending text message: {e}", exc_info=True)
            return False
    
    def send_file(
        self,
        file_path: str,
        chat_name: str,
        caption: str = "",
        file_type: str = "unknown",
        telegram_user_id: int = None,
        telegram_fallback_callback = None
    ) -> Dict[str, Any]:
        """
        שליחת קובץ בודד לוואטסאפ עם multi-stage fallback
        
        Args:
            file_path: נתיב לקובץ
            chat_name: שם הצ'אט/קבוצה
            caption: כותרת (caption) לקובץ / template payload
            file_type: סוג הקובץ (לצורכי לוג)
            telegram_user_id: מזהה משתמש בטלגרם (לצורך fallback)
            telegram_fallback_callback: פונקציה לקריאה במקרה של fallback לטלגרם
            
        Returns:
            Dict עם תוצאות מפורטות: {success, delivered_via, attempts, should_send_telegram, ...}
        """
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'delivered_via': 'failed'
            }
        
        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would send file to '{chat_name}': {file_path}")
            return {
                'success': True,
                'delivered_via': 'dry_run'
            }
        
        try:
            logger.info(f"📤 Sending {file_type} to '{chat_name}': {Path(file_path).name}")
            
            # המרה לנתיב מוחלט
            abs_file_path = str(Path(file_path).absolute())
            
            # קבלת גודל וסוג קובץ
            file_size_mb = os.path.getsize(abs_file_path) / (1024 * 1024)
            
            # זיהוי MIME type
            ext = Path(abs_file_path).suffix.lower()
            mime_map = {
                '.mp4': 'video/mp4', '.avi': 'video/x-msvideo', '.mov': 'video/quicktime',
                '.mkv': 'video/x-matroska', '.webm': 'video/webm',
                '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4',
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp'
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')
            
            # שליחה עם enhanced endpoint
            response = requests.post(
                f"{self.service_url}/send/enhanced",
                json={
                    "file_path": abs_file_path,
                    "wa_chat_id": chat_name,
                    "template_payload": caption,
                    "mime_type": mime_type,
                    "file_size_mb": file_size_mb,
                    "tg_target": telegram_user_id
                },
                timeout=300  # 5 דקות למקרה של retries
            )
            
            response.raise_for_status()
            result = response.json()
            
            # לוג מפורט של התוצאה
            delivered_via = result.get('delivered_via', 'unknown')
            
            if result.get('success'):
                logger.info(f"✅ Successfully delivered via: {delivered_via}")
                logger.info(f"   Attempts: {result.get('attempts', {})}")
                return result
            
            # לא הצליח ב-WhatsApp
            logger.warning(f"⚠️ WhatsApp delivery failed: {delivered_via}")
            logger.warning(f"   Final error: {result.get('final_error', 'Unknown')}")
            logger.warning(f"   Attempts: {result.get('attempts', {})}")
            
            # אם יש צורך ב-Telegram fallback
            if result.get('should_send_telegram'):
                logger.info("📨 Telegram fallback required")
                
                if telegram_fallback_callback and callable(telegram_fallback_callback):
                    telegram_payload = result.get('telegram_payload', {})
                    try:
                        logger.info("📤 Calling Telegram fallback callback...")
                        telegram_result = telegram_fallback_callback(
                            user_id=telegram_user_id,
                            file_path=telegram_payload.get('file_path'),
                            template_text=telegram_payload.get('template_payload', ''),
                            failure_summary=telegram_payload.get('failure_summary', '')
                        )
                        
                        if telegram_result:
                            logger.info("✅ Telegram fallback succeeded")
                            result['telegram_sent'] = True
                        else:
                            logger.error("❌ Telegram fallback failed")
                            result['telegram_sent'] = False
                    except Exception as tg_error:
                        logger.error(f"❌ Telegram fallback error: {tg_error}", exc_info=True)
                        result['telegram_sent'] = False
                        result['telegram_error'] = str(tg_error)
                else:
                    logger.warning("⚠️ No Telegram fallback callback provided")
            
            return result
                
        except Exception as e:
            error_reason = str(e)
            logger.error(f"❌ Error sending file {file_path}: {error_reason}", exc_info=True)
            return {
                'success': False,
                'error': error_reason,
                'delivered_via': 'failed'
            }
    
    def send_files(
        self,
        files: List[Dict[str, str]],
        chat_name: str,
        credits_text: str = "",
        telegram_user_id: int = None,
        telegram_fallback_callback = None
    ) -> Dict[str, bool]:
        """
        שליחת מספר קבצים לוואטסאפ עם multi-stage fallback
        
        Args:
            files: רשימת מילונים עם מפתחות: file_path, file_type, caption
            chat_name: שם הצ'אט/קבוצה
            credits_text: טקסט קרדיטים (יישלח עם התמונה)
            telegram_user_id: מזהה משתמש בטלגרם (לצורך fallback)
            telegram_fallback_callback: פונקציה לקריאה במקרה של fallback לטלגרם
            
        Returns:
            מילון עם תוצאות: {file_path: success}
        """
        results = {}
        
        logger.info(f"📤 Starting WhatsApp delivery to '{chat_name}' ({len(files)} files)")
        
        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would send {len(files)} files")
            for file_info in files:
                results[file_info.get('file_path', '')] = True
            return results
        
        # שליחה של כל קובץ בנפרד עם הלוגיקה המשודרגת
        for file_info in files:
            file_path = file_info.get('file_path')
            file_type = file_info.get('file_type', 'unknown')
            caption = file_info.get('caption', '')
            
            if not file_path:
                logger.warning("⚠️ Skipping file with no path")
                continue
            
            # הוספת קרדיטים לכותרות תמונות
            if file_type == 'image' and credits_text:
                if caption:
                    caption = f"{caption}\n\n{credits_text}"
                else:
                    caption = credits_text
            
            # שליחת הקובץ באמצעות send_file המשודרג
            result = self.send_file(
                file_path=file_path,
                chat_name=chat_name,
                caption=caption,
                file_type=file_type,
                telegram_user_id=telegram_user_id,
                telegram_fallback_callback=telegram_fallback_callback
            )
            
            # שמירת התוצאה
            abs_path = str(Path(file_path).absolute())
            if isinstance(result, dict):
                results[abs_path] = result.get('success', False)
            else:
                # fallback למקרה של פורמט ישן
                results[abs_path] = bool(result)
        
        # סיכום
        success_count = sum(1 for v in results.values() if v)
        failed_count = len(results) - success_count
        
        if failed_count > 0:
            logger.warning(f"📊 Delivery complete: {success_count}/{len(files)} succeeded, {failed_count} failed")
        else:
            logger.info(f"📊 Delivery complete: {success_count}/{len(files)} files sent successfully")
        
        return results
    
    def close(self):
        """סגירת החיבור (placeholder לתאימות עם הקוד הישן)"""
        logger.info("📱 WhatsApp Delivery closed")
