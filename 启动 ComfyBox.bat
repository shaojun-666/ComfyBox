@echo off
title ComfyBox 启动器
setlocal

REM ============================================================
REM  ComfyBox 启动器（可移植版）
REM  预期目录结构：
REM      <APP>\ComfyUI\    ComfyUI 本体
REM      <APP>\venv\       Python 虚拟环境
REM      <APP>\ComfyBox\   本控制台（当前脚本所在目录）
REM  可选：本目录 config.bat 覆盖默认值（模板见 config.example.bat）
REM ============================================================

set "BOX=%~dp0"
if "%BOX:~-1%"=="\" set "BOX=%BOX:~0,-1%"
for %%I in ("%BOX%\..") do set "APP=%%~fI"

REM ---- 载入本地配置（不入版本库）----
if exist "%BOX%\config.bat" call "%BOX%\config.bat"

REM ---- 默认值（按上述目录结构推导，可被 config.bat 覆盖）----
if not defined PYW  set "PYW=%APP%\venv\Scripts\pythonw.exe"
if not defined PY   set "PY=%APP%\venv\Scripts\python.exe"
if not defined PORT set "PORT=8790"

set "PROFILE=%BOX%\browser-profile"
set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"

echo ============================================================
echo   ComfyBox  -  ComfyUI 本地控制台
echo ============================================================
echo.

REM ---- 0) 自检 ----
if not exist "%BOX%\server.py" (
  echo [错误] 找不到控制台后端:  %BOX%\server.py
  echo        请确认 ComfyBox 目录完整。
  pause
  exit /b 1
)
if not exist "%BOX%\index.html" (
  echo [错误] 找不到控制台页面:  %BOX%\index.html
  echo        请确认 ComfyBox 目录完整。
  pause
  exit /b 1
)
if not exist "%PYW%" if not exist "%PY%" (
  echo [错误] 找不到 Python 虚拟环境:
  echo        %PYW%
  echo        请检查目录结构，或在 config.bat 里设置 PYW / PY。
  pause
  exit /b 1
)
if not exist "%PYW%" set "PYW=%PY%"

REM ---- 1) 控制台服务（与 ComfyUI 各自独立，先起后不管）----
REM 用 netstat 判断端口，避免依赖外部脚本，也不走系统代理
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [1/3] 控制台已在运行，直接打开页面。
  goto :open
)

echo [1/3] 启动控制台服务（端口 %PORT%，无窗口后台运行）...
start "" "%PYW%" "%BOX%\server.py" --port %PORT% --autostart

REM ---- 2) 等服务就绪（用端口探测，比固定等待稳）----
echo [2/3] 等待服务就绪...
set "READY="
for /l %%i in (1,1,40) do if not defined READY call :waitport
if not defined READY (
  echo     [错误] 端口 %PORT% 未在 40 秒内就绪。
  echo            常见原因：Python 环境异常，或端口被占用。
  echo            可双击「停止 ComfyBox.bat」后重试，并查看 logs 目录。
)

REM ---- 3) 打开页面（用独立浏览器配置，数据留在本目录）----
:open
if not exist "%PROFILE%" mkdir "%PROFILE%"
echo [3/3] 打开控制台页面...
if exist "%EDGE%" goto :use_edge
if exist "%CHROME%" goto :use_chrome

echo     未找到 Edge / Chrome，改用系统默认浏览器。
start "" "http://127.0.0.1:%PORT%/"
goto :done

:use_edge
start "" "%EDGE%" --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "http://127.0.0.1:%PORT%/"
goto :done

:use_chrome
start "" "%CHROME%" --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "http://127.0.0.1:%PORT%/"
goto :done

:done
echo.
echo 完成。控制台地址:  http://127.0.0.1:%PORT%/
echo ComfyUI 正在后台加载模型（约 20-60 秒），加载好后工作台会自动出现。
echo.
echo 说明: 关闭本窗口不影响使用;
echo       停止 ComfyUI 释放内存 -^> 双击「停止 ComfyUI (释放内存).bat」
echo       停止控制台网页     -^> 双击「停止 ComfyBox.bat」
echo.
ping -n 7 127.0.0.1 >nul
exit /b 0

:waitport
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set "READY=1"
if not defined READY ping -n 2 127.0.0.1 >nul
goto :eof
