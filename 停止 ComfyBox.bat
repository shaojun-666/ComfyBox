@echo off
title 停止 ComfyBox 控制台
setlocal

set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
if exist "%DIR%\config.bat" call "%DIR%\config.bat"
if not defined PORT set "PORT=8790"

echo 正在停止 ComfyBox 控制台（端口 %PORT%）...
set "FOUND="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
  set "FOUND=1"
)
if defined FOUND (
  echo 已停止。
) else (
  echo 控制台服务本来就没在运行。
)
echo 注意: 本操作不影响 ComfyUI 本体。
echo       需要释放显存/内存请双击「停止 ComfyUI (释放内存).bat」。
ping -n 4 127.0.0.1 >nul
