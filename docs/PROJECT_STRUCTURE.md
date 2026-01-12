# 📂 מבנה הפרויקט - Project Structure

מסמך זה מסביר את המבנה המאורגן של הפרויקט.

## 🗂️ תיקיות ראשיות

### `/` - שורש הפרויקט
קבצים ראשיים:
- `main.py` - נקודת הכניסה הראשית של הבוט
- `config.py` - הגדרות מרכזיות וטעינת משתני סביבה
- `requirements.txt` - תלויות Python
- `README.md` - תיעוד ראשי
- `ENV_TEMPLATE.txt` - תבנית לקובץ `.env`
- `channels.json` - הגדרות ערוצי טלגרם
- `templates.json` - תבניות תוכן

### `/plugins/` - פלאגינים (Pyrogram Handlers)
מכיל את כל ה-handlers של הבוט:
- `start.py` - פקודות בסיסיות (`/start`, `/help`, `/status`)
- `content_creator.py` - הלוגיקה הראשית ליצירת תוכן
- `queue_commands.py` - ניהול תור עיבוד
- `settings.py` - הגדרות ותבניות

### `/services/` - שירותים
מכיל את כל הלוגיקה העסקית:

#### `/services/media/` - עיבוד מדיה
- `youtube.py` - הורדה מ-YouTube (dual quality)
- `ffmpeg_utils.py` - כלי עזר ל-FFmpeg (המרות, codec checks)
- `audio.py` - עיבוד MP3 (תגיות ID3, תמונות)
- `image.py` - עיבוד תמונות (הוספת קרדיטים)
- `utils.py` - כלי עזר כלליים
- `error_handler.py` - טיפול בשגיאות

#### `/services/channels/` - ניהול ערוצים
- `manager.py` - ניהול ערוצי טלגרם
- `sender.py` - שליחה לערוצים
- `storage.py` - אחסון הגדרות ערוצים

#### `/services/whatsapp/` - שירות WhatsApp
- `delivery.py` - שליחה ל-WhatsApp דרך Node.js service

#### שירותים נוספים
- `context.py` - AppContext (singleton לניהול bot/userbot)
- `processing_queue.py` - תור עיבוד אסינכרוני
- `rate_limiter.py` - הגבלת קצב בקשות
- `templates.py` - ניהול תבניות
- `user_states.py` - ניהול מצבי משתמשים

### `/downloads/` - קבצים זמניים
תיקייה לקבצים שהורדו/עובדו. הקבצים נמחקים אוטומטית לאחר 60 שניות.

### `/data/` - נתונים זמניים
תיקייה לקבצי session ונתונים זמניים אחרים:
- קבצי `.session` של Pyrogram (מוזנחים ב-git)
- קבצים זמניים אחרים

### `/logs/` - לוגים
תיקייה לקבצי לוגים:
- `bot.log` - לוג ראשי (בשורש הפרויקט)
- `logs/whatsapp/` - לוגים של שירות WhatsApp

### `/docs/` - תיעוד
מכיל את כל קבצי התיעוד:
- `ANALYSIS_REPORT.md` - דוח ניתוח פרויקט
- `BUGS_FOUND.md` - רשימת באגים שנמצאו
- `CODE_REVIEW.md` - סקירת קוד
- `DEEP_ANALYSIS_REPORT.md` - ניתוח מעמיק
- `CHANNELS_GUIDE.md` - מדריך ערוצים
- `WHATSAPP_DEBUG_FILES.md` - תיעוד דיבוג WhatsApp
- `PROJECT_STRUCTURE.md` - קובץ זה

### `/tests/` - טסטים
מכיל קבצי טסט:
- `test_dual_download.py` - טסט להורדה כפולה מ-YouTube
- `test_whatsapp_upload.py` - טסט להעלאה ל-WhatsApp

### `/scripts/` - סקריפטים
מכיל סקריפטים שימושיים:
- `start_whatsapp_service.bat` - הפעלת שירות WhatsApp (Windows)
- `update_whatsapp_service.bat` - עדכון שירות WhatsApp (Windows)

### `/whatsapp_service/` - שירות Node.js
שירות Node.js נפרד לשליחה ל-WhatsApp:
- `server.js` - שרת Express
- `package.json` - תלויות Node.js
- `whatsapp_auth/` - קבצי אימות WhatsApp (מוזנח ב-git)

## 📝 קבצים מיוחדים

### `.gitignore`
מגדיר אילו קבצים לא לכלול ב-git:
- קבצי `.env` (משתני סביבה)
- קבצי `.session` (אימות טלגרם)
- תיקיית `downloads/` (קבצים זמניים)
- תיקיית `data/` (נתונים זמניים)
- תיקיית `logs/` (לוגים)
- תיקיית `whatsapp_session/` (סשן WhatsApp)
- תיקיית `node_modules/` (תלויות Node.js)

### `.gitkeep`
קבצים ריקים שמונעים מ-git להתעלם מתיקיות ריקות:
- `downloads/.gitkeep`
- `data/.gitkeep`
- `docs/.gitkeep`
- `tests/.gitkeep`
- `scripts/.gitkeep`

## 🔄 זרימת עבודה

1. **התחלה**: `main.py` → טעינת config → אתחול bot/userbot
2. **פקודה**: משתמש שולח פקודה → `plugins/` מטפלים
3. **עיבוד**: `services/` מבצעים את העבודה
4. **תוצאה**: קבצים נשמרים ב-`downloads/` → נשלחים → נמחקים

## 📦 תלויות

### Python (`requirements.txt`)
- `pyrogram` - ספריית טלגרם
- `yt-dlp` - הורדה מ-YouTube
- `mutagen` - עריכת תגיות MP3
- `Pillow` - עיבוד תמונות
- `ffmpeg-python` - wrapper ל-FFmpeg
- ועוד...

### Node.js (`whatsapp_service/package.json`)
- `whatsapp-web.js` - שליחה ל-WhatsApp
- `express` - שרת HTTP
- `puppeteer` - אוטומציה של דפדפן
- ועוד...

## 🎯 עקרונות ארגון

1. **הפרדת אחריות**: כל תיקייה עם תפקיד ברור
2. **קוד נקי**: כל קובץ עם מטרה אחת
3. **תיעוד**: כל פונקציה מתועדת
4. **טסטים**: טסטים נפרדים מהקוד הראשי
5. **סקריפטים**: סקריפטים שימושיים במקום אחד
6. **תיעוד**: כל התיעוד במקום אחד

## 🔧 תחזוקה

### הוספת פיצ'ר חדש
1. הוסף קוד ב-`services/` או `plugins/`
2. עדכן תיעוד ב-`docs/` אם צריך
3. הוסף טסט ב-`tests/` אם רלוונטי

### תיקון באג
1. מצא את הקובץ הרלוונטי
2. תקן את הבאג
3. בדוק עם טסטים
4. עדכן תיעוד אם צריך

### עדכון תיעוד
1. עדכן את `README.md` אם שינוי משמעותי
2. עדכן את `docs/` אם יש שינוי טכני
3. עדכן את `PROJECT_STRUCTURE.md` אם המבנה השתנה

---

**עודכן לאחרונה**: ינואר 2026

