# -*- coding: utf-8 -*-
"""
聚宽社区每日签到自动化脚本
验证码策略：拦截 captchar API 获取 bgImg/hqImg，OpenCV 识别缺口位置，自动拖动滑块
平台：自动检测 macOS/Windows/Linux；支持任意 Chromium 内核浏览器（Chrome/Edge/Chromium/Brave 等）。

cron: 5 9 * * *
new Env('聚宽社区每日签到')

青龙面板 / Docker：
  - python 依赖：numpy、opencv-python-headless、playwright；并执行 playwright install chromium
  - 未装系统 Chrome 时，会自动尝试 Playwright 缓存中的 Chromium（与系统浏览器二选一逻辑在 detect_browser 末尾）
  - 容器：IN_DOCKER=1 或存在 /.dockerenv 时追加 --no-sandbox --disable-dev-shm-usage
  - 无头/无显示：需在容器内配置虚拟显示（如 xvfb-run）或带 DISPLAY 的环境
环境变量：
  JQDATA_USERNAME=用户名 # 必填
  JQDATA_PASSWORD=密码 # 必填
  BROWSER_CHROMIUM_EXE=浏览器可执行文件路径 # 可选
  BROWSER_CDP_PORT=cdp端口，默认 9222
  BROWSER_CDP_WAIT_SEC=cdp等待时间，默认 20 秒
  BROWSER_CDP_LAUNCH_RETRIES=cdp启动重试次数，默认 4 次
  BROWSER_CHROMIUM_ARGS=额外启动参数，空格分隔，追加在默认参数之后 # 可选
  IN_DOCKER=1 # 是否在docker容器中运行，可选，默认自动识别
  DEBUG_MODE=1 # 可选，开启后写入调试日志、全流程页面截图与验证码调试图（默认关闭不落盘图片）
"""

import time, random, sys, os, subprocess, pathlib, base64, shutil, re
import numpy as np
import cv2
from playwright.sync_api import sync_playwright

# ===================== 配置 =====================
DEBUG_MODE = os.environ.get("DEBUG_MODE", "0").strip().lower() in ("1", "true", "yes")
if DEBUG_MODE:
    print("DEBUG_MODE 已启用")
try:
    CDP_PORT = int((os.environ.get("BROWSER_CDP_PORT") or "9222").strip() or "9222")
except ValueError:
    CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"
CAPTCHA_MAX_RETRIES = 3
MANUAL_CAPTCHA_TIMEOUT = 60
LOG_FILE = os.path.join(
    os.path.dirname(__file__),
    "joinquant_checkin_log_debug.log" if DEBUG_MODE else "joinquant_checkin_log.log",
)
# 青龙 / Docker：CDP 专用 profile 目录名（用于 pgrep 精确匹配本脚本启动的浏览器）
JOINQUANT_PROFILE_ROOT = "JoinQuantCDP"

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

# 设置环境变量，避免 Playwright 驱动报 OpenSSL 错误
os.environ["OPENSSL_CONF"] = ""
os.environ["PYTHONIOENCODING"] = "utf-8"


def _is_docker_like():
    if (os.environ.get("IN_DOCKER") or "").strip().lower() in ("1", "true", "yes"):
        return True
    return pathlib.Path("/.dockerenv").exists()


def default_joinquant_user_data(browser_name: str) -> str:
    """本脚本专用 user-data-dir（与日常浏览器配置隔离，便于 pgrep 管理进程）。"""
    slug = "edge" if browser_name == "Edge" else "chromium"
    if IS_WINDOWS:
        base = os.path.expandvars(rf"%LOCALAPPDATA%\{JOINQUANT_PROFILE_ROOT}")
        return os.path.join(base, slug)
    if IS_MAC:
        return os.path.expanduser(f"~/Library/Application Support/{JOINQUANT_PROFILE_ROOT}/{slug}")
    return os.path.expanduser(f"~/.config/{JOINQUANT_PROFILE_ROOT}/{slug}")


def _infer_browser_name_from_path(exe_path: str) -> str:
    lower = exe_path.lower()
    if "edge" in lower or "msedge" in lower:
        return "Edge"
    if "brave" in lower:
        return "Brave"
    if "vivaldi" in lower:
        return "Vivaldi"
    if "opera" in lower or "operagx" in lower:
        return "Opera"
    if "ms-playwright" in lower or ("playwright" in lower and "chromium" in lower):
        return "Chromium"
    if "chromium" in lower and "chrome" not in lower:
        return "Chromium"
    if "chrome" in lower:
        return "Chrome"
    return "Chromium"


def _detect_playwright_bundled_chromium():
    """
    使用 Playwright 自带的 Chromium 可执行路径（需已执行 playwright install chromium）。
    与 launch 逻辑一致：由脚本用 subprocess 带 CDP 参数启动该 exe，再用 connect_over_cdp 连接。
    """
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if exe and pathlib.Path(exe).exists():
            return exe, "Chromium", default_joinquant_user_data("Chrome")
    except Exception:
        pass
    return None, None, None


# ===================== 浏览器检测 =====================
def detect_browser():
    """
    自动检测本机 Chromium 内核浏览器，返回 (browser_exe, browser_name, user_data_dir)。
    优先系统已安装的 Chrome/Edge/Chromium 等；均未命中时再尝试 Playwright 自带的 Chromium（playwright install chromium）。
    未找到返回 (None, None, None)。
    """
    if IS_WINDOWS:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for p in chrome_paths:
            if pathlib.Path(p).exists():
                return p, "Chrome", default_joinquant_user_data("Chrome")

        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for p in edge_paths:
            if pathlib.Path(p).exists():
                return p, "Edge", default_joinquant_user_data("Edge")

        brave_win = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        if pathlib.Path(brave_win).exists():
            return brave_win, "Brave", default_joinquant_user_data("Brave")

        for cmd, label in (("msedge", "Edge"), ("chrome", "Chrome"), ("brave", "Brave")):
            w = shutil.which(cmd)
            if w:
                return w, label, default_joinquant_user_data("Edge" if label == "Edge" else "Chrome")
        try:
            r = subprocess.run(["where", "msedge"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return r.stdout.strip().splitlines()[0], "Edge", default_joinquant_user_data("Edge")
        except Exception:
            pass
        return _detect_playwright_bundled_chromium()

    if IS_MAC:
        mac_candidates = [
            ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "Chrome"),
            ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "Edge"),
            ("/Applications/Chromium.app/Contents/MacOS/Chromium", "Chromium"),
            ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "Brave"),
            ("/Applications/Vivaldi.app/Contents/MacOS/Vivaldi", "Vivaldi"),
        ]
        for p, label in mac_candidates:
            if pathlib.Path(p).exists():
                return p, label, default_joinquant_user_data("Edge" if label == "Edge" else "Chrome")
        for cmd, label in (("google-chrome", "Chrome"), ("chromium", "Chromium"), ("brave-browser", "Brave")):
            w = shutil.which(cmd)
            if w:
                return w, label, default_joinquant_user_data("Edge" if label == "Edge" else "Chrome")
        return _detect_playwright_bundled_chromium()

    # Linux：PATH + 常见安装路径（青龙 Docker 常用）
    linux_cmds = [
        ("google-chrome-stable", "Chrome"),
        ("google-chrome", "Chrome"),
        ("chromium-browser", "Chromium"),
        ("chromium", "Chromium"),
        ("brave-browser", "Brave"),
        ("vivaldi-stable", "Vivaldi"),
        ("opera", "Opera"),
        ("microsoft-edge", "Edge"),
        ("microsoft-edge-stable", "Edge"),
        ("msedge", "Edge"),
    ]
    for cmd, label in linux_cmds:
        w = shutil.which(cmd)
        if w:
            return w, label, default_joinquant_user_data("Edge" if label == "Edge" else "Chrome")

    return _detect_playwright_bundled_chromium()


def get_browser_from_env():
    """
    环境变量：
      BROWSER_CHROMIUM_EXE   浏览器可执行文件完整路径（Chromium 系）
      CHROMIUM_BROWSER_NAME  可选；用于日志与 profile 子目录（Edge 与其它分开）
    """
    exe = os.environ.get("BROWSER_CHROMIUM_EXE", "").strip()
    if not exe:
        return None, None, None, None

    if not pathlib.Path(exe).exists():
        warning = f"环境变量 BROWSER_CHROMIUM_EXE 指定的路径不存在: {exe}，将使用自动检测"
        return None, None, None, warning

    name = os.environ.get("CHROMIUM_BROWSER_NAME", "").strip()
    if not name:
        name = _infer_browser_name_from_path(exe)

    user_data = default_joinquant_user_data("Edge" if name == "Edge" else "Chrome")
    return exe, name, user_data, None


# 全局检测变量（延迟到 run_checkin 中根据环境变量输出日志）
_used_env_browser = False
_env_warning = None

_env_browser = get_browser_from_env()
if _env_browser[0]:
    # 环境变量有效
    BROWSER_EXE, BROWSER_NAME, BROWSER_USER_DATA_DIR, _env_warning = _env_browser
    _used_env_browser = True
else:
    # 环境变量无效或未设置
    _env_warning = _env_browser[3]  # 获取警告信息（如果有）
    BROWSER_EXE, BROWSER_NAME, BROWSER_USER_DATA_DIR = detect_browser()
    _used_env_browser = False

# 如果环境变量路径无效，回退到自动检测
if _env_warning:
    print(f"[WARN] {_env_warning}")
    print(f"[WARN] 回退到自动检测浏览器")
    BROWSER_EXE, BROWSER_NAME, BROWSER_USER_DATA_DIR = detect_browser()
    _used_env_browser = False

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_cdp_available():
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2)
        return True
    except Exception:
        return False


# ===================== 跨平台进程管理 =====================

def _resolved_user_data_dir():
    """当前配置下绝对路径的 user-data-dir（用于匹配进程命令行）。"""
    if not BROWSER_USER_DATA_DIR:
        return None
    try:
        return str(pathlib.Path(BROWSER_USER_DATA_DIR).expanduser().resolve())
    except Exception:
        return str(pathlib.Path(BROWSER_USER_DATA_DIR).expanduser())

def _windows_process_image_name():
    if BROWSER_EXE:
        return pathlib.Path(BROWSER_EXE).name
    return "msedge.exe" if BROWSER_NAME == "Edge" else "chrome.exe"

def get_browser_main_pids():
    """获取与本脚本 user-data-dir 相关的浏览器主进程（尽量排除 renderer）。"""
    if IS_WINDOWS:
        exe_name = _windows_process_image_name()
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            main_pids = []
            ud = _resolved_user_data_dir()
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].lower() == exe_name.lower():
                    try:
                        pid = parts[1]
                        cmd_result = subprocess.run(
                            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/value"],
                            capture_output=True, text=True, timeout=3
                        )
                        cmd = cmd_result.stdout.strip()
                        if ud and ud.lower() not in cmd.lower():
                            continue
                        if "--type=" not in cmd:
                            main_pids.append((pid, cmd))
                    except Exception:
                        pass
            return main_pids
        except Exception:
            return []
    ud = _resolved_user_data_dir()
    if not ud:
        return []
    try:
        result = subprocess.run(
            ["pgrep", "-f", re.escape(ud)],
            capture_output=True, text=True, timeout=8
        )
        pids = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
        main_pids = []
        for pid in pids:
            try:
                cmd_result = subprocess.run(
                    ["ps", "-p", pid, "-o", "command="],
                    capture_output=True, text=True, timeout=3
                )
                cmd = cmd_result.stdout.strip()
                main_pids.append((pid, cmd))
            except Exception:
                pass
        return main_pids
    except Exception:
        return []

def browser_has_cdp_flag(pid):
    """检查指定 PID 的浏览器进程是否带有 --remote-debugging-port 参数"""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/value"],
                capture_output=True, text=True, timeout=3
            )
            return f"--remote-debugging-port={CDP_PORT}" in result.stdout
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(
                ["ps", "-p", pid, "-o", "command="],
                capture_output=True, text=True, timeout=3
            )
            return f"--remote-debugging-port={CDP_PORT}" in result.stdout
        except Exception:
            return False

def kill_browser_without_cdp():
    """结束使用本脚本 profile、但未带 CDP 端口的浏览器进程。"""
    if IS_WINDOWS:
        exe_name = _windows_process_image_name()
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            ud = _resolved_user_data_dir()
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].lower() == exe_name.lower():
                    pid = parts[1]
                    try:
                        cmd_result = subprocess.run(
                            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/value"],
                            capture_output=True, text=True, timeout=3
                        )
                        cmd = cmd_result.stdout.strip()
                        if ud and ud.lower() not in cmd.lower():
                            continue
                        if f"--remote-debugging-port={CDP_PORT}" in cmd:
                            continue
                        log(f"  终止 {BROWSER_NAME} 进程 PID={pid}")
                        subprocess.run(["taskkill", "/F", "/PID", pid], timeout=5)
                    except Exception as e:
                        log(f"  终止 PID={pid} 失败: {e}")
            time.sleep(1)
        except Exception as e:
            log(f"  查找 {BROWSER_NAME} 进程失败: {e}")
        return

    ud = _resolved_user_data_dir()
    if not ud:
        return
    try:
        result = subprocess.run(
            ["pgrep", "-f", re.escape(ud)],
            capture_output=True, text=True, timeout=8
        )
        pids = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
        for pid in pids:
            try:
                cmd_result = subprocess.run(
                    ["ps", "-p", pid, "-o", "command="],
                    capture_output=True, text=True, timeout=3
                )
                cmd = cmd_result.stdout.strip()
                if f"--remote-debugging-port={CDP_PORT}" in cmd:
                    continue
                log(f"  终止 {BROWSER_NAME} 进程 PID={pid}")
                subprocess.run(["kill", "-9", pid], timeout=5)
            except Exception as e:
                log(f"  终止 PID={pid} 失败: {e}")
        time.sleep(1)
    except Exception as e:
        log(f"  查找 {BROWSER_NAME} 进程失败: {e}")

def kill_all_profile_browser_processes():
    """结束所有使用本脚本 user-data-dir 的浏览器进程（含已开 CDP），用于端口未就绪时强制重启。"""
    if IS_WINDOWS:
        exe_name = _windows_process_image_name()
        ud = _resolved_user_data_dir()
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].lower() == exe_name.lower():
                    pid = parts[1]
                    try:
                        cmd_result = subprocess.run(
                            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/value"],
                            capture_output=True, text=True, timeout=3
                        )
                        cmd = cmd_result.stdout.strip()
                        if ud and ud.lower() not in cmd.lower():
                            continue
                        log(f"  强制结束 {BROWSER_NAME} PID={pid}")
                        subprocess.run(["taskkill", "/F", "/PID", pid], timeout=5)
                    except Exception:
                        pass
            time.sleep(1)
        except Exception:
            pass
        return

    ud = _resolved_user_data_dir()
    if not ud:
        return
    try:
        result = subprocess.run(
            ["pgrep", "-f", re.escape(ud)],
            capture_output=True, text=True, timeout=8
        )
        for pid in result.stdout.strip().splitlines():
            pid = pid.strip()
            if not pid:
                continue
            try:
                log(f"  强制结束 {BROWSER_NAME} PID={pid}")
                subprocess.run(["kill", "-9", pid], timeout=5)
            except Exception:
                pass
        time.sleep(1)
    except Exception:
        pass

def _chromium_launch_args(user_data_dir: str):
    args = [
        BROWSER_EXE,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if _is_docker_like():
        args.extend([
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
    extra = (os.environ.get("BROWSER_CHROMIUM_ARGS") or "").strip()
    if extra:
        args.extend(extra.split())
    args.append("about:blank")
    return args

def launch_browser_with_cdp():
    """
    启动 Chromium 系浏览器并开放 CDP。
    若端口未就绪：关闭本脚本 profile 下相关进程后重试，直至连上或达到次数上限。
    """
    if not BROWSER_EXE or not BROWSER_NAME:
        log("❌ 未检测到可用的 Chromium 内核浏览器")
        return False

    log(f"使用 {BROWSER_NAME} 路径: {BROWSER_EXE}")
    if _is_docker_like():
        log("检测到 Docker/容器环境（IN_DOCKER 或 /.dockerenv），将追加 --no-sandbox 等参数")

    max_rounds = int((os.environ.get("BROWSER_CDP_LAUNCH_RETRIES") or "4").strip() or "4")
    max_rounds = max(1, min(max_rounds, 10))

    if is_cdp_available():
        log(f"检测到 CDP 端口 {CDP_PORT} 已开放，直接连接")
        return True

    user_data_dir = BROWSER_USER_DATA_DIR or default_joinquant_user_data(
        "Edge" if BROWSER_NAME == "Edge" else "Chrome"
    )
    try:
        user_data_dir = str(pathlib.Path(user_data_dir).expanduser().resolve())
    except Exception:
        user_data_dir = str(pathlib.Path(user_data_dir).expanduser())
    os.makedirs(user_data_dir, exist_ok=True)

    for round_i in range(1, max_rounds + 1):
        if is_cdp_available():
            log(f"CDP 端口 {CDP_PORT} 已就绪")
            return True

        main_pids = get_browser_main_pids()
        has_cdp_process = any(browser_has_cdp_flag(pid) for pid, _ in main_pids)

        if has_cdp_process:
            log(f"已有带 CDP 参数的进程，等待端口 {CDP_PORT} 就绪...")
            for i in range(15):
                time.sleep(1)
                if is_cdp_available():
                    log(f"CDP 端口已就绪（等待了 {i + 1}s）")
                    return True
            log("等待 CDP 端口仍不可用，将结束相关进程并重新启动浏览器")

        if main_pids:
            log(f"第 {round_i}/{max_rounds} 轮：清理未就绪的浏览器进程后重试...")
            kill_all_profile_browser_processes()
            time.sleep(2)

        if is_cdp_available():
            return True

        log(f"第 {round_i}/{max_rounds} 轮：启动 {BROWSER_NAME}（CDP 端口 {CDP_PORT}）...")
        try:
            popen_kwargs = {}
            if IS_WINDOWS:
                popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS
            subprocess.Popen(_chromium_launch_args(user_data_dir), **popen_kwargs)
        except Exception as e:
            log(f"启动 {BROWSER_NAME} 失败: {e}")
            kill_all_profile_browser_processes()
            time.sleep(2)
            continue

        wait_sec = int((os.environ.get("BROWSER_CDP_WAIT_SEC") or "20").strip() or "20")
        wait_sec = max(5, min(wait_sec, 120))
        for i in range(wait_sec):
            time.sleep(1)
            if is_cdp_available():
                log(f"{BROWSER_NAME} 启动成功，CDP 端口已就绪（等待了 {i + 1}s）")
                return True

        log(f"第 {round_i}/{max_rounds} 轮：等待 CDP 端口超时，将关闭浏览器并重试")
        kill_all_profile_browser_processes()
        time.sleep(2)

    log(f"❌ 经过 {max_rounds} 轮仍无法使 CDP 端口 {CDP_PORT} 就绪")
    return False

def screenshot(page, name):
    """安全截图，避免字体加载卡住。仅 DEBUG_MODE 时写入磁盘。"""
    if not DEBUG_MODE:
        return
    path = os.path.join(os.path.dirname(__file__), name)
    try:
        page.screenshot(path=path, timeout=8000, type="jpeg", quality=80)
        log(f"  已截图 {name}")
    except Exception as e:
        log(f"  截图 {name} 失败（已忽略）: {type(e).__name__}")


# ===================== 验证码图像处理 =====================

def b64_to_cv_img(b64_str):
    """Base64 字符串转 OpenCV BGR 图片"""
    if ',' in b64_str:
        b64_str = b64_str.split(',', 1)[1]
    b64_str = b64_str.strip()
    missing = len(b64_str) % 4
    if missing:
        b64_str += '=' * (4 - missing)
    img_bytes = base64.b64decode(b64_str)
    return cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

def find_gap_x(bg_b64, hq_b64, attempt=1):
    """
    识别背景图缺口 X 坐标（从 base64 数据）。
    注意：API 返回的 bgImg 是被切割拼接的，不准确。请使用 find_gap_x_from_screenshots。
    """
    bg = b64_to_cv_img(bg_b64)
    hq = b64_to_cv_img(hq_b64)
    if bg is None or hq is None:
        return None
    return find_gap_x_from_screenshots(bg, hq, attempt=attempt)

def find_gap_x_from_screenshots(bg, hq, attempt=1):
    """
    识别背景图缺口 X 坐标（从 OpenCV 图片对象）。
    bg: 大图（背景，已隐藏小图后的截图）
    hq: 小图（滑块拼图块截图）
    attempt: 重试次数，每次用不同策略/参数
    """
    if bg is None or hq is None:
        log("  ⚠️ 图片为空")
        return None
    log(f"  背景图: {bg.shape[1]}x{bg.shape[0]}, 滑块图: {hq.shape[1]}x{hq.shape[0]}")

    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    hq_gray = cv2.cvtColor(hq, cv2.COLOR_BGR2GRAY)
    bg_w = bg.shape[1]

    # 提取滑块实际内容区域（去除透明/白色背景）
    _, hq_binary = cv2.threshold(hq_gray, 127, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((2, 2), np.uint8)
    hq_binary = cv2.morphologyEx(hq_binary, cv2.MORPH_OPEN, kernel)

    coords = cv2.findNonZero(hq_binary)
    if coords is None:
        log("  ⚠️ 无法提取滑块内容区域")
        return None

    x, y, w_hq, h_hq = cv2.boundingRect(coords)
    margin = 2
    x = max(0, x - margin)
    y = max(0, y - margin)
    w_hq = min(hq.shape[1] - x, w_hq + margin * 2)
    h_hq = min(hq.shape[0] - y, h_hq + margin * 2)
    hq_content = hq_gray[y:y + h_hq, x:x + w_hq]
    log(f"  滑块实际内容: {w_hq}x{h_hq} (在原图偏移: x={x}, y={y})")

    # ===== 根据 attempt 选择不同策略 =====
    if attempt == 1:
        # 第1次：标准灰度模板匹配
        result = cv2.matchTemplate(bg_gray, hq_content, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        gap_x = max_loc[0]
        log(f"  策略A(灰度匹配): gap_x={gap_x}px (置信度={max_val:.3f})")

    elif attempt == 2:
        # 第2次：边缘检测匹配 + 调整阈值
        bg_edge = cv2.Canny(bg_gray, 50, 150)
        hq_edge = cv2.Canny(hq_content, 50, 150)
        if hq_edge.size > 0:
            result = cv2.matchTemplate(bg_edge, hq_edge, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            gap_x = max_loc[0]
            log(f"  策略B(边缘匹配低阈值): gap_x={gap_x}px (置信度={max_val:.3f})")
        else:
            gap_x = None

    elif attempt == 3:
        # 第3次：尝试不同的二值化阈值提取滑块内容
        for thresh in [100, 80, 150]:
            _, hq_bin2 = cv2.threshold(hq_gray, thresh, 255, cv2.THRESH_BINARY_INV)
            coords2 = cv2.findNonZero(hq_bin2)
            if coords2 is not None:
                x2, y2, w2, h2 = cv2.boundingRect(coords2)
                if w2 > 5 and h2 > 5:
                    hq_c2 = hq_gray[y2:y2 + h2, x2:x2 + w2]
                    r2 = cv2.matchTemplate(bg_gray, hq_c2, cv2.TM_CCOEFF_NORMED)
                    _, mv2, _, ml2 = cv2.minMaxLoc(r2)
                    log(f"  策略C(阈值{thresh}): gap_x={ml2[0]}px (置信度={mv2:.3f})")
                    if mv2 > 0.3:
                        gap_x = ml2[0]
                        break
        else:
            gap_x = None

    if gap_x is None:
        log("  ⚠️ 缺口识别失败")
        return None

    # 合理性检查
    min_gap = 40
    max_gap = bg_w - w_hq - 10
    if gap_x < min_gap:
        log(f"  ⚠️ gap_x({gap_x})太小，调整到 {min_gap}")
        gap_x = min_gap
    elif gap_x > max_gap:
        log(f"  ⚠️ gap_x({gap_x})太大，调整到 {max_gap}")
        gap_x = max_gap

    log(f"  ✅ 最终缺口位置: gap_x={gap_x}px")

    if DEBUG_MODE:
        try:
            ddir = os.path.join(os.path.dirname(__file__), "captcha_debug")
            os.makedirs(ddir, exist_ok=True)
            dbg = bg.copy()
            cv2.rectangle(dbg, (gap_x, 0), (gap_x + w_hq, bg.shape[0]), (0, 0, 255), 2)
            cv2.putText(dbg, f"gap={gap_x},attempt={attempt}", (5, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imwrite(os.path.join(ddir, f"gap_{int(time.time())}.jpg"), dbg)
        except Exception:
            pass
    return gap_x

def get_drag_distance(gap_x, captcha_data, page):
    """
    将缺口原始 X 坐标转换为页面上的实际拖动距离。
    关键理解：
    - gap_x: 缺口在原始背景图(bgImg)上的 X 坐标
    - 滑块手柄初始位置在背景图最左端（约 x=0 处）
    - 拖动距离 = 缺口位置 * 缩放比例 - 手柄初始偏移
    """
    bg_img_w = captcha_data.get('bgImgW', 363)
    try:
        info = page.evaluate("""() => {
            const el = document.querySelector('#yth_captchar');
            if (!el) return null;
            const bg = el.querySelector('.valid-code__div');
            const dr = el.querySelector('.valid-code__drag-handle.handler');
            return {
                bg_w: bg ? bg.getBoundingClientRect().width : 0,
                bg_left: bg ? bg.getBoundingClientRect().left : 0,
                dr_x: dr ? dr.getBoundingClientRect().x : 0,
                dr_w: dr ? dr.getBoundingClientRect().width : 0,
            };
        }""")
        if info and info['bg_w'] > 0:
            scale = info['bg_w'] / bg_img_w
            # 手柄中心相对于背景图左边缘的初始偏移
            handle_offset = 0 # (info['dr_x'] + info['dr_w'] / 2) - info['bg_left']
            # 缺口在页面上的位置
            gap_page_x = gap_x * scale
            # 拖动距离 = 缺口位置 - 手柄初始位置
            dist = gap_page_x - handle_offset
            log(f"  缩放={scale:.3f}, 手柄初始偏移={handle_offset:.1f}px, "
                f"缺口页面位置={gap_page_x:.1f}px, 拖动距离={dist:.1f}px")
            # 合理性检查
            if 10 < dist < info['bg_w'] * 0.9:
                return dist
            else:
                log(f"  ⚠️ 拖动距离({dist:.0f})超出合理范围，回退: gap_x*scale={gap_page_x:.1f}px")
                return gap_page_x
    except Exception as e:
        log(f"  ⚠️ 获取页面尺寸失败: {e}")
    # 最坏情况：直接用 gap_x（假设无缩放）
    return gap_x

def move_slider(page, distance):
    """模拟人类拖动滑块"""
    handle = page.query_selector(".valid-code__drag-handle.handler")
    if not handle:
        return False
    box = handle.bounding_box()
    if not box:
        return False
    sx = box['x'] + box['width'] / 2
    sy = box['y'] + box['height'] / 2
    log(f"  手柄中心: ({sx:.0f}, {sy:.0f})")
    page.mouse.move(sx, sy)
    time.sleep(random.uniform(0.1, 0.2))
    page.mouse.down()
    time.sleep(random.uniform(0.05, 0.1))
    # ease-in-out 轨迹
    steps = random.randint(18, 30)
    for i in range(1, steps + 1):
        t = i / steps
        ease = 4*t*t*t if t < 0.5 else 1 - pow(-2*t+2, 3)/2
        mx = sx + distance * ease
        my = sy + random.uniform(-1.5, 1.5)
        page.mouse.move(mx, my)
        time.sleep(random.uniform(0.01, 0.03))
    time.sleep(random.uniform(0.05, 0.1))
    page.mouse.up()
    log(f"  拖动完成: {distance:.0f}px")
    return True

def captcha_passed(page):
    """检查验证码是否已通过（容器消失或隐藏）"""
    try:
        c = page.query_selector("#yth_captchar")
        if not c or not c.is_visible():
            return True
    except Exception:
        return True
    return False

def install_xhr_interceptor(page):
    """在页面上注入 XHR 拦截器，捕获 captchar API 响应"""
    # 先检查是否已安装（避免覆盖已捕获的数据）
    already = page.evaluate("() => window.__captcharInterceptInstalled === true")
    if already:
        return
    page.evaluate("""() => {
        window.__captcharIntercept = window.__captcharIntercept || null;
        window.__captcharInterceptInstalled = true;
        const origOpen = XMLHttpRequest.prototype.open;
        const origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(method, url) {
            this.__url = url;
            return origOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function() {
            const xhr = this;
            xhr.addEventListener('load', function() {
                if (xhr.__url && xhr.__url.includes('verifyCode/captchar')) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        if (data && data.data && data.data.bgImg) {
                            window.__captcharIntercept = data;
                        }
                    } catch(e) {}
                }
            });
            return origSend.apply(this, arguments);
        };
    }""")

def get_captcha_images(page, timeout=12):
    """等待并获取 captchar API 返回的 bgImg/hqImg 数据"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            data = page.evaluate("() => window.__captcharIntercept")
            if data and data.get('data') and data['data'].get('bgImg'):
                return data['data']
        except Exception:
            pass
        time.sleep(0.5)
    return None

def screenshot_element_bgr(page, selector, save_path=None):
    """
    截图指定 DOM 元素为 BGR 图。
    save_path 非空且为目录已存在时写入原始 PNG 字节（仅 DEBUG 流程会传路径）。
    """
    try:
        el = page.query_selector(selector)
        if not el:
            return None
        data = el.screenshot(timeout=5000)
        if save_path:
            with open(save_path, "wb") as f:
                f.write(data)
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        log(f"  截图 {selector} 失败: {e}")
    return None

def solve_captcha_auto(page, context="验证码"):
    """
    自动解决滑块验证码。
    策略: 验证码弹出后，截图 DOM 元素获取真实图片（API 返回的 bgImg 是被切割拼接的，不准确）
    流程: 等待验证码弹出 → 截图 #xy_img(小图) → 隐藏小图后截图 #yth_captchar(大图) → OpenCV 识别缺口 → 拖动滑块。
    调试图仅 DEBUG_MODE 时写入 captcha_debug/；否则截图仅在内存中供 OpenCV 使用。
    """
    log(f"  🔍 准备处理「{context}」验证码...")

    # 等待验证码容器出现
    try:
        page.wait_for_selector("#yth_captchar", timeout=15000)
        time.sleep(2)  # 等待 Vue 渲染完成
    except Exception:
        if captcha_passed(page):
            log(f"  ✅ 验证码已通过（未弹出）")
            return True
        log(f"  ⚠️ 等待验证码超时")
        return False

    # 截图获取真实图片（API 返回的 bgImg 是被切割拼接的，不准确）
    captcha_dir = os.path.join(os.path.dirname(__file__), "captcha_debug")
    small_path = big_path = None
    if DEBUG_MODE:
        os.makedirs(captcha_dir, exist_ok=True)
        ts = int(time.time())
        small_path = os.path.join(captcha_dir, f"small_{ts}.png")
        big_path = os.path.join(captcha_dir, f"big_{ts}.png")

    # 1. 截图小图 (#xy_img)
    hq = screenshot_element_bgr(page, "#xy_img", small_path)
    if hq is None:
        log("  ⚠️ 截图小图失败，回退人工模式")
        return wait_for_captcha_manual(page, context)
    if DEBUG_MODE and small_path:
        log(f"  小图已保存: {small_path}")

    # 2. 隐藏小图，截图大图 (#yth_captchar)
    page.evaluate("""() => {
        const small = document.querySelector('#xy_img');
        if (small) small.style.visibility = 'hidden';
    }""")
    time.sleep(0.5)
    bg = screenshot_element_bgr(page, "#yth_captchar", big_path)
    if bg is None:
        page.evaluate("""() => {
            const small = document.querySelector('#xy_img');
            if (small) small.style.visibility = 'visible';
        }""")
        log("  ⚠️ 截图大图失败，回退人工模式")
        return wait_for_captcha_manual(page, context)
    if DEBUG_MODE and big_path:
        log(f"  大图已保存: {big_path}")

    # 恢复小图显示
    page.evaluate("""() => {
        const small = document.querySelector('#xy_img');
        if (small) small.style.visibility = 'visible';
    }""")

    log(f"  截图大图: {bg.shape[1]}x{bg.shape[0]}, 小图: {hq.shape[1]}x{hq.shape[0]}")

    # 获取页面上的背景图实际宽度（用于计算缩放）
    bg_img_w = page.evaluate("""() => {
        const el = document.querySelector('#yth_captchar');
        return el ? el.getBoundingClientRect().width : 363;
    }""") or 363

    for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
        log(f"  --- 第 {attempt}/{CAPTCHA_MAX_RETRIES} 次尝试 ---")
        screenshot(page, f"captcha_attempt_{attempt}.jpg")

        # 识别缺口位置（每次重试用不同策略）
        gap_x = find_gap_x_from_screenshots(bg, hq, attempt=attempt)
        if gap_x is None:
            log(f"  ⚠️ 缺口识别失败，回退人工模式")
            return wait_for_captcha_manual(page, context)

        # 计算拖动距离
        drag_dist = get_drag_distance(gap_x, {'bgImgW': bg_img_w}, page)
        if drag_dist <= 0 or drag_dist > bg_img_w:
            log(f"  ⚠️ 拖动距离异常({drag_dist:.0f}px)，回退人工模式")
            return wait_for_captcha_manual(page, context)

        # 拖动滑块
        move_slider(page, drag_dist)
        time.sleep(2)

        # 检查是否通过
        if captcha_passed(page):
            log(f"  ✅ 验证码通过！（第{attempt}次尝试）")
            time.sleep(1)
            return True

        # 检查验证码是否还在（可能已通过但检测延迟）
        if not page.query_selector("#yth_captchar"):
            log(f"  ✅ 验证码容器已消失，判定通过")
            return True

        if attempt < CAPTCHA_MAX_RETRIES:
            log(f"  验证未通过，准备重试（调整识别策略）...")
            time.sleep(1.5)

    log(f"  ⚠️ 自动尝试 {CAPTCHA_MAX_RETRIES} 次均失败，切换人工模式")
    return wait_for_captcha_manual(page, context)

def wait_for_captcha_manual(page, context="签到", timeout=MANUAL_CAPTCHA_TIMEOUT):
    """人工辅助：等待用户手动完成验证码"""
    log(f"  ⏳ 请在浏览器中手动完成「{context}」滑块验证码...")
    log(f"  等待最长 {timeout} 秒...")
    start = time.time()
    while time.time() - start < timeout:
        if captcha_passed(page):
            log(f"  ✅ 验证码通过！")
            time.sleep(1)
            return True
        time.sleep(0.5)
    log(f"  ⚠️ 人工验证码超时")
    return False

def js_navigate(page, url, wait=5):
    """用 JS 方式导航，避免 CDP 下 page.goto() 关闭 Target"""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass
    page.evaluate(f"window.location.href = '{url}'")
    time.sleep(wait)
    # 等待页面加载完成
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    log(f"  导航完成: {page.url}")

def is_logged_in(page):
    """检测是否已登录（多种方式）"""
    try:
        # 方式1: 检查导航栏是否有"登录"链接
        has_login_link = page.evaluate("""() => {
            const links = [...document.querySelectorAll('#kk_navbar a, .common-header a, header a')];
            return links.some(d => (d.innerText || d.textContent || '').trim().includes('登录'));
        }""")
        if has_login_link:
            return False

        # 方式2: 检查是否有用户头像/用户名显示
        has_user_info = page.evaluate("""() => {
            return !!document.querySelector('.user-name, .avatar, [class*="user"], [class*="profile"]');
        }""")
        if has_user_info:
            return True

        # 方式3: 检查 localStorage 或 cookie 中是否有登录态
        has_token = page.evaluate("""() => {
            return localStorage.getItem('token') !== null ||
                   document.cookie.includes('session') ||
                   document.cookie.includes('jwt');
        }""")
        if has_token:
            return True

        # 默认认为未登录（保守策略）
        return False
    except Exception:
        return False

def ensure_login(page):
    """检测登录状态，未登录则自动登录"""
    log("检查登录状态...")

    if is_logged_in(page):
        log("✅ 已登录")
        return True

    log("未登录，准备自动登录...")
    username = os.environ.get("JQDATA_USERNAME", "")
    password = os.environ.get("JQDATA_PASSWORD", "")
    if not username or not password:
        log("❌ 环境变量 JQDATA_USERNAME / JQDATA_PASSWORD 未设置")
        return False

    js_navigate(page, "https://www.joinquant.com/user/login/index", wait=3)
    time.sleep(2)

    # 用 JS 填充表单（模拟输入，触发 input 事件）
    page.evaluate(f"""() => {{
        const userInput = document.querySelector('input[name=username]');
        const pwdInput = document.querySelector('input[name=pwd]');
        const agreeBox = document.querySelector('input#agreementBox');

        if (userInput) {{
            userInput.value = '{username}';
            userInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            userInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        if (pwdInput) {{
            pwdInput.value = '{password}';
            pwdInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            pwdInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        if (agreeBox && !agreeBox.checked) {{
            agreeBox.click();
        }}
    }}""")
    time.sleep(1)

    # 点击登录按钮
    log("点击登录按钮...")
    try:
        login_btn = page.query_selector("button.login-submit")
        if login_btn:
            login_btn.click()
        else:
            page.evaluate("() => document.querySelector('button.login-submit')?.click()")
    except Exception as e:
        log(f"  点击登录按钮失败: {e}")
        return False

    time.sleep(3)

    # 检查是否登录成功
    if not is_logged_in(page):
        log("❌ 登录失败")
        return False

    log("✅ 登录成功")
    return True

def read_article(page):
    """任务1：访问文章列表，随机阅读一篇文章10秒以上"""
    log("=== 任务1：访问文章列表，随机阅读一篇文章 ===")

    js_navigate(page, "https://www.joinquant.com/view/community/list?listType=1", wait=4)
    # 导航后重新安装 XHR 拦截器
    try:
        install_xhr_interceptor(page)
    except Exception:
        pass
    time.sleep(2)

    current_url = page.url
    log(f"当前页面：{current_url}")

    # 检测登录状态，未登录则自动登录
    if "login" in current_url.lower():
        log("被重定向到登录页，尝试自动登录...")
        if not ensure_login(page):
            return False
        # 登录成功后重新导航到文章列表
        js_navigate(page, "https://www.joinquant.com/view/community/list?listType=1", wait=4)
        time.sleep(2)
    else:
        # 检查页面是否需要登录
        if not ensure_login(page):
            return False

    # 等待文章列表加载
    try:
        page.wait_for_selector(".jq-c-list_community__item", timeout=10000)
        log("文章列表已加载")
    except Exception:
        log("等待文章列表超时，继续尝试")
    time.sleep(2)

    article_items = page.query_selector_all(".jq-c-list_community__item")
    log(f"找到 {len(article_items)} 篇文章卡片")

    if not article_items:
        log("❌ 未找到文章卡片")
        return False

    # 随机选一篇
    chosen_item = random.choice(article_items)
    title_el = chosen_item.query_selector(".jq-c-list_community__text")
    title_text = title_el.inner_text().strip() if title_el else "(无标题)"
    log(f"选择文章: {title_text[:60]}")
    screenshot(page, "01_article_list.jpg")

    # 获取文章 URL — 多种方法
    article_url = None

    # 方法1：从卡片内的所有链接提取
    try:
        all_links = chosen_item.evaluate("""el => {
            const links = el.querySelectorAll('a[href]');
            const urls = [];
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                if (!href.includes('/user/') && !href.includes('listType')) {
                    if (href.includes('/post/') || href.includes('/community/post')) {
                        urls.push(href);
                    }
                }
            }
            return urls;
        }""")
        if all_links:
            article_url = all_links[0]
            log(f"  从卡片提取到 {len(all_links)} 个文章链接")
    except Exception as e:
        log(f"  提取链接失败: {e}")

    # 方法2：从整个页面提取文章链接列表
    if not article_url:
        try:
            page_links = page.evaluate("""() => {
                const items = document.querySelectorAll('.jq-c-list_community__item');
                const urls = [];
                for (const item of items) {
                    const links = item.querySelectorAll('a[href]');
                    for (const a of links) {
                        const href = a.getAttribute('href') || '';
                        // 只要包含 post 且不含 user/listType 的链接
                        if (href.includes('/post/') && !href.includes('/user/') && !href.includes('listType')) {
                            urls.push(href);
                            break;
                        }
                    }
                }
                return urls;
            }""")
            if page_links:
                article_url = random.choice(page_links)
                log(f"  从页面提取到 {len(page_links)} 个文章链接，随机选一个")
        except Exception:
            pass

    # 方法3：直接点击卡片并等待 URL 变化
    if not article_url:
        url_before = page.url
        click_target = title_el if title_el else chosen_item
        try:
            click_target.click()
            log("  点击文章卡片，等待页面跳转...")
            for _ in range(20):
                time.sleep(0.5)
                if page.url != url_before:
                    article_url = page.url
                    break
            return True
        except Exception as e:
            log(f"  点击失败: {e}")
            return False

    if not article_url:
        log("❌ 无法获取文章链接")
        return False

    # 确保完整 URL
    if article_url.startswith("/"):
        article_url = "https://www.joinquant.com" + article_url
    elif not article_url.startswith("http"):
        article_url = "https://www.joinquant.com/" + article_url

    log(f"访问文章: {article_url}")
    js_navigate(page, article_url, wait=4)
    # 导航后重新安装 XHR 拦截器
    try:
        install_xhr_interceptor(page)
    except Exception:
        pass
    time.sleep(2)
    log(f"当前页面: {page.url}")
    screenshot(page, "02_article_page.jpg")

    # 模拟阅读（滚动 12 秒）
    log("开始阅读文章（等待12秒，模拟滚动）...")
    for i in range(4):
        page.mouse.wheel(0, random.randint(200, 400))
        time.sleep(3)
    log("✅ 文章阅读完成（共12秒）")
    return True

def do_checkin(page):
    """任务2：访问积分中心并签到"""
    log("=== 任务2：访问积分中心并签到 ===")

    js_navigate(page, "https://www.joinquant.com/view/user/floor?type=creditsdesc", wait=4)
    # 导航后重新安装 XHR 拦截器
    try:
        install_xhr_interceptor(page)
    except Exception:
        pass
    time.sleep(2)

    log(f"当前页面：{page.url}")
    screenshot(page, "05_credits_center.jpg")

    # 先检查是否已签到（页面显示"今日已签到"或"已签到"按钮）
    body_text = page.inner_text("body")
    already_checked_in = "今日已签到" in body_text or "今日已签" in body_text
    if already_checked_in:
        log("✅ 今日已签到")

    # 查找签到按钮
    checkin_btn = None
    if not already_checked_in:
        for sel in ["button:has-text('签到')", "a:has-text('签到')",
                    "button:has-text('每日签到')", "[class*='sign-btn']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    # 排除"已签到"状态的按钮
                    text = el.inner_text().strip()
                    if "已签到" in text or "今日已签" in text:
                        log(f"  跳过'{text}'按钮（已签到状态）")
                        continue
                    checkin_btn = el
                    log(f"找到签到按钮: {sel} (text='{text}')")
                    break
            except Exception:
                pass

    if not checkin_btn and not already_checked_in:
        if "已签到" in body_text:
            log("✅ 今日已签到！")
            already_checked_in = True
        else:
            log("❌ 未找到签到按钮")
            screenshot(page, "06_no_checkin_btn.jpg")
            # 即使没有签到按钮，也继续尝试领取文章奖励

    # ===== 执行签到 =====
    checkin_ok = already_checked_in  # 已签到则视为成功
    if checkin_btn:
        log("点击签到按钮...")
        try:
            install_xhr_interceptor(page)
            log("  签到前重新安装 XHR 拦截器")
        except Exception as e:
            log(f"  ⚠️ 拦截器安装失败: {e}")
        checkin_btn.click()
        time.sleep(2)
        screenshot(page, "06_checkin_captcha.jpg")

        checkin_ok = solve_captcha_auto(page, context="签到")
        time.sleep(2)
        screenshot(page, "07_after_checkin.jpg")

        if checkin_ok:
            try:
                body_text = page.inner_text("body")
                if "签到成功" in body_text or "已签到" in body_text:
                    log("✅ 签到成功（确认页面提示）")
                else:
                    log("✅ 签到完成（验证码已通过）")
            except Exception:
                log("✅ 签到完成")
        else:
            log("⚠️ 签到验证码超时，请查看截图确认")

    # ===== 领取所有可领取的奖励（积分中心）=====
    log("检查积分中心所有可领取奖励...")
    time.sleep(1)

    # 获取所有"立即领取"按钮及其对应的积分类型
    claim_items = page.evaluate("""() => {
        const btns = [...document.querySelectorAll('.floor-credit-center button:not([disabled])')];
        return btns
            .filter(d => d.innerText.trim() === '立即领取')
            .map(btn => {
                // 获取对应的积分类型名称
                let taskName = '';
                try {
                    const header = btn.parentNode.parentNode.parentNode.parentNode.querySelector('.header-title');
                    taskName = header ? header.innerText.trim() : '签到';
                } catch(e) {}
                return { taskName, index: btns.indexOf(btn) };
            })
            // .filter(item => item.taskName); // 只保留能获取到任务名的
    }""")

    if not claim_items:
        log("  未发现「立即领取」按钮（可能今日已领取或无奖励）")
        return checkin_ok

    log(f"  发现 {len(claim_items)} 个可领取任务: {[item['taskName'] for item in claim_items]}")

    # 逐个执行领取
    for i, item in enumerate(claim_items):
        task_name = item['taskName']
        log(f"  [{i+1}/{len(claim_items)}] 领取「{task_name}」...")

        try:
            install_xhr_interceptor(page)
        except Exception:
            pass

        # 点击当前按钮
        page.evaluate(f"""() => {{
            const btns = [...document.querySelectorAll('.floor-credit-center button:not([disabled])')];
            const validBtns = btns.filter(d => d.innerText.trim() === '立即领取');
            if (validBtns[{i}]) validBtns[{i}].click();
        }}""")
        time.sleep(1)
        screenshot(page, f"08_claim_captcha_{i+1}.jpg")

        claim_ok = solve_captcha_auto(page, context=f"「{task_name}」领取")
        time.sleep(2)
        screenshot(page, f"09_after_claim_{i+1}.jpg")

        if claim_ok:
            log(f"  ✅ 「{task_name}」领取完成")
        else:
            log(f"  ⚠️ 「{task_name}」领取验证码超时")


    return checkin_ok

def run_checkin():
    global _used_env_browser, _env_warning

    # 清空旧日志
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== 聚宽签到日志 {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    log("=== 聚宽社区每日签到开始 ===")
    log(f"检测到平台: {'Windows' if IS_WINDOWS else 'macOS' if IS_MAC else 'Linux'}")

    if _used_env_browser:
        log(f"使用环境变量指定的浏览器: {BROWSER_NAME}")
        log(f"  路径: {BROWSER_EXE}")
    else:
        if _env_warning:
            log(f"⚠️ {_env_warning}")
        log(f"自动检测浏览器: {BROWSER_NAME}")

    if not BROWSER_EXE:
        log("❌ 未检测到可用的 Chromium 内核浏览器（可设置 BROWSER_CHROMIUM_EXE）")
        sys.exit(1)

    if not launch_browser_with_cdp():
        log(f"❌ 无法启动/连接带 CDP 端口的 {BROWSER_NAME}")
        sys.exit(1)

    with sync_playwright() as p:
        log(f"通过 CDP 连接 {BROWSER_NAME}（{CDP_URL}）...")
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            log("✅ CDP 连接成功")
        except Exception as e:
            log(f"❌ CDP 连接失败: {e}")
            sys.exit(1)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()

        page.set_default_timeout(30000)

        # 在执行任务前安装 XHR 拦截器
        try:
            install_xhr_interceptor(page)
            log("XHR 拦截器已预安装")
        except Exception as e:
            log(f"XHR 拦截器安装失败: {e}")

        # 执行任务
        article_ok = read_article(page)
        checkin_ok = do_checkin(page)

        log("=== 所有任务执行完毕 ===")
        log(f"  文章阅读: {'✅ 成功' if article_ok else '❌ 失败'}")
        log(f"  每日签到: {'✅ 成功' if checkin_ok else '❌ 失败'}")

        browser.close()
        log(f"CDP 连接已断开（{BROWSER_NAME} 浏览器继续运行）")

if __name__ == "__main__":
    run_checkin()
