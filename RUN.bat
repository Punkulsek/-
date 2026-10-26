@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe goto missing
.venv\Scripts\python.exe -m cookiebot.app
set "result=%errorlevel%"
echo 종료 코드: %result%. 오류는 logs 및 crash_logs에서 확인하세요.
pause
exit /b %result%
:missing
echo INSTALL.bat를 먼저 실행하세요.
pause
exit /b 1
