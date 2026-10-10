@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title Cắt Nhạc MP3 - Ghép Video MP4
cd /d "%~dp0"

echo ====================================================
echo   KHỞI ĐỘNG ỨNG DỤNG CẮT NHẠC MP3 & GHÉP VIDEO MP4
echo ====================================================
echo.
python app.py
pause
