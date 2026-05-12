@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ============================================================
echo   SCU 二课 Web 版  -  http://127.0.0.1:5000
echo ============================================================
start http://127.0.0.1:5000
D:\Software\Anaconda\envs\scu-plus\python.exe "%~dp0app.py"
pause
