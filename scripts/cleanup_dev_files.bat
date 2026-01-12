@echo off
chcp 65001 >nul
echo ========================================
echo   🧹 ניקוי קבצי פיתוח
echo ========================================
echo.

echo 🗑️  מוחק קבצי __pycache__...
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    echo    מוחק: %%d
    rd /s /q "%%d" 2>nul
)
echo ✅ הושלם - קבצי cache נמחקו
echo.

echo 🗑️  מוחק לוגים ישנים...
if exist bot.log (
    del /q bot.log
    echo    נמחק: bot.log
)
if exist logs\whatsapp\artifacts\*.json (
    del /q logs\whatsapp\artifacts\*.json
    echo    נמחקו: קבצי artifacts
)
if exist logs\whatsapp\screenshots\*.png (
    del /q logs\whatsapp\screenshots\*.png
    echo    נמחקו: צילומי מסך
)
echo ✅ הושלם - לוגים ישנים נמחקו
echo.

echo 🗑️  מנקה תיקיית downloads...
set count=0
for %%f in (downloads\*) do (
    if not "%%f"=="downloads\.gitkeep" (
        del /q "%%f" 2>nul
        set /a count+=1
    )
)
if %count% GTR 0 (
    echo    נמחקו %count% קבצים
) else (
    echo    אין קבצים למחיקה
)
echo ✅ הושלם - תיקיית downloads נוקתה
echo.

echo ========================================
echo ✅ ניקוי הושלם!
echo ========================================
echo.
echo ⚠️  הערות חשובות:
echo    - קבצי .session לא נמחקו (אימות)
echo    - תיקיית whatsapp_session/ לא נמחקה (בדוק ידנית)
echo    - קובץ cookies.txt לא נמחק (אם נחוץ)
echo    - קבצי .env לא נמחקו (הגדרות)
echo.
echo 💡 טיפ: אם אתה בטוח, תוכל למחוק ידנית:
echo    - whatsapp_session/ (אם יש לך whatsapp_service/whatsapp_auth/)
echo    - cookies.txt (אם לא צריך להורדות מ-YouTube)
echo.
pause

