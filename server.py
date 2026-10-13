#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyBox - ComfyUI 本地控制台后端

纯 Python 标准库实现，零第三方依赖。职责：
  1. 静态托管 index.html（控制台界面本身）
  2. /api/status    聚合 ComfyUI 运行状态 / GPU / 显存 / 内存 / 队列
  3. /api/models    模型清单（checkpoints / loras / vae / controlnet ...）
  4. /api/gallery   输出目录图片列表
  5. /api/img       直读本地图片文件（ComfyUI 停止时也能看图）
  6. /api/start     启动 ComfyUI（pythonw 无黑窗，日志落文件）
  7. /api/stop      停止 ComfyUI（按端口找 PID 后结束）
  8. /api/log       查看 ComfyUI / ComfyBox 日志尾部
  9. /api/open      在资源管理器中打开输出目录
 10. /api/config    暴露路径等运行环境信息

设计原则：ComfyUI 与 ComfyBox 各自独立。关掉控制台不会杀掉 ComfyUI，
关掉 ComfyUI 也不影响控制台继续监控（状态栏会显示"已停止"）。
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------- 路径与常量

HERE = os.path.dirname(os.path.abspath(__file__))          # ...\ComfyUI\ComfyBox
APP = os.path.dirname(HERE)                                # ...\ComfyUI
COMFY_DIR = os.path.join(APP, "ComfyUI")                   # ComfyUI 代码根
VENV = os.path.join(APP, "venv")                           # 独立虚拟环境
VENV_PY = os.path.join(VENV, "Scripts", "python.exe")
VENV_PYW = os.path.join(VENV, "Scripts", "pythonw.exe")     # 无窗口解释器
MAIN_PY = os.path.join(COMFY_DIR, "main.py")
OUT_DIR = os.path.join(COMFY_DIR, "output")
TEMP_DIR = os.path.join(COMFY_DIR, "temp")
MODELS_DIR = os.path.join(COMFY_DIR, "models")
CUSTOM_NODES = os.path.join(COMFY_DIR, "custom_nodes")
LOG_DIR = os.path.join(HERE, "logs")
BOX_LOG = os.path.join(LOG_DIR, "comfbox.log")
COMFY_LOG = os.path.join(LOG_DIR, "comfyui.log")
WORKFLOW_DIR = os.path.join(COMFY_DIR, "user", "default", "workflows")

DEF_BOX_PORT = 8790
DEF_COMFY_PORT = 8188

# 缓存类目录统一收口，避免 C 盘被慢慢吃掉。
# 根目录优先级：环境变量 COMYBOX_CACHE_DIR > <APP>\AI-Cache。
# （启动脚本的 config.bat 里设置 COMYBOX_CACHE_DIR，即可把缓存指向任意盘。）
CACHE_ROOT = (os.environ.get("COMYBOX_CACHE_DIR") or "").strip() or os.path.join(APP, "AI-Cache")

CACHE_ENV = {
    "HF_HOME": os.path.join(CACHE_ROOT, "huggingface"),
    "CUDA_CACHE_PATH": os.path.join(CACHE_ROOT, "cuda"),
    "CUDA_CACHE_MAXSIZE": "2147483648",
    "TORCHINDUCTOR_CACHE_DIR": os.path.join(CACHE_ROOT, "torchinductor"),
    "TORCH_EXTENSIONS_DIR": os.path.join(CACHE_ROOT, "torch-extensions"),
    "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
    "PYTHONPYCACHEPREFIX": os.path.join(CACHE_ROOT, "pycache"),
}

MODEL_SLOTS = [
    ("checkpoints", "主模型 / Checkpoint"),
    ("loras", "LoRA"),
    ("vae", "VAE"),
    ("controlnet", "ControlNet"),
    ("embeddings", "Embedding"),
    ("clip_vision", "CLIP Vision"),
    ("unet", "UNet / 扩散模型"),
    ("upscale_models", "放大模型"),
]

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}

COMFY_PORT = DEF_COMFY_PORT
STARTING_SINCE = 0.0        # >0 表示正在启动中（时间戳）

# 访问本机 127.0.0.1 时绕开系统代理（VPN / 加速器常会劫持 127.0.0.1 请求）
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------- 基础工具


def ensure_dirs():
    for d in (LOG_DIR,):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass


def port_open(port, host="127.0.0.1", timeout=0.6):
    """TCP 探测端口是否可连接。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, int(port))) == 0
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def run_cmd(args, timeout=15):
    """执行外部命令并返回解码后的文本。

    注意：中文 Windows 的 netstat / taskkill 输出是 GBK，而 Python 3.13 的
    text=True 默认按 UTF-8 解码。解码失败会让 subprocess 的读取线程崩掉，
    导致 .stdout 直接变成 None。所以这里取原始字节自行解码。
    """
    try:
        r = subprocess.run(
            args, capture_output=True, timeout=timeout,
            creationflags=0x08000000,  # CREATE_NO_WINDOW，不闪黑框
        )
    except Exception:
        return "", -1
    raw = r.stdout or b""
    text = raw.decode("utf-8", "replace")
    if "\ufffd" in text:            # UTF-8 解不通就按本地代码页再试
        text = raw.decode("gbk", "replace")
    return text, r.returncode


def pid_on_port(port):
    """从 netstat -ano 里解析出监听某端口的进程 PID。"""
    out, _code = run_cmd(["netstat", "-ano", "-p", "TCP"], timeout=10)
    if not out:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].endswith(":" + str(port)):
                try:
                    return int(parts[4])
                except ValueError:
                    continue
    return None


def human(size):
    """字节数转人类可读。"""
    try:
        size = float(size)
    except Exception:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return ("%.0f %s" % (size, unit)) if unit == "B" else ("%.2f %s" % (size, unit))
        size /= 1024.0


def http_json(url, timeout=3.0):
    """GET 一个本地 JSON 接口，失败返回 None。

    必须显式禁用代理：本机装了 HTTP_PROXY（如 VPN / 加速器）时，urllib 会
    把 127.0.0.1 的请求也丢给代理，结果是永远连不上。
    """
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with _LOCAL_OPENER.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def tail_lines(path, n=200):
    """读取文本文件最后 n 行（容忍文件不存在 / 编码异常）。"""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, max(8192, n * 400))
            f.seek(size - block)
            data = f.read()
        text = data.decode("utf-8", "replace")
        lines = text.splitlines()
        return lines[-n:]
    except Exception as e:
        return ["<读取日志失败: %s>" % e]


def safe_join(root, *parts):
    """拼接路径并确保没有跳出 root（防目录穿越）。"""
    p = os.path.normpath(os.path.join(root, *[x for x in parts if x]))
    root_abs = os.path.normpath(root)
    if p != root_abs and not p.lower().startswith(root_abs.lower() + os.sep):
        return None
    return p


# ---------------------------------------------------------------- 业务逻辑


def comfy_status():
    """聚合 ComfyUI 运行状态。"""
    global STARTING_SINCE
    running = port_open(COMFY_PORT)
    info = {
        "running": running,
        "starting": bool(STARTING_SINCE and (time.time() - STARTING_SINCE) < 180 and not running),
        "port": COMFY_PORT,
        "url": "http://127.0.0.1:%d" % COMFY_PORT,
        "pid": None,
        "queue_running": 0,
        "queue_pending": 0,
        "version": None,
        "python": None,
        "torch": None,
        "ram_total": None,
        "ram_free": None,
        "gpu": None,
        "vram_total": None,
        "vram_free": None,
    }
    if not running:
        if STARTING_SINCE and (time.time() - STARTING_SINCE) >= 180:
            STARTING_SINCE = 0.0
        return info

    STARTING_SINCE = 0.0
    info["pid"] = pid_on_port(COMFY_PORT)

    stats = http_json("http://127.0.0.1:%d/system_stats" % COMFY_PORT, timeout=4)
    if isinstance(stats, dict):
        sysinfo = stats.get("system", {}) or {}
        info["version"] = sysinfo.get("comfyui_version")
        info["python"] = (sysinfo.get("python_version") or "").split(" ")[0] or None
        info["torch"] = sysinfo.get("pytorch_version")
        info["ram_total"] = sysinfo.get("ram_total")
        info["ram_free"] = sysinfo.get("ram_free")
        devs = stats.get("devices") or []
        if devs:
            d0 = devs[0]
            info["gpu"] = (d0.get("name") or "").replace(" : cudaMallocAsync", "")
            info["vram_total"] = d0.get("vram_total")
            info["vram_free"] = d0.get("vram_free")

    q = http_json("http://127.0.0.1:%d/queue" % COMFY_PORT, timeout=4)
    if isinstance(q, dict):
        info["queue_running"] = len(q.get("queue_running") or [])
        info["queue_pending"] = len(q.get("queue_pending") or [])
    return info


def list_models():
    """扫描 models 目录，返回各槽位模型清单。"""
    out = []
    for key, label in MODEL_SLOTS:
        d = os.path.join(MODELS_DIR, key)
        items = []
        if os.path.isdir(d):
            for root, _dirs, files in os.walk(d):
                for fn in files:
                    if fn.startswith("put_") or fn.startswith("."):
                        continue
                    fp = os.path.join(root, fn)
                    rel = os.path.relpath(fp, d).replace("\\", "/")
                    try:
                        sz = os.path.getsize(fp)
                    except OSError:
                        sz = 0
                    if sz == 0:
                        continue
                    items.append({"name": rel, "size": sz, "sizeText": human(sz)})
            items.sort(key=lambda x: -x["size"])
        out.append({"key": key, "label": label, "dir": d, "exists": os.path.isdir(d), "items": items})
    return out


def list_workflows():
    """列出用户工作流目录下的工作流，按修改时间倒序。

    跳过 .index.json 之类的隐藏文件，并尽量读出节点数，
    这样在控制台里就能一眼看出某个工作流值不值得打开。
    """
    items = []
    if not os.path.isdir(WORKFLOW_DIR):
        return items

    for fn in os.listdir(WORKFLOW_DIR):
        if fn.startswith(".") or not fn.lower().endswith(".json"):
            continue
        fp = os.path.join(WORKFLOW_DIR, fn)
        if not os.path.isfile(fp):
            continue
        try:
            st = os.stat(fp)
        except OSError:
            continue

        nodes = None
        archived = False
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                nodes = len(data.get("nodes") or [])
        except Exception:
            pass   # 不是合法工作流 JSON，也照样列出来

        items.append({
            "file": fn,
            "name": os.path.splitext(fn)[0],
            "size": st.st_size,
            "sizeText": human(st.st_size),
            "mtime": int(st.st_mtime),
            "nodes": nodes,
        })

    items.sort(key=lambda x: -x["mtime"])
    return items


def list_gallery(limit=120):
    """列出输出目录里的图片，按修改时间倒序。"""
    items = []
    if os.path.isdir(OUT_DIR):
        for root, _dirs, files in os.walk(OUT_DIR):
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in IMAGE_EXT:
                    continue
                fp = os.path.join(root, fn)
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                sub = os.path.relpath(root, OUT_DIR).replace("\\", "/")
                if sub == ".":
                    sub = ""
                items.append({
                    "name": fn,
                    "sub": sub,
                    "size": st.st_size,
                    "sizeText": human(st.st_size),
                    "mtime": st.st_mtime,
                    "timeText": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                })
    items.sort(key=lambda x: -x["mtime"])
    return items[:limit], len(items)


def start_comfy():
    """启动 ComfyUI：无窗口、日志落文件、与控制器解耦。"""
    global STARTING_SINCE
    if port_open(COMFY_PORT):
        return {"ok": True, "msg": "ComfyUI 已在运行，无需重复启动"}
    if not os.path.isfile(MAIN_PY):
        return {"ok": False, "msg": "找不到 ComfyUI 主程序：%s" % MAIN_PY}

    exe = VENV_PYW if os.path.isfile(VENV_PYW) else VENV_PY
    if not os.path.isfile(exe):
        return {"ok": False, "msg": "找不到虚拟环境解释器：%s" % exe}

    ensure_dirs()
    env = os.environ.copy()
    env.update(CACHE_ENV)
    args = [
        exe, "main.py",
        "--listen", "127.0.0.1",
        "--port", str(COMFY_PORT),
        "--output-directory", OUT_DIR,
        "--temp-directory", TEMP_DIR,
    ]
    try:
        with open(COMFY_LOG, "ab", buffering=0) as logf:
            logf.write(("\n" + "=" * 70 + "\n[ComfyBox] 启动 ComfyUI  %s\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode("utf-8"))
            DETACHED = 0x00000008
            NEWGRP = 0x00000200
            subprocess.Popen(
                args, cwd=COMFY_DIR, env=env,
                stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
                creationflags=DETACHED | NEWGRP, close_fds=True,
            )
    except Exception as e:
        return {"ok": False, "msg": "启动失败：%s" % e}

    STARTING_SINCE = time.time()
    return {"ok": True, "msg": "已发出启动指令，模型加载中……"}


def stop_comfy():
    """停止 ComfyUI（结束监听 8188 的进程）。"""
    global STARTING_SINCE
    STARTING_SINCE = 0.0
    if not port_open(COMFY_PORT):
        return {"ok": True, "msg": "ComfyUI 本来就没在运行"}
    pid = pid_on_port(COMFY_PORT)
    if not pid:
        return {"ok": False, "msg": "端口 %d 被占用，但没能定位到进程 PID" % COMFY_PORT}
    out, code = run_cmd(["taskkill", "/F", "/T", "/PID", str(pid)], timeout=20)
    for _ in range(20):
        if not port_open(COMFY_PORT):
            return {"ok": True, "msg": "ComfyUI 已停止（PID %d），显存与内存已释放" % pid}
        time.sleep(0.25)
    return {"ok": False, "msg": "结束指令未能释放端口 %d（返回码 %s）：%s"
            % (COMFY_PORT, code, (out or "").strip()[:200])}


# ---------------------------------------------------------------- HTTP 处理


class Handler(BaseHTTPRequestHandler):
    server_version = "ComfyBox/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 输出助手 ----------

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def json_out(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def log_message(self, fmt, *a):
        # 静音默认的逐请求日志，避免刷屏（错误仍写日志文件）
        pass

    # ---------- 路由 ----------

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)

        # ---------- API ----------
        if path == "/api/status":
            return self.json_out({"ok": True, "status": comfy_status(), "box": self._box_info()})

        if path == "/api/models":
            return self.json_out({"ok": True, "slots": list_models()})

        if path == "/api/workflows":
            return self.json_out({
                "ok": True,
                "dir": WORKFLOW_DIR,
                "exists": os.path.isdir(WORKFLOW_DIR),
                "items": list_workflows(),
            })

        if path == "/api/gallery":
            limit = int((qs.get("limit") or ["120"])[0] or 120)
            items, total = list_gallery(limit)
            return self.json_out({"ok": True, "items": items, "total": total})

        if path == "/api/img":
            return self._serve_img(qs)

        if path == "/api/log":
            which = (qs.get("which") or ["comfy"])[0]
            n = int((qs.get("n") or ["300"])[0] or 300)
            path_map = {"comfy": COMFY_LOG, "box": BOX_LOG}
            target = path_map.get(which, COMFY_LOG)
            return self.json_out({
                "ok": True, "which": which, "file": target,
                "exists": os.path.isfile(target),
                "lines": tail_lines(target, n),
            })

        if path == "/api/config":
            return self.json_out({"ok": True, "config": self._box_info()})

        if path == "/api/open":
            return self._do_open(qs)

        # ---------- 静态文件 ----------
        return self._serve_static(path)

    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        if path == "/api/start":
            return self.json_out(start_comfy())
        if path == "/api/stop":
            return self.json_out(stop_comfy())
        if path == "/api/restart":
            r1 = stop_comfy()
            time.sleep(0.6)
            r2 = start_comfy()
            return self.json_out({"ok": r2.get("ok"), "msg": "%s；%s" % (r1.get("msg"), r2.get("msg"))})
        return self.json_out({"ok": False, "msg": "未知接口 %s" % path}, 404)

    # ---------- 具体实现 ----------

    def _box_info(self):
        return {
            "app": APP,
            "comfyDir": COMFY_DIR,
            "outDir": OUT_DIR,
            "tempDir": TEMP_DIR,
            "modelsDir": MODELS_DIR,
            "logDir": LOG_DIR,
            "customNodes": CUSTOM_NODES,
            "customNodeCount": len(os.listdir(CUSTOM_NODES)) if os.path.isdir(CUSTOM_NODES) else 0,
            "venv": VENV,
            "boxPort": self.server.server_address[1],
            "comfyPort": COMFY_PORT,
            "comfyUrl": "http://127.0.0.1:%d" % COMFY_PORT,
            "mainPyExists": os.path.isfile(MAIN_PY),
            "venvOk": os.path.isfile(VENV_PY),
        }

    def _serve_img(self, qs):
        name = (qs.get("name") or [""])[0]
        sub = (qs.get("sub") or [""])[0]
        if not name:
            return self._send(400, "missing name")
        fp = safe_join(OUT_DIR, sub, name)
        if not fp or not os.path.isfile(fp):
            return self._send(404, "not found")
        ext = os.path.splitext(fp)[1].lower()
        if ext not in IMAGE_EXT:
            return self._send(403, "not an image")
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except Exception as e:
            return self._send(500, str(e))
        return self._send(200, data, MIME.get(ext, "application/octet-stream"))

    def _do_open(self, qs):
        what = (qs.get("what") or ["output"])[0]
        targets = {
            "output": OUT_DIR,
            "app": APP,
            "comfy": COMFY_DIR,
            "log": LOG_DIR,
            "models": MODELS_DIR,
            "box": HERE,
            "workflows": WORKFLOW_DIR,
        }
        d = targets.get(what)
        if not d:
            return self.json_out({"ok": False, "msg": "未知目标 %s" % what}, 400)
        if not os.path.isdir(d):
            return self.json_out({"ok": False, "msg": "目录不存在：%s" % d})
        try:
            os.startfile(d)  # noqa: 仅 Windows 可用
            return self.json_out({"ok": True, "msg": "已打开 %s" % d})
        except Exception as e:
            return self.json_out({"ok": False, "msg": "打开失败：%s" % e})

    def _serve_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        rel = path.lstrip("/")
        fp = safe_join(HERE, rel)
        if not fp or not os.path.isfile(fp):
            return self._send(404, "404 Not Found: %s" % path, "text/plain; charset=utf-8")
        ext = os.path.splitext(fp)[1].lower()
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except Exception as e:
            return self._send(500, str(e))
        return self._send(200, data, MIME.get(ext, "application/octet-stream"))


def main():
    global COMFY_PORT
    ap = argparse.ArgumentParser(description="ComfyBox 控制台后端")
    ap.add_argument("--port", type=int, default=DEF_BOX_PORT, help="控制台网页端口")
    ap.add_argument("--comfy-port", type=int, default=DEF_COMFY_PORT, help="ComfyUI 端口")
    ap.add_argument("--autostart", action="store_true", help="启动控制台时顺带拉起 ComfyUI")
    args = ap.parse_args()
    COMFY_PORT = args.comfy_port

    ensure_dirs()

    # 无窗口运行时 stdout 可能为 None，先兜底到日志文件，避免 print 抛错
    if sys.stdout is None:
        sys.stdout = open(BOX_LOG, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout

    def say(msg):
        try:
            print("[ComfyBox] " + msg, flush=True)
        except Exception:
            pass

    if args.autostart:
        r = start_comfy()
        say("autostart: " + r.get("msg", ""))

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        say("端口 %d 无法监听：%s" % (args.port, e))
        return 2

    say("控制台已启动： http://127.0.0.1:%d" % args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
