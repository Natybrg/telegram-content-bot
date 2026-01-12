# 🧹 מדריך ניקוי - קבצים שניתן למחוק לאחר הפיתוח

מדריך זה מסביר אילו קבצים ותיקיות ניתן למחוק בבטחה לאחר שסיימת את שלב הפיתוח.

## ✅ קבצים שניתן למחוק בבטחה

### 1. קבצי Python Cache (נוצרים אוטומטית)
**ניתן למחוק - ייווצרו מחדש אוטומטית**

```
__pycache__/                    # תיקיית שורש
plugins/__pycache__/
services/__pycache__/
services/channels/__pycache__/
services/media/__pycache__/
services/whatsapp/__pycache__/
```

**למה?** קבצי bytecode של Python. נוצרים אוטומטית בעת הרצת הקוד.

**איך למחוק?**
```bash
# Windows PowerShell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# או ידנית - מחק את כל התיקיות __pycache__
```

---

### 2. קבצי Log ישנים
**ניתן למחוק - ייווצרו מחדש בעת הרצה**

```
bot.log                          # לוג ראשי (בשורש)
logs/whatsapp/artifacts/*.json  # קבצי שגיאות ישנים
logs/whatsapp/screenshots/*.png # צילומי מסך של שגיאות
```

**למה?** לוגים ישנים לא נחוצים בייצור. הלוגים ייווצרו מחדש בעת הרצה.

**איך למחוק?**
```bash
# Windows PowerShell
Remove-Item bot.log -ErrorAction SilentlyContinue
Remove-Item logs\whatsapp\artifacts\*.json -ErrorAction SilentlyContinue
Remove-Item logs\whatsapp\screenshots\*.png -ErrorAction SilentlyContinue
```

---

### 3. תיקיית whatsapp_session/ (Session ישן)
**ניתן למחוק - אם יש לך כבר whatsapp_service/whatsapp_auth/**

```
whatsapp_session/               # כל התיקייה (גדולה מאוד!)
```

**למה?** נראה כמו session ישן של Chrome/Puppeteer. אם יש לך כבר `whatsapp_service/whatsapp_auth/` שעובד, זה לא נחוץ.

**⚠️ אזהרה:** אם זה ה-session היחיד שלך שעובד, אל תמחק!

**איך למחוק?**
```bash
# Windows PowerShell
Remove-Item whatsapp_session -Recurse -Force
```

---

### 4. קבצים זמניים בתיקיית downloads/
**ניתן למחוק - נמחקים אוטומטית אחרי 60 שניות, אבל אפשר לנקות ידנית**

```
downloads/*.mp3
downloads/*.jpg
downloads/*.png
downloads/*.mp4
# כל הקבצים בתיקייה (אבל השאר את התיקייה עצמה!)
```

**למה?** קבצים זמניים שנשמרו מהרצות קודמות. נמחקים אוטומטית אחרי 60 שניות, אבל אפשר לנקות ידנית.

**איך למחוק?**
```bash
# Windows PowerShell
Remove-Item downloads\* -Exclude .gitkeep -ErrorAction SilentlyContinue
```

---

### 5. קבצי Test Output (אם יש)
**ניתן למחוק**

```
test_output/
*.test.mp4
*.test.mp3
*.test.jpg
```

**למה?** קבצי פלט מטסטים.

---

## ⚠️ קבצים שלא למחוק (חשובים!)

### קבצי Session (אימות)
```
telegram_bot.session
telegram_userbot.session
whatsapp_service/whatsapp_auth/
```

**למה?** קבצי אימות. אם תמחק אותם, תצטרך להתחבר מחדש!

---

### קבצי Configuration
```
.env
config.py
channels.json
templates.json
ENV_TEMPLATE.txt
```

**למה?** קבצי הגדרות. חיוניים לפעולה!

---

### קבצי Cookie (אם צריך)
```
cookies.txt
```

**למה?** אם אתה משתמש ב-cookies להורדה מ-YouTube, זה נחוץ. אם לא, אפשר למחוק.

---

## 📋 סקריפט ניקוי אוטומטי

יצרתי סקריפט ניקוי שיכול לעשות את כל זה אוטומטית:

### `scripts/cleanup_dev_files.bat` (Windows)
```batch
@echo off
echo ========================================
echo   ניקוי קבצי פיתוח
echo ========================================
echo.

echo 🗑️  מוחק קבצי __pycache__...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo ✅ הושלם

echo.
echo 🗑️  מוחק לוגים ישנים...
if exist bot.log del /q bot.log
if exist logs\whatsapp\artifacts\*.json del /q logs\whatsapp\artifacts\*.json
if exist logs\whatsapp\screenshots\*.png del /q logs\whatsapp\screenshots\*.png
echo ✅ הושלם

echo.
echo 🗑️  מנקה תיקיית downloads...
for %%f in (downloads\*) do if not "%%f"=="downloads\.gitkeep" del /q "%%f"
echo ✅ הושלם

echo.
echo ========================================
echo ✅ ניקוי הושלם!
echo ========================================
echo.
echo ⚠️  הערה: לא נמחקו:
echo    - קבצי .session (אימות)
echo    - תיקיית whatsapp_session/ (בדוק ידנית)
echo    - קובץ cookies.txt (אם נחוץ)
echo.
pause
```

---

## 🎯 המלצות לפי שלב

### לפני העלאה לייצור (Production)
1. ✅ מחק כל `__pycache__/`
2. ✅ מחק לוגים ישנים
3. ✅ נקה `downloads/`
4. ✅ בדוק אם `whatsapp_session/` נחוץ
5. ✅ בדוק אם `cookies.txt` נחוץ

### לפני גיבוי (Backup)
1. ✅ שמור קבצי `.session`
2. ✅ שמור `whatsapp_service/whatsapp_auth/`
3. ✅ שמור `.env`
4. ✅ שמור `channels.json` ו-`templates.json`

### לפני העלאה ל-Git
1. ✅ ודא ש-`.gitignore` מעודכן
2. ✅ ודא שאין קבצים רגישים (`.env`, `.session`)
3. ✅ ודא שאין קבצים גדולים מיותרים

---

## 📊 גודל משוער של קבצים שניתן למחוק

- `__pycache__/` - כמה MB (תלוי בגודל הפרויקט)
- `whatsapp_session/` - **מאות MB עד GB!** (תיקייה גדולה מאוד)
- `logs/` - כמה MB עד GB (תלוי בכמות הלוגים)
- `downloads/` - תלוי בקבצים שהורדו

**סה"כ:** יכול לחסוך **GB רבים** של מקום!

---

## 🔄 ניקוי אוטומטי

הבוט מנקה אוטומטית:
- קבצים ב-`downloads/` אחרי 60 שניות
- סשנים ישנים אחרי 24 שעות
- רשימות קבצים ישנות

אבל קבצי cache ולוגים לא נמחקים אוטומטית - צריך לנקות ידנית.

---

**עודכן לאחרונה:** ינואר 2026

