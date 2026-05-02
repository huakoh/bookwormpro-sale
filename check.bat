@echo off
chcp 65001 >nul
title BookwormPRO 安装诊断

echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║         BookwormPRO 安装诊断                          ║
echo   ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"
python scripts\check.py

pause
