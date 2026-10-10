@echo off
chcp 65001 >nul
title Cloudflare Tunnel - Cat Nhac MP3 & Video MP4
cd /d "%~dp0"

echo ====================================================
echo   KHOI DONG CLOUDFLARE TUNNEL (DUONG LINK CLOUD CHO DIEN THOAI)
echo ====================================================
echo.
echo Dang mo duong ham Cloudflare cho cong 8765...
echo Vui long xem duong link https://*.trycloudflare.com ben duoi de mo tren dien thoai:
echo.
cloudflared.exe tunnel --url http://127.0.0.1:8765
pause
