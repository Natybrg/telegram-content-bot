# ⚠️ בעיות נפוצות ופתרונות

## 🔴 PeerIdInvalid בהעלאה לערוצים

### תסמינים:
- תמונה ו-MP3 נשלחים בהצלחה
- וידאו נכשל עם שגיאה: `PeerIdInvalid`
- בלוגים: `❌ [TELEGRAM → CHANNEL] ערוץ XXX לא נגיש: PeerIdInvalid`

### ✅ הפתרון שנמצא (2026-01-12):

**הבעיה:** היוזרבוט צריך הרשאת **"Add Admins"** (הוספת מנהלים חדשים) בערוץ!

**צעדי פתרון:**

1. **פתח את הערוץ בטלגרם** (כמנהל ראשי)
2. לחץ על שם הערוץ ← **Administrators** (מנהלים)
3. **מצא את היוזרבוט** (המספר שב-`PHONE_NUMBER` מקובץ `.env`)
4. לחץ על **Edit Admin** (עריכת מנהל)
5. **וודא שמסומן:** ✅ **Add Admins** (הוספת מנהלים חדשים)
6. **שמור** את השינויים
7. **הפעל מחדש** את הבוט (`Ctrl+C` ואז `python main.py`)

### למה זה קורה?

Telegram API דורש הרשאת "Add Admins" כדי לתת גישה מלאה לפרטי הערוץ דרך API. 
זה **לא באג** - זה feature אבטחה!

### הרשאות מומלצות ליוזרבוט:

בכל ערוץ שהבוט צריך לפרסם אליו, תן ליוזרבוט:

- ✅ **Post Messages** (פרסום הודעות)
- ✅ **Edit Messages** (עריכת הודעות)  
- ✅ **Delete Messages** (מחיקת הודעות)
- ✅ **Add Admins** (הוספת מנהלים) ⭐ **קריטי!**
- ✅ **Manage Chat** (ניהול צ'אט)
- ✅ **Send Media** (שליחת מדיה)

**תיעוד מלא:** `docs/PEERID_SOLUTION.md`

---

## 🟡 WhatsApp לא מתחבר

### תסמינים:
- `❌ WhatsApp service unavailable`
- הבוט לא שולח לוואטסאפ

### פתרון:

1. ודא ש-Node.js service רץ:
   ```bash
   cd whatsapp_service
   npm start
   ```

2. סרוק את ה-QR קוד:
   ```
   פתח: http://localhost:3000/qr
   סרוק עם WhatsApp ← Linked Devices
   ```

3. בדוק סטטוס:
   ```
   http://localhost:3000/status
   ```

---

## 🟡 FFmpeg לא נמצא

### תסמינים:
- `❌ FFmpeg not found`
- המרות וידאו נכשלות

### פתרון:

#### Windows:
```bash
winget install FFmpeg
```

#### Linux/Mac:
```bash
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # Mac
```

ודא ש-FFmpeg בנתיב:
```bash
ffmpeg -version
```

---

## 🟡 הורדת וידאו מ-YouTube נכשלת

### תסמינים:
- `WARNING: No supported JavaScript runtime`
- הורדות אטיות/נכשלות

### פתרון:

התקן Deno (JS runtime מומלץ):

#### Windows:
```powershell
irm https://deno.land/install.ps1 | iex
```

#### Linux/Mac:
```bash
curl -fsSL https://deno.land/install.sh | sh
```

**עדכן yt-dlp:**
```bash
pip install --upgrade yt-dlp
```

---

## 🟢 קובץ גדול מדי

### Telegram:
- מקסימום: **2GB** (דרך userbot)
- מקסימום: **50MB** (דרך bot רגיל)

### WhatsApp:
- וידאו: **70MB** (אוטומטי מדחוס)
- אודיו: **16MB** (אוטומטי מדחוס)
- תמונה: **5MB**

הבוט מטפל בדחיסה אוטומטית ב-WhatsApp service.

---

## 🔧 בדיקות נוספות

### בדוק לוגים:
```bash
tail -f bot.log
```

### בדוק שהכל רץ:
```bash
# Terminal 1: Bot
python main.py

# Terminal 2: WhatsApp
cd whatsapp_service
npm start
```

### הפעל מחדש הכל:
```bash
# עצור הכל (Ctrl+C)
# נקה session files
rm -f *.session*
# הפעל מחדש
python main.py
```

---

## 📞 עזרה נוספת

- **לוגים:** `bot.log`
- **תיעוד טכני:** `docs/`
- **בעיות ידועות:** `docs/BUGS_FOUND.md`
- **פתרונות:** `docs/PEERID_SOLUTION.md`

---

**עודכן:** 2026-01-12 - הוסף פתרון PeerIdInvalid
