# 🔧 סקריפטים - Scripts

תיקייה זו מכילה סקריפטים שימושיים להפעלה ותחזוקה של הבוט.

## 📋 קבצי סקריפט

### `start_whatsapp_service.bat`
הפעלת שירות WhatsApp (Windows).

**שימוש:**
```bash
scripts\start_whatsapp_service.bat
```

הסקריפט:
- עובר לתיקיית `whatsapp_service/`
- מפעיל את שירות Node.js עם `npm start`

### `update_whatsapp_service.bat`
עדכון שירות WhatsApp (Windows).

**שימוש:**
```bash
scripts\update_whatsapp_service.bat
```

הסקריפט:
- עובר לתיקיית `whatsapp_service/`
- מריץ `npm install` לעדכון תלויות
- מציג סיכום שינויים

### `cleanup_dev_files.bat`
ניקוי קבצי פיתוח (Windows).

**שימוש:**
```bash
scripts\cleanup_dev_files.bat
```

הסקריפט:
- מוחק כל תיקיות `__pycache__/`
- מוחק לוגים ישנים (`bot.log`, `logs/whatsapp/`)
- מנקה תיקיית `downloads/`
- **לא מוחק** קבצים חשובים (`.session`, `.env`, וכו')

**⚠️ אזהרה:** הסקריפט לא מוחק:
- קבצי `.session` (אימות)
- תיקיית `whatsapp_session/` (בדוק ידנית)
- קובץ `cookies.txt` (אם נחוץ)
- קבצי `.env` (הגדרות)

ראה `docs/CLEANUP_GUIDE.md` לפרטים נוספים.

## ⚙️ דרישות

- Node.js מותקן במערכת
- תיקיית `whatsapp_service/` קיימת
- `package.json` בתיקיית `whatsapp_service/`

## 📝 הערות

- הסקריפטים מיועדים ל-Windows (`.bat`)
- עבור Linux/Mac, ניתן ליצור גרסאות `.sh` דומות

