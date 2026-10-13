@echo off
REM ============================================================
REM  ComfyBox 本地配置模板
REM  用法：把本文件复制为 config.bat，按需取消注释并改成你的实际路径。
REM  config.bat 不会被提交到版本库（已在 .gitignore 中忽略）。
REM
REM  默认值基于如下目录结构推导，若你的目录正是这样，则无需配置：
REM      <APP>\ComfyUI\    ComfyUI 本体
REM      <APP>\venv\       Python 虚拟环境
REM      <APP>\ComfyBox\   本控制台
REM ============================================================

REM ---- Python 虚拟环境解释器 ----
REM set "PYW=D:/ComfyUI/venv/Scripts/pythonw.exe"
REM set "PY=D:/ComfyUI/venv/Scripts/python.exe"

REM ---- 控制台端口（默认 8790）----
REM set "PORT=8790"

REM ---- ComfyUI 端口（默认 8188，停止脚本使用）----
REM set "COMFY_PORT=8188"

REM ---- AI 缓存根目录（默认 <APP>\AI-Cache）----
REM 用于 HF_HOME / CUDA_CACHE_PATH / torch 缓存等，避免占用系统盘。
REM set "COMYBOX_CACHE_DIR=D:/AI-Cache"
