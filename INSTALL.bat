@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
py -3.11 -m venv .venv >logs\install.log 2>&1
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt >>logs\install.log 2>&1
if errorlevel 1 goto fail
echo 설치 완료. CHECK.bat를 실행하세요.
pause
exit /b 0
:fail
type logs\install.log
echo 설치 실패. Python 3.11 64비트와 Python Launcher 설치 여부를 확인하세요.
pause
exit /b 1
