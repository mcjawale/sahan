@echo off
cd /d "%~dp0"

rem Make sure Python and the required libraries exist (first run only)
where python >nul 2>nul
if errorlevel 1 (
    msg * "Python is not installed. Install it from https://www.python.org/downloads/ (tick 'Add to PATH') then run this again." 
    exit /b 1
)
python -c "import flask, reportlab" >nul 2>nul
if errorlevel 1 (
    echo Installing Sahan Fleet components...
    python -m pip install -r requirements.txt
)

rem Start the server invisibly in the background (skip if already running)
netstat -ano | findstr "LISTENING" | findstr /c:":5000 " >nul
if errorlevel 1 (
    start "" pythonw app.py
    ping -n 4 127.0.0.1 >nul
)

rem Open in a fresh Chrome browser window
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if exist "%CHROME%" (
    start "" "%CHROME%" --new-window http://localhost:5000
) else (
    start "" http://localhost:5000
)
exit