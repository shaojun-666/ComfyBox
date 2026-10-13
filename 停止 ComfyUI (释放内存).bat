@echo off
title 停止 ComfyUI
setlocal

set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
if exist "%DIR%\config.bat" call "%DIR%\config.bat"
if not defined COMFY_PORT set "COMFY_PORT=8188"

echo 正在停止 ComfyUI（端口 %COMFY_PORT%）...
set "FOUND="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%COMFY_PORT%" ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
  set "FOUND=1"
)
if defined FOUND (
  echo 已停止，显存与内存已释放。
  echo 注意: 已打开的 ComfyUI 网页会显示连接失败，属正常现象; 图片文件不受影响。
) else (
  echo ComfyUI 本来就没在运行。
)
ping -n 4 127.0.0.1 >nul
