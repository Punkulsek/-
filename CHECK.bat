@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe goto missing
.venv\Scripts\python.exe -m cookiebot.app --check
set "result=%errorlevel%"
pause
exit /b %result%
:missing
echo INSTALL.bat를 먼저 실행하세요.
pause
exit /b 1
