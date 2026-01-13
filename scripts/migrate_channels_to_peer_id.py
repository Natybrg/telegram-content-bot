"""
Migration Script: Convert channel IDs to peer_id (Base64)
מיגרציה מפורמט ישן (ID) לפורמט חדש (peer_id_b64)
"""

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path

# הוספת שורש הפרויקט ל-PYTHONPATH
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from pyrogram import Client
from core import API_ID, API_HASH, USERBOT_SESSION_NAME, PHONE_NUMBER, ROOT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_channels():
    """
    מבצע מיגרציה של כל הערוצים מ-ID ל-peer_id_b64
    """
    logger.info("🚀 Starting channel migration...")
    
    # טעינת קובץ channels.json
    channels_file = ROOT_DIR / "channels.json"
    if not channels_file.exists():
        logger.error(f"❌ channels.json not found at {channels_file}")
        return
    
    with open(channels_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"📋 Loaded channels.json")
    
    # יצירת userbot client
    userbot = Client(
        name=USERBOT_SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        workdir=str(ROOT_DIR)
    )
    
    try:
        await userbot.start()
        logger.info("✅ Userbot started")
    except Exception as e:
        if "database is locked" in str(e) or "locked" in str(e).lower():
            logger.error("❌ Database is locked - the bot/userbot is probably running!")
            logger.error("💡 Please stop the bot first, then run the migration script again.")
            logger.error("   You can stop it with Ctrl+C in the terminal where it's running.")
            return
        else:
            raise
    
    try:
        # מיגרציה של repository.telegram
        migrated_count = 0
        failed_count = 0
        
        if "repository" in data and "telegram" in data["repository"]:
            new_telegram_list = []
            
            for item in data["repository"]["telegram"]:
                if isinstance(item, str):
                    # זה ID ישן - נמיר אותו
                    channel_ref = item
                    logger.info(f"🔄 Migrating channel: {channel_ref}")
                    
                    try:
                        # קבלת chat object
                        chat = await userbot.get_chat(channel_ref)
                        
                        # יצירת peer_id_b64
                        peer_id_b64 = base64.b64encode(chat.peer_id).decode("utf-8")
                        
                        # יצירת entry חדש
                        new_entry = {
                            "peer_id_b64": peer_id_b64,
                            "title": chat.title or "Unknown Channel",
                            "legacy_id": channel_ref  # שמירת ה-ID הישן למקרה של rollback
                        }
                        
                        new_telegram_list.append(new_entry)
                        migrated_count += 1
                        
                        logger.info(f"✅ Migrated: {channel_ref} → {chat.title} (peer_id_b64: {peer_id_b64[:20]}...)")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to migrate {channel_ref}: {e}")
                        failed_count += 1
                        # נשמור את ה-ID הישן עם סימון שגיאה
                        new_telegram_list.append({
                            "peer_id_b64": None,
                            "title": channel_ref,
                            "legacy_id": channel_ref,
                            "is_legacy": True,
                            "migration_error": str(e)
                        })
                
                elif isinstance(item, dict):
                    # זה כבר פורמט חדש או legacy שכבר סומן
                    if item.get("peer_id_b64"):
                        # כבר יש peer_id_b64 - נשמור אותו
                        new_telegram_list.append(item)
                        logger.info(f"ℹ️ Already migrated: {item.get('title', 'Unknown')}")
                    elif item.get("legacy_id"):
                        # זה legacy - ננסה למיגרציה
                        legacy_id = item["legacy_id"]
                        logger.info(f"🔄 Migrating legacy channel: {legacy_id}")
                        
                        try:
                            chat = await userbot.get_chat(legacy_id)
                            peer_id_b64 = base64.b64encode(chat.peer_id).decode("utf-8")
                            
                            new_entry = {
                                "peer_id_b64": peer_id_b64,
                                "title": chat.title or item.get("title", "Unknown Channel"),
                                "legacy_id": legacy_id
                            }
                            
                            new_telegram_list.append(new_entry)
                            migrated_count += 1
                            
                            logger.info(f"✅ Migrated legacy: {legacy_id} → {chat.title} (peer_id_b64: {peer_id_b64[:20]}...)")
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to migrate legacy {legacy_id}: {e}")
                            failed_count += 1
                            new_telegram_list.append(item)  # נשמור את ה-entry הישן
                    else:
                        # entry לא מוכר - נשמור אותו כמו שהוא
                        new_telegram_list.append(item)
                        logger.warning(f"⚠️ Unknown entry format: {item}")
            
            data["repository"]["telegram"] = new_telegram_list
        
        # מיגרציה של template_links
        if "template_links" in data:
            for template_name, links in data["template_links"].items():
                if "telegram" in links:
                    new_telegram_links = []
                    
                    for item in links["telegram"]:
                        if isinstance(item, str):
                            # בדיקה אם זה Base64 (אורך טיפוסי) או legacy ID
                            if len(item) > 20 and not item.lstrip('-').isdigit():
                                # זה נראה כמו Base64 - נשמור אותו
                                new_telegram_links.append(item)
                                logger.info(f"ℹ️ Template link already Base64: {item[:20]}...")
                            else:
                                # זה legacy ID - נחפש את ה-peer_id_b64 ב-repository
                                found_peer_id_b64 = None
                                
                                for repo_item in data["repository"]["telegram"]:
                                    if isinstance(repo_item, dict):
                                        if repo_item.get("legacy_id") == item:
                                            found_peer_id_b64 = repo_item.get("peer_id_b64")
                                            break
                                
                                if found_peer_id_b64:
                                    new_telegram_links.append(found_peer_id_b64)
                                    logger.info(f"✅ Migrated template link: {item} → {found_peer_id_b64[:20]}...")
                                else:
                                    logger.warning(f"⚠️ Could not find peer_id_b64 for template link: {item}")
                                    # נשמור את ה-ID הישן - ייתכן שזה username
                                    new_telegram_links.append(item)
                        else:
                            new_telegram_links.append(item)
                    
                    links["telegram"] = new_telegram_links
        
        # שמירת הקובץ המעודכן
        backup_file = channels_file.with_suffix('.json.backup')
        logger.info(f"💾 Creating backup: {backup_file}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Saving migrated data to {channels_file}")
        with open(channels_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info("=" * 60)
        logger.info(f"✅ Migration completed!")
        logger.info(f"   • Migrated: {migrated_count} channels")
        logger.info(f"   • Failed: {failed_count} channels")
        logger.info(f"   • Backup saved to: {backup_file}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error during migration: {e}", exc_info=True)
        raise
    finally:
        try:
            if userbot.is_connected:
                await userbot.stop()
                logger.info("✅ Userbot stopped")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(migrate_channels())
