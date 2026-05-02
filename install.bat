@echo off
chcp 65001 >nul
title BookwormPRO 安装向导

:: ═══════════════════════════════════════════
::  BookwormPRO — AI 智能助手技能包 安装程序
::  版本: 1.0  |  双击运行即可
:: ═══════════════════════════════════════════

echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║    ____              _                                ║
echo   ║   ^| __ )  ___   ___ ^| ^| _____      _____  _ __       ║
echo   ║   ^|  _ \ / _ \ / _ \^| ^|/ / \ \ /\ / / _ \^| '__^|      ║
echo   ║   ^| ^|_) ^| (_) ^| (_) ^| ^|  ^<  \ V  V / (_) ^| ^|        ║
echo   ║   ^|____/ \___/ \___/^|_^|\_\  \_/\_/ \___/^|_^|        ║
echo   ║                                                      ║
echo   ║         AI 智能助手技能包 · 一键安装                  ║
echo   ╚══════════════════════════════════════════════════════╝
echo.

:: ── 步骤 1: 检查 Python ──
echo   [1/3] 检查运行环境...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo   ❌ 未检测到 Python！
    echo.
    echo   请先安装 Python 3.10 或更高版本：
    echo   https://www.python.org/downloads/
    echo.
    echo   ⚠ 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   ✅ Python %PYVER% 已就绪

:: ── 步骤 2: 运行安装向导 ──
echo.
echo   [2/3] 启动安装向导...
echo.

cd /d "%~dp0"
python scripts\setup_wizard.py

if %errorlevel% neq 0 (
    echo.
    echo   ❌ 安装过程出错，请检查上方错误信息。
    pause
    exit /b 1
)

:: ── 步骤 3: 验证安装 ──
echo.
echo   [3/3] 验证安装...

python scripts\check.py

echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║                                                      ║
echo   ║   🎉 安装完成！                                      ║
echo   ║                                                      ║
echo   ║   下一步:                                            ║
echo   ║   1. 打开 docs\快速开始.html 查看教程                ║
echo   ║   2. 重启你的 AI 助手                                ║
echo   ║   3. 试试输入: bookworm自检                          ║
echo   ║                                                      ║
echo   ║   善读者，必善造。                                   ║
echo   ║                                                      ║
echo   ╚══════════════════════════════════════════════════════╝
echo.
pause
