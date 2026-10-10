@echo off
chcp 65001 >nul
title Deploy len Cloudflare Pages - taivideonhanh.pages.dev
echo =======================================================
echo   DANG DEPLOY LEN CLOUDFLARE PAGES: taivideonhanh
echo =======================================================
echo.
cd /d "%~dp0"
call npx wrangler pages deploy cloudflare_pages_dist --project-name=taivideonhanh
echo.
pause