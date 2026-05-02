@echo off
chcp 65001 >nul
title BookwormPRO 卸载

echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║         BookwormPRO 卸载                              ║
echo   ╚══════════════════════════════════════════════════════╝
echo.
echo   将删除以下内容：
echo     · ~/.bookwormpro/skills/  （所有技能文件）
echo     · ~/.bookwormpro/SOUL.md  （灵魂文件）
echo     · ~/.bookwormpro/CLAUDE.md
echo.
echo   ⚠ 你的 .env (API Key) 和 config.yaml 不会被删除
echo.

set /p CONFIRM="  确认卸载？输入 yes 继续: "

if /i not "%CONFIRM%"=="yes" (
    echo   已取消。
    pause
    exit /b 0
)

echo.
echo   正在卸载...

if exist "%USERPROFILE%\.bookwormpro\skills" (
    rmdir /s /q "%USERPROFILE%\.bookwormpro\skills"
    echo   ✅ 技能文件已删除
) else (
    echo   ⚪ 技能目录不存在
)

if exist "%USERPROFILE%\.bookwormpro\SOUL.md" (
    del /q "%USERPROFILE%\.bookwormpro\SOUL.md"
    echo   ✅ SOUL.md 已删除
)

if exist "%USERPROFILE%\.bookwormpro\CLAUDE.md" (
    del /q "%USERPROFILE%\.bookwormpro\CLAUDE.md"
    echo   ✅ CLAUDE.md 已删除
)

if exist "%USERPROFILE%\.claude\SOUL.md" (
    del /q "%USERPROFILE%\.claude\SOUL.md"
    echo   ✅ ~/.claude/SOUL.md 已删除
)

echo.
echo   🎉 卸载完成。
echo   📝 .env 和 config.yaml 已保留，可手动删除：
echo      %USERPROFILE%\.bookwormpro\.env
echo      %USERPROFILE%\.bookwormpro\config.yaml
echo.
pause
