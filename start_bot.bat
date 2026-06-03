@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   微信机器人 - 一键启动
echo ========================================
echo.

echo [1/3] 停止旧进程...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
echo        已完成

echo [2/3] 清理缓存...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc >nul 2>&1
echo        已完成

echo [3/3] 启动机器人...
echo.
python main.py
pause
