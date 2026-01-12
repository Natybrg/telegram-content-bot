# 📋 מסמך פרומפטים לתיקון ושיפור הפרויקט

**תאריך יצירה:** 2026-01-12  
**גרסה:** 1.0

---

## 🔴 חלק 1: תיקוני באגים קריטיים



### פרומפט #2: תיקון Race Condition בתור העיבוד

**עדיפות:** 🟠 גבוהה

**תיאור הבעיה:**
ב-`services/processing_queue.py` יש אפשרות ל-race condition אם שני משתמשים מוסיפים task בו-זמנית.

**פרומפט מלא:**

```
אני צריך לתקן race condition פוטנציאלי בתור עיבוד המשתמשים שלי.

## הקשר:
הבוט שלי משתמש ב-`asyncio.Queue` ב-`services/processing_queue.py` לניהול תור FIFO של משתמשים.
הקוד נמצא בשורות 20-212.

## הבעיה הפוטנציאלית:
במתודה `add_to_queue()` (שורות 30-81), יש בדיקה אם המשתמש כבר בתור:
```python
# שורה 33
if user_id == self.current_user_id:
    return "עובד עכשיו"

# שורה 36-40
for item in list(self.queue._queue):
    if item.user_id == user_id:
        return "כבר בתור"
```

הבעיה: אם שני משתמשים (או אותו משתמש פעמיים) קוראים ל-`add_to_queue()` **בדיוק באותו זמן**, שניהם עשויים לעבור את הבדיקה ולהתווסף לתור.

## מה שאני צריך ממך:

### שלב 1 - ניתוח
נתח:
1. האם זו באמת בעיה ב-asyncio? (single-threaded event loop)
2. מתי זה יכול לקרות בפועל?
3. מה התוצאה אם זה יקרה?
4. האם יש race conditions נוספים בקוד?

### שלב 2 - פתרון
ספק פתרון שמשתמש ב-**asyncio.Lock** או **threading.Lock**:

```python
# services/processing_queue.py

class ProcessingQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current_user_id: Optional[int] = None
        self.is_processing = False
        self._lock = asyncio.Lock()  # 🆕 נעשה שינוי כאן
        # ...
    
    async def add_to_queue(self, user_id: int, callback: Callable, message, status_msg=None):
        async with self._lock:  # 🆕 נעשה שינוי כאן
            # כל הקוד הקיים
            # ...
```

עדכן את כל המקומות הרלוונטיים בקוד שצריכים הגנה.

### שלב 3 - טסטים
ספק קוד לטסט שמדמה גישה מקבילה:

```python
# tests/test_race_condition.py
import asyncio
import pytest
from services.processing_queue import processing_queue

@pytest.mark.asyncio
async def test_concurrent_queue_additions():
    """בודק שאין race condition בהוספה לתור"""
    # הרצת 100 tasks במקביל עם אותו user_id
    # ...
```

### שלב 4 - וולידציה
1. הרץ את הטסטים
2. ודא שהקוד עדיין עובד כרגיל
3. ודא שאין deadlocks
4. ספק לוגים לוולידציה

בקשות נוספות:
- ✅ אל תשנה את API הקיים
- ✅ הסבר למה Lock עדיף על RLock במקרה הזה
- ✅ תן דוגמאות לשימוש ב-Lock נכון
```

---

### פרומפט #3: תיקון Timeout בהמרת FFmpeg

**עדיפות:** 🟠 גבוהה

**תיאור הבעיה:**
FFmpeg timeouts לא מחושבים נכון לקבצים גדולים עם קודקים כבדים (AV1/VP9).

**פרומפט מלא:**

```
אני צריך לשפר את לוגיקת ה-timeout בהמרות FFmpeg.

## הקשר:
הבוט שלי מוריד סרטונים מ-YouTube, ממיר אותם ל-H.264+AAC עם FFmpeg.
הקוד נמצא ב:
- `services/media/youtube.py` - חישוב timeout (שורות 29-75)
- `services/media/ffmpeg_utils.py` - המרות FFmpeg

## הבעיה:
1. Timeout קצר מדי לקבצים גדולים (\u003e500MB) עם AV1/VP9
2. ההמרה נכשלת אחרי timeout גם אם FFmpeg עדיין עובד

## דוגמה לשגיאה:
```
⏱️ [YOUTUBE] Timeout כולל: 600s (10 דקות)
❌ [YOUTUBE] TimeoutError - אבל FFmpeg עדיין רץ ברקע!
```

## מה שאני צריך ממך:

### שלב 1 - ניתוח
נתח את `calculate_timeout()` ב-`youtube.py`:
1. האם הנוסחאות נכונות?
2. האם יש קודקים נוספים שצריך להתחשב בהם?
3. האם צריך להתחשב ב-resolution (1080p vs 720p)?
4. האם צריך להתחשב ב-bitrate היעד?

### שלב 2 - שיפור חישוב Timeout
עדכן את `calculate_timeout()`:

```python
def calculate_timeout(
    file_size_mb: float, 
    operation_type: str = "download",
    video_codec: str = "",
    audio_codec: str = "",
    resolution: tuple = None,  # 🆕 (width, height)
    target_bitrate: int = None  # 🆕 kbps
) -> int:
    """
    מחשב timeout דינמי חכם יותר
    """
    # ניתוח מעמיק של הפרמטרים
    # חישוב timeout מדויק יותר
    # החזרת ערך + הסבר ללוג
```

### שלב 3 - המרה חכמה
שפר את `convert_to_compatible_format()` ב-`ffmpeg_utils.py`:
1. בדוק קודקים **לפני** ההמרה
2. אם כבר H.264+AAC, דלג על המרה (copy streams)
3. אם רק video צריך המרה, אל תמיר audio
4. הוסף progress callback מפורט יותר

### שלב 4 - Graceful Timeout
במקום להרוג את FFmpeg בכוח, תן לו לסיים:

```python
try:
    result = await asyncio.wait_for(ffmpeg_task, timeout=dynamic_timeout)
except asyncio.TimeoutError:
    # 🆕 תן ל-FFmpeg 30 שניות נוספות לסיים
    logger.warning("⏱️ Timeout - מחכה 30 שניות נוספות...")
    await asyncio.wait_for(ffmpeg_task, timeout=30)
```

### שלב 5 - בדיקה
ספק:
1. טבלה של timeouts משוערים לגדלים שונים
2. קוד טסט עם קבצים שונים
3. השוואה לפני/אחרי השיפור

דרישות:
- ✅ תואם לקוד הקיים
- ✅ fallback לערכים ישנים אם המידע חסר
- ✅ לוגים מפורטים
```

---

### פרומפט #4: תיקון Memory Leak בקאש של YouTube

**עדיפות:** 🟡 בינונית

**תיאור הבעיה:**
ב-`services/media/youtube.py` יש cache למידע על וידאו שלא מנוקה אף פעם.

**פרומפט מלא:**

```
יש לי memory leak בקאש של פונקציית `get_video_info()`.

## הקשר:
ב-`services/media/youtube.py` שורות 676-742, יש cache למניעת קריאות מיותרות ל-YouTube:

```python
_video_info_cache = {}
_video_info_cache_timestamps = {}
_video_info_cache_ttl = 300  # 5 דקות
```

## הבעיה:
הקאש גדל לאינסוף ולא מנוקה אף פעם. אחרי שבוע עם 1000 סרטונים, זה יכול לתפוס הרבה זיכרון.

## מה שאני צריך ממך:

### שלב 1 - ניתוח
1. חשב כמה זיכרון תופס פריט אחד בקאש
2. חשב כמה זיכרון יתפוס הקאש אחרי שבוע (נניח 100 סרטונים ביום)
3. האם זו באמת בעיה או שאני מגזים?

### שלב 2 - פתרון עם LRU Cache
המר ל-`functools.lru_cache`:

```python
from functools import lru_cache
import time

# 🆕 גרסה חדשה
@lru_cache(maxsize=100)  # שמור רק 100 סרטונים אחרונים
async def get_video_info(url: str, cookies_path: str = "cookies.txt"):
    # קוד קיים...
```

**אבל!** יש בעיה: `lru_cache` לא עובד עם async. ספק פתרון.

### שלב 3 - פתרון חלופי עם TTL Cache
יצור `TTLCache` מותאם:

```python
# services/cache.py (חדש)
import asyncio
import time
from typing import Dict, Any, Optional
from collections import OrderedDict

class TTLCache:
    """
    Cache עם TTL + LRU eviction
    """
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        # מלא את הפונקציה
        
    async def set(self, key: str, value: Any):
        # מלא את הפונקציה
        
    async def cleanup_expired(self):
        # מלא את הפונקציה
        
    async def periodic_cleanup(self):
        """רץ ברקע ומנקה פריטים ישנים כל דקה"""
        # מלא את הפונקציה
```

### שלב 4 - שימוש בקאש
עדכן את `get_video_info()`:

```python
# services/media/youtube.py

from services.cache import TTLCache

video_info_cache = TTLCache(max_size=100, ttl_seconds=300)

async def get_video_info(url: str, cookies_path: str = "cookies.txt", use_cache: bool = True):
    if not use_cache:
        return await _get_video_info_uncached(url, cookies_path)
    
    cached = await video_info_cache.get(url)
    if cached:
        logger.debug(f"📦 [CACHE] Hit: {url}")
        return cached
    
    logger.debug(f"📦 [CACHE] Miss: {url}")
    info = await _get_video_info_uncached(url, cookies_path)
    await video_info_cache.set(url, info)
    return info
```

### שלב 5 - אתחול בסטארטאפ
ב-`main.py`, התחל cleanup תקופתי:

```python
# main.py
async def main():
    # ...
    
    # 🆕 התחל cache cleanup
    from services.media.youtube import video_info_cache
    asyncio.create_task(video_info_cache.periodic_cleanup())
    logger.info("✅ Cache cleanup worker started")
    
    # ...
```

### שלב 6 - מדדים
הוסף מדדים:
1. כמה hits/misses
2. גודל הקאש הנוכחי
3. פריטים שנוקו

דרישות:
- ✅ thread-safe (asyncio.Lock)
- ✅ לא לשבור API קיים
- ✅ טסטים
```

---

## 🟡 חלק 2: שיפורי ביצועים

### פרומפט #5: העברה ל-ProcessPoolExecutor עבור FFmpeg

**עדיפות:** 🟡 בינונית

**תיאור:**
FFmpeg חוסם את ה-event loop, צריך להריץ אותו ב-process נפרד.

**פרומפט מלא:**

```
אני צריך להעביר את FFmpeg לרוץ ב-ProcessPoolExecutor במקום ThreadPoolExecutor.

## הקשר:
כרגע ב-`config.py` יש `ThreadPoolExecutor`:
```python
class ExecutorManager:
    @classmethod
    def get_executor(cls, max_workers: int = 4):
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=max_workers)
```

## הבעיה:
FFmpeg הוא CPU-intensive ו-Python Threads לא משחררים את ה-GIL. זה חוסם את כל ה-event loop.

## מה שאני צריך ממך:

### שלב 1 - ניתוח
הסבר:
1. מה ההבדל בין ThreadPool ל-ProcessPool?
2. למה FFmpeg CPU-intensive?
3. מתי כדאי להשתמש ב-ThreadPool ומתי ב-ProcessPool?

### שלב 2 - יישום
יצור 2 executors:

```python
# config.py

class ExecutorManager:
    _thread_executor = None
    _process_executor = None
    
    @classmethod
    def get_thread_executor(cls, max_workers: int = 4):
        """עבור I/O operations (requests, WhatsApp, etc.)"""
        # ...
    
    @classmethod
    def get_process_executor(cls, max_workers: int = 2):
        """עבור CPU-intensive operations (FFmpeg, image processing)"""
        if cls._process_executor is None:
            cls._process_executor = ProcessPoolExecutor(max_workers=max_workers)
            atexit.register(cls.shutdown_process_executor)
        return cls._process_executor
    
    @classmethod
    def shutdown_all(cls):
        # סגור את שני ה-executors
```

### שלב 3 - עדכון קוד FFmpeg
עדכן את כל הקריאות ל-FFmpeg להשתמש ב-ProcessPool:

```python
# services/media/ffmpeg_utils.py

async def convert_to_compatible_format(input_path, output_path, progress_callback=None):
    executor = executor_manager.get_process_executor()  # 🆕
    # ...
```

### שלב 4 - Serialization
ודא ש-progress_callback serializable:
- אי אפשר להעביר async functions ל-ProcessPool
- צריך workaround עם queues או pipes

ספק פתרון מלא.

### שלב 5 - בדיקה
1. השווה ביצועים לפני/אחרי
2. בדוק CPU usage
3. בדוק event loop blocking

דרישות:
- ✅ תואם backward
- ✅ טיפול בשגיאות
```

---

### פרומפט #6: Batch Upload לערוצים

**עדיפות:** 🟢 נמוכה

**תיאור:**
כרגע כל קובץ נשלח בנפרד לכל ערוץ (סדרתי). אפשר לבצע במקביל.

**פרומפט מלא:**

```
אני רוצה לשפר את מהירות ההעלאה לערוצים מרובים.

## הקשר:
ב-`services/channels/sender.py` שורות 384-426, יש לולאה שעוברת על ערוצים:

```python
for channel in other_channels:
    try:
        await send_method(**params)
        # ...
```

זה סדרתי (serial). אם יש 10 ערוצים, זה לוקח פי 10 זמן.

## מה שאני צריך ממך:

### שלב 1 - ניתוח
1. למה זה סדרתי ולא מקביל?
2. מה היתרונות והחסרונות של מקביליות?
3. האם Telegram מגביל rate?

### שלב 2 - פתרון מקביל
עדכן ל-`asyncio.gather()`:

```python
# שליחה לשאר הערוצים במקביל
if other_channels:
    tasks = []
    for channel in other_channels:
        task = send_to_single_channel(channel_client, channel, file_id, caption, ...)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # טיפול בתוצאות
```

יצור את `send_to_single_channel()`.

### שלב 3 - Rate Limiting
הוסף rate limiter:
- מקסימום 20 הודעות לשנייה
- delay בין batches

### שלב 4 - בדיקה
השווה זמני העלאה לפני/אחרי.

דרישות:
- ✅ לא לשבור קוד קיים
- ✅ טיפול בשגיאות
```

---

## 🔵 חלק 3: שיפורי תשתית

### פרומפט #7: מעבר מ-JSON ל-SQLite

**עדיפות:** 🔵 ארוך-טווח

**פרומפט:**

```
אני רוצה להעביר את המערכת מ-JSON files ל-SQLite.

## הקשר:
כרגע נתונים נשמרים ב:
- `templates.json` - תבניות
- `channels.json` - ערוצים וקישורים
- Session data ב-memory בלבד

## מה שאני צריך ממך:

### שלב 1 - תכנון
תכנן את מבנה הDB:

```sql
-- schema.sql

CREATE TABLE templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,  -- 'telegram' או 'whatsapp'
    identifier TEXT NOT NULL,  -- ID, username, או שם קבוצה
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, identifier)
);

CREATE TABLE template_channel_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    FOREIGN KEY (template_name) REFERENCES templates(name),
    FOREIGN KEY (channel_id) REFERENCES channels(id),
    UNIQUE(template_name, channel_id)
);

CREATE TABLE user_sessions (
    user_id INTEGER PRIMARY KEY,
    state TEXT NOT NULL,
    data JSON,  -- כל הנתונים כ-JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE upload_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### שלב 2 - יישום
יצור:
1. `services/database.py` - connection manager
2. `services/models.py` - SQLAlchemy models
3. Migration script

### שלב 3 - עדכון קוד
המר:
1. `TemplateManager` להשתמש ב-DB
2. `ChannelsManager` להשתמש ב-DB
3. `UserStateManager` להשתמש ב-DB

### שלב 4 - Migration
יצור script שמעביר נתונים מ-JSON ל-DB.

### שלב 5 - Backward Compatibility
תמוך ב-fallback ל-JSON אם DB לא זמין.

דרישות:
- ✅ SQLite (לא PostgreSQL)
- ✅ SQLAlchemy ORM
- ✅ Migration scripts
- ✅ טסטים
```

---

### פרומפט #8: Health Monitoring System

**עדיפות:** 🔵 ארוך-טווח

**פרומפט:**

```
אני רוצה monitoring system לבוט.

## מטרה:
לדעת בזמן אמת:
- מה סטטוס כל השירותים (WhatsApp, FFmpeg, Telegram)
- כמה משתמשים בתור
- כמה uploads הצליחו/נכשלו
- כמה שטח דיסק נשאר

## מה שאני צריך ממך:

### שלב 1 - תכנון
תכנן מבנה:

```python
# services/health_monitor.py

class HealthMonitor:
    async def check_whatsapp_service(self) -> Dict:
        # בדוק ש-WhatsApp service זמין
        
    async def check_ffmpeg(self) -> Dict:
        # בדוק ש-FFmpeg מותקן וזמין
        
    async def check_disk_space(self) -> Dict:
        # בדוק שיש מספיק שטח ב-downloads/
        
    async def check_telegram_connection(self) -> Dict:
        # בדוק ש-bot ו-userbot מחוברים
        
    async def get_full_status(self) -> Dict:
        # אסוף את כל הסטטוסים
```

### שלב 2 - Dashboard
יצור פקודה `/health` שמחזירה:

```
🏥 **מצב מערכת**

🟢 **טלגרם:**
  • Bot: מחובר
  • Userbot: מחובר
  • Ping: 45ms

🟢 **WhatsApp:**
  • Service: פעיל
  • QR: מחובר
  • Uptime: 2d 14h

🟢 **FFmpeg:**
  • גרסה: 6.0
  • זמין: ✅

🟡 **דיסק:**
  • פנוי: 15GB / 100GB
  • אחוז: 15%

📊 **סטטיסטיקות:**
  • בתור: 2 משתמשים
  • הצלחות היום: 45
  • כשלונות היום: 3
```

### שלב 3 - Alerts
שלח התראה למנהל אם:
- WhatsApp נותק
- דיסק מלא (\u003e90%)
- יותר מ-5 משתמשים בתור

### שלב 4 - Metrics Export
ייצא metrics ל-Prometheus format (אופציונלי).

דרישות:
- ✅ בדיקה כל דקה
- ✅ cache תוצאות ל-30 שניות
- ✅ לא לחסום את ה-bot
```

---

## 📊 חלק 4: פרומפטים לתיעוד ובדיקה

### פרומפט #9: יצירת Unit Tests

**פרומפט:**

```
אני צריך unit tests למערכת.

## מה שאני צריך:

### שלב 1 - תשתית
הגדר:
1. `pytest` + `pytest-asyncio`
2. `conftest.py` עם fixtures
3. Mock objects ל-Telegram/WhatsApp

### שלב 2 - טסטים לפונקציות קריטיות
כתוב tests ל:
1. `process_content()` - 10 scenarios
2. `send_to_telegram_channels()` - 5 scenarios
3. `whatsapp.send_file()` - 5 scenarios
4. `update_mp3_tags()` - 5 scenarios
5. `download_youtube_video_dual()` - 5 scenarios

### שלב 3 - Coverage
הגע ל-70% coverage לפחות.

### שלב 4 - CI Integration
הוסף GitHub Actions workflow.

דרישות:
- ✅ pytest
- ✅ async tests
- ✅ mocking
- ✅ fixtures
```

---

### פרומפט #10: תיעוד API מלא

**פרומפט:**

```
אני צריך documentation מלא לכל הפרויקט.

## מה שאני צריך:

### שלב 1 - Docstrings
הוסף docstrings בפורמט Google לכל:
- פונקציות ציבוריות
- קלאסים
- מתודות

### שלב 2 - API Reference
יצור `docs/API_REFERENCE.md` עם:
- כל הפונקציות הציבוריות
- פרמטרים
- return values
- דוגמאות שימוש

### שלב 3 - Architecture Diagram
יצור תרשים ארכיטקטורה מפורט.

### שלב 4 - חכרות להתקנה סובל ופעולה
עדקן את ה-README.

דרישות:
- ✅ Sphinx/MkDocs (אופציונלי)
- ✅ דוגמאות קוד
- ✅ תרשימים
```

---

## 🎯 טבלת עדיפויות

| # | נושא | עדיפות | זמן משוער | תלות |
|---|------|---------|-----------|------|
| 1 | PeerIdInvalid תיקון | 🔴 קריטי | 2-3 שעות | אין |
| 2 | Race Condition | 🟠 גבוהה | 1-2 שעות | אין |
| 3 | FFmpeg Timeout | 🟠 גבוהה | 2-3 שעות | אין |
| 4 | Memory Leak Cache | 🟡 בינונית | 1-2 שעות | אין |
| 5 | ProcessPool FFmpeg | 🟡 בינונית | 3-4 שעות | #3 |
| 6 | Batch Upload | 🟢 נמוכה | 2-3 שעות | #1 |
| 7 | SQLite Migration | 🔵 ארוך | 1-2 ימים | אין |
| 8 | Health Monitoring | 🔵 ארוך | 1 יום | אין |
| 9 | Unit Tests | 🔵 ארוך | 2-3 ימים | #1-6 |
| 10 | תיעוד API | 🔵 ארוך | 1 יום | אין |

---

## 📝 הערות לשימוש

**איך להשתמש בפרומפטים:**

1. **העתק את הפרומפט המלא** (כולל כל הטקסט)
2. **הדבק ב-ChatGPT/Claude/Gemini**
3. **עקוב אחרי ההוראות** שהמודל נותן
4. **בדוק את הקוד** לפני שאתה משלב אותו
5. **הרץ טסטים** אחרי כל שינוי

**טיפים:**
- ✅ עבוד על פרומפט אחד בכל פעם
- ✅ התחל מהפרומפטים הקריטיים
- ✅ גבה את הקוד לפני שינויים
- ✅ בדוק שהבוט עובד אחרי כל שינוי

---

**סיום מסמך**
