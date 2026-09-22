@echo off
rem Stop the Sahan Fleet server
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "LISTENING" ^| findstr /c:":5000 "') do taskkill /f /pid %%p >nul 2>&1
echo Sahan Fleet server stopped.
timeout /t 3 /nobreak >nul <nul
