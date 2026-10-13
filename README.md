# ComfyBox · ComfyUI 本地控制台

给 ComfyUI 套的一层「一键启动 + 网页控制台」。目标只有一个：**双击一次就能用，不用管黑窗口、不用记端口、不用手动开浏览器。**

```
双击  启动 ComfyBox.bat   →  浏览器自动打开控制台，ComfyUI 在后台自动加载
关闭控制台网页不影响生图；要释放显存内存时双击  停止 ComfyUI (释放内存).bat
```

后端 `server.py` 是**纯 Python 标准库**实现，零第三方依赖；前端 `index.html` 是**单文件、零依赖、离线可用**的界面。

---

## 一、预期目录结构

ComfyBox 不绑定任何固定盘符，它的默认路径都从**自身所在位置**推导。推荐这样摆放（`<APP>` 可以是任意目录）：

```
<APP>\
  ComfyUI\        ← ComfyUI 本体（含 main.py、models\、output\）
  venv\           ← Python 虚拟环境（装了 ComfyUI 依赖的那个）
  ComfyBox\       ← 本项目
    server.py
    index.html
    启动 ComfyBox.bat
    ...
```

若目录不满足上面的约定（例如 venv 在别处），把 `config.example.bat` 复制为 `config.bat` 并填写路径即可，详见第三节。

---

## 二、文件说明

| 文件 | 作用 |
|---|---|
| `启动 ComfyBox.bat` | **唯一入口**。启动控制台服务 → 自动拉起 ComfyUI → 打开浏览器 |
| `停止 ComfyBox.bat` | 只停控制台网页（默认端口 8790），**不动 ComfyUI** |
| `停止 ComfyUI (释放内存).bat` | 停掉 ComfyUI（默认端口 8188），释放显存与内存 |
| `server.py` | 控制台后端：纯标准库 HTTP 服务，负责状态查询、启停 ComfyUI、日志、图片 |
| `index.html` | 控制台界面：单文件、零依赖、离线可用 |
| `config.example.bat` | 本地配置模板（复制为 `config.bat` 使用，后者不入版本库） |
| `logs/comfyui.log` | ComfyUI 的输出日志（**启动失败先看这里**） |
| `logs/comfbox.log` | 控制台自己的日志 |
| `browser-profile/` | 控制台专用的浏览器配置目录（会话数据留在本目录，不污染日常浏览器） |

### 端口约定

| 端口 | 用途 |
|---|---|
| **8790** | ComfyBox 控制台（你要打开的页面） |
| **8188** | ComfyUI 本体（工作台由控制台内嵌显示，也可单独访问） |

---

## 三、配置（可选）

把 `config.example.bat` 复制为 `config.bat`，按需取消注释：

```bat
@echo off
REM Python 虚拟环境解释器（不在上述默认位置时）
REM set "PYW=D:\ComfyUI\venv\Scripts\pythonw.exe"
REM set "PY=D:\ComfyUI\venv\Scripts\python.exe"
REM 控制台端口（默认 8790）
REM set "PORT=8790"
REM ComfyUI 端口（默认 8188）
REM set "COMFY_PORT=8188"
REM AI 缓存根目录（默认 <APP>\AI-Cache，用于 HF / CUDA / torch 缓存）
REM set "COMYBOX_CACHE_DIR=D:\AI-Cache"
```

`config.bat` 会被启动脚本优先加载，其内容会传递给 `server.py`（后者读取环境变量 `COMYBOX_CACHE_DIR`）。该文件已被 `.gitignore` 忽略。

---

## 四、控制台能做什么

- **状态一眼看清**：运行中 / 已停止 / 启动中，GPU 型号、显存占用条、内存占用条、任务队列
- **一键启停**：不用去关黑窗口，也不用翻任务管理器
- **工作台内嵌**：ComfyUI 原界面直接嵌在「工作台」标签里，打开就是生图界面；右下角有悬浮的「重载界面」按钮，可让 ComfyUI 重新读取工作流与模型
- **工作流清单**：列出 `user/default/workflows/` 下的所有工作流（节点数 / 大小 / 修改时间），点击复制文件名
- **模型清单**：自动扫描 `models/` 下各槽位（主模型 / LoRA / VAE / ControlNet …），显示文件名与大小
- **输出画廊**：自动收集 `output/` 里的出图，缩略图网格 + 点击放大（ComfyUI 停止时也能看图）
- **日志面板**：直接看 ComfyUI 日志尾部，启动失败时不用去翻文件
- **快捷按钮**：打开输出文件夹 / 打开模型目录 / 新标签页打开 ComfyUI

---

## 五、日常用法

**生图**：双击 `启动 ComfyBox.bat` → 等 20 秒左右（第一次要把 SDXL 加载进显存）→ 在「工作台」里画图 → 出图自动出现在「输出」标签。

**不想让它占内存时**：双击 `停止 ComfyUI (释放内存).bat`。ComfyUI 常驻时会占 **10~13 GB 内存**（SDXL 缓存在 RAM 里），不用的时候停掉能立刻回收。下次要用再双击启动器，约 20 秒回来。

**换模型**：把 `.safetensors` 放进 `ComfyUI\models\checkpoints\`，然后在控制台「模型」标签点「重新扫描」，回到 ComfyUI 界面刷新节点即可选到。

**工作流明明存了，工作台里却看不到？** 点工作台右下角的「重载界面」（或按 Ctrl+R）。ComfyUI 的工作流列表只在页面加载时读一次，新放进 `workflows\` 的文件不会自动冒出来；可以先在控制台「工作流」标签确认文件确实在位。

---

## 六、故障排查

**Q：双击启动器后浏览器页面打不开？**
A：看 `logs/comfbox.log`。常见原因是 Python 环境被移动/删除，脚本会自检并给出提示。

**Q：页面能开，但「工作台」里 ComfyUI 一直转圈？**
A：看「日志」标签或 `logs/comfyui.log`。多半是模型文件缺失或显存不足；状态栏的显存条能直接看出占用。

**Q：想彻底重置控制台（清掉浏览器里存的东西）？**
A：关掉窗口后删除 `browser-profile\` 目录即可。

**Q：控制台显示「已停止」但我明明启动过？**
A：ComfyUI 进程可能崩了。点「启动」重来一次，然后看日志面板末尾的报错。

**Q：端口被占用？**
A：8790 或 8188 被别的程序占了。改端口：控制台的改 `config.bat` 里的 `PORT`；ComfyUI 的改 `config.bat` 里的 `COMFY_PORT`（或在启动 `server.py` 时传 `--comfy-port`）。

---

## 七、给以后改代码的人：三个已踩过的坑

这几处都是**真实踩过并且已修复**的，改动时别改回去：

**1. 不要在 bat 里用 `powershell -Command "... ^| Out-Null"` 做端口探测。**
cmd 会把 `^` 原样传给 PowerShell，导致 `找不到与参数名称"^"匹配的形式参数`，探测永远失败（表现为脚本傻等 20 秒后误报「未就绪」）。现在统一用：

```bat
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
```

不依赖外部程序、不走系统代理、快得多。

**2. `%~dp0` 结尾自带反斜杠，拼路径前必须去掉。**
否则 `--directory "%DIR%"` 展开成 `--directory "D:\...\OllaBox\"`，结尾的 `\"` 被当成转义引号，Python 收到的是带引号的错误路径。写法：

```bat
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"
```

**3. 以某个工作流为模板派生新工作流时，必须换掉顶层的 `id`。**

工作流 JSON 顶层的 `id` 是它在 ComfyUI 前端里的唯一索引。照抄模板而不改，新旧两个工作流就会撞 id，**新的会被老的顶掉，在前端列表里直接看不见**（文件明明在，`/api/workflows` 也列得出来，就是 UI 里没有）。注意只换顶层 `id` —— `nodes[].id` 是画布内的引用编号，不能动。

**另外几条本项目的既有约定：**

- bat 一律写成 **GBK 编码 + CRLF**。UTF-8 的 bat 即使配了 `chcp 65001`，cmd 解析中文时仍可能错乱。
- 延时用 `ping -n N 127.0.0.1 >nul`，不要用 `timeout`——容易被 PATH 里的同名命令（如 Git 自带的）截胡。
- Python 调用外部命令（netstat / taskkill）时**不要用 `text=True`**：中文 Windows 输出是 GBK，Python 3.13 默认按 UTF-8 解码会让读取线程崩掉、`.stdout` 变成 `None`。`server.py` 里的 `run_cmd()` 已经处理好了。
- 访问 `127.0.0.1` 的 HTTP 请求要**显式禁用代理**，否则用户开着 VPN 时可能被代理劫持（`server.py` 用的是 `ProxyHandler({})`）。
