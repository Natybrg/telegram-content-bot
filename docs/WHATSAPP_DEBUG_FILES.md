# קבצים לשליחה לפתרון בעיית שליחת סרטונים ל-WhatsApp

## 📋 רשימת קבצים נדרשים

### ✅ קבצים חובה (Core Files)

1. **`whatsapp_service/server.js`**
   - הקוד הראשי של שרת Node.js
   - מכיל את הפונקציות `sendWhatsAppAsMedia` ו-`sendWhatsAppAsDocument`
   - זה הקובץ המרכזי שמטפל בשליחה כוידאו

2. **`services/whatsapp/delivery.py`**
   - הקוד Python שמתקשר עם השרת Node.js
   - שולח בקשות HTTP לשרת

3. **`whatsapp_service/package.json`**
   - רשימת התלויות והגרסאות
   - חשוב לראות איזו גרסה של `whatsapp-web.js` בשימוש

### 📝 קבצים נוספים (מומלץ)

4. **`test_whatsapp_upload.py`**
   - קובץ הטסט שמראה את הבעיה
   - מכיל את הלוגיקה של attempt/fallback

5. **לוגים אחרונים** (אם יש):
   - `logs/whatsapp/artifacts/error_*.json` - קבצי שגיאות
   - לוגים מהקונסול של השרת Node.js

## 🔍 תיאור הבעיה

**הבעיה:** סרטונים נשלחים כמסמכים (documents) במקום כוידאו לצפייה ישירה (media)

**מה קורה:**
- `sendWhatsAppAsMedia` נכשל עם שגיאה: `"Evaluation failed: t"`
- השרת עובר אוטומטית ל-`sendWhatsAppAsDocument` ומצליח
- התוצאה: הקובץ נשלח כמסמך ולא כוידאו

**פרטים טכניים:**
- גרסת whatsapp-web.js: ^1.25.0
- הבעיה מתרחשת גם בקבצים קטנים (7.5MB)
- `MessageMedia.fromFilePath` + `chat.sendMessage` נכשל
- `client.sendMessage` גם נכשל
- Native file upload לא מוצא את `input[type="file"]` ב-DOM

## 📦 איך לשלוח

1. צור תיקיית ZIP עם הקבצים הבאים:
   ```
   whatsapp_debug/
   ├── whatsapp_service/
   │   ├── server.js
   │   └── package.json
   ├── services/
   │   └── whatsapp/
   │       └── delivery.py
   ├── test_whatsapp_upload.py
   └── WHATSAPP_DEBUG_FILES.md (הקובץ הזה)
   ```

2. הוסף לוגים אחרונים (אם יש):
   - קבצי error מ-`logs/whatsapp/artifacts/`
   - לוגים מהקונסול של השרת

3. הוסף תיאור קצר:
   - גודל הקובץ שניסית לשלוח
   - שם הצ'אט ב-WhatsApp
   - האם השרת Node.js רץ
   - האם יש שגיאות בקונסול

## 🎯 נקודות מפתח לבדיקה

1. **שורה 320-487 ב-`server.js`** - הפונקציה `sendWhatsAppAsMedia`
2. **שורה 717-908 ב-`server.js`** - הפונקציה `deliver` (האורקסטרטור)
3. **שורה 347-395 ב-`server.js`** - הניסיון לשלוח כ-MEDIA
4. **שורה 397-487 ב-`server.js`** - Fallback ל-native upload

## 💡 הערות נוספות

- הקוד מנסה 3 ניסיונות עם `client.sendMessage`
- אם נכשל, עובר ל-native file upload דרך Puppeteer
- Native upload מנסה לפתוח את הצ'אט דרך Store או URL
- אם file input לא נמצא, נכשל ועובר ל-DOCUMENT

