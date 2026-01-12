@echo off
echo ========================================
echo 🔄 Updating WhatsApp Service
echo ========================================
echo.

cd /d "%~dp0whatsapp_service"

echo 📦 Installing/Updating dependencies...
call npm install

echo.
echo ========================================
echo ✅ Update Complete!
echo ========================================
echo.
echo 📝 Changes made:
echo   - Upgraded whatsapp-web.js to v1.25.0+
echo   - Increased Node.js heap to 8GB
echo   - Added garbage collection support
echo   - Enhanced Puppeteer configuration
echo   - Improved large file handling (100MB+)
echo.
echo 🚀 To start the service:
echo    npm start
echo.
pause
