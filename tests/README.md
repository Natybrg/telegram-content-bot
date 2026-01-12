# 🧪 טסטים - Tests

תיקייה זו מכילה קבצי טסט לבדיקת פונקציונליות הבוט.

## 📋 קבצי טסט

### `test_dual_download.py`
טסט להורדה כפולה מ-YouTube בשתי איכויות (1080p ו-720p).

**שימוש:**
```bash
python tests/test_dual_download.py
```

הטסט:
- מוריד סרטון בשתי איכויות
- בודק codec compatibility (H.264 + AAC)
- מציג מידע מפורט על הקבצים
- מאפשר מחיקה אוטומטית בסיום

### `test_whatsapp_upload.py`
טסט להעלאה ל-WhatsApp.

**שימוש:**
```bash
# טסט רגיל
python tests/test_whatsapp_upload.py

# טסט עם קובץ ספציפי
python tests/test_whatsapp_upload.py --file path/to/video.mp4

# טסט ללא שליחה אמיתית (dry-run)
python tests/test_whatsapp_upload.py --dry-run

# רשימת קבצים זמינים
python tests/test_whatsapp_upload.py --list

# בחירת הקובץ הגדול ביותר
python tests/test_whatsapp_upload.py --large

# שליחה כ-MEDIA בלבד (ללא fallback)
python tests/test_whatsapp_upload.py --media-only
```

הטסט:
- בודק תקינות קובץ
- קובע אסטרטגיית שליחה (MEDIA vs DOCUMENT)
- שולח ל-WhatsApp
- מציג תוצאות מפורטות

## ⚙️ דרישות

- כל התלויות מ-`requirements.txt` מותקנות
- FFmpeg מותקן במערכת
- שירות WhatsApp רץ (לטסט WhatsApp)
- קובץ `.env` מוגדר נכון

## 📝 הערות

- הטסטים משתמשים בקבצים מתיקיית `downloads/`
- הקבצים נשארים לאחר הטסט (אלא אם בוחרים למחוק)
- הטסטים לא משפיעים על הפעולה הרגילה של הבוט

