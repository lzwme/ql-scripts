#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@see https://github.com/iicookies/auto-checkin/blob/master/trae_ui_checkin.py
Trae Work 桌面端 UI 自动签到。

Trae 是 Electron 应用，UIA 只能看到标题栏最小化/最大化/关闭，
签到按钮在 Chromium 页面里，必须：截图 → OCR → 鼠标点击。

实测路径（2026-08-21 TraeWork CN 0.1.52）：
  1. 聚焦 TraeWork CN 窗口
  2. 点击左下角用户信息（「用户xxxxxxxx」）
  3. 弹出账户菜单后，点击「签到」
  4. 成功后菜单显示「今日已签到，明天再来吧」，积分 +200

用法:
    python trae_ui_checkin.py
    python trae_ui_checkin.py --debug
    python trae_ui_checkin.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "trae_ui_checkin.log"

WINDOW_TITLES = ("TraeWork CN", "TRAE SOLO CN", "Trae CN")
EXE_NAMES = ("TRAE SOLO CN.exe", "TraeWork CN.exe", "Trae CN.exe")

USER_RE = re.compile(r"用户\s*\d+")
CREDIT_RE = re.compile(r"\+?\s*([\d,]+)")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data: str) -> int:
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def setup_file_log() -> None:
    log_fp = open(LOG_PATH, "a", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, log_fp)
    sys.stderr = _Tee(sys.__stderr__, log_fp)


# ---------------------------------------------------------------------------
# OCR 命中
# ---------------------------------------------------------------------------
@dataclass
class Hit:
    text: str
    score: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def compact(self) -> str:
        return re.sub(r"\s+", "", self.text)


def parse_ocr(raw) -> list[Hit]:
    hits: list[Hit] = []
    for item in raw or []:
        if not item or len(item) < 2:
            continue
        box, text = item[0], str(item[1])
        try:
            score = float(item[2]) if len(item) > 2 else 1.0
        except (TypeError, ValueError):
            score = 1.0
        xs = [int(p[0]) for p in box]
        ys = [int(p[1]) for p in box]
        hits.append(Hit(text=text, score=score, x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys)))
    return hits


def find_user_chip(hits: list[Hit], img_h: int) -> Hit | None:
    """左下角用户信息：底部区域里带「用户」的条目，取最靠下的一条。"""
    floor = int(img_h * 0.82)
    cands = [h for h in hits if h.y1 >= floor and ("用户" in h.text or USER_RE.search(h.text))]
    if not cands:
        cands = [h for h in hits if USER_RE.search(h.text)]
    if not cands:
        return None
    return max(cands, key=lambda h: h.y1)


def _is_daily_checkin_label(compact: str) -> bool:
    """左侧说明文案：每日签到领…积分（OCR 可能带前缀噪声，如「白」）。"""
    c = compact
    return ("每日" in c and "签到" in c and "积分" in c) or (
        "签到领" in c and "积分" in c
    )


def find_checkin_button(hits: list[Hit], img_h: int) -> Hit | None:
    """账户菜单里的「签到」按钮。

    要排除两类干扰：左侧说明文字「每日签到领200积分」，以及左下角那个
    「每日签到领积分」浮层里的签到按钮（点它不会有可识别的结果反馈）。

    实测 RapidOCR 偶发只认出左侧说明、漏掉右侧独立「签到」按钮（像素仍在，
    约在说明文字右侧 60~110px）。此时用说明行推算按钮位置做兜底。
    """
    floor = int(img_h * 0.85)  # 左下角浮层区域，不要点
    cands = [h for h in hits if h.y2 < floor]
    exact = [h for h in cands if h.compact == "签到"]
    if exact:
        return max(exact, key=lambda h: h.x1)
    loose = [
        h for h in cands
        if h.compact.endswith("签到")
        and "每日" not in h.compact
        and "今日" not in h.compact
        and len(h.compact) <= 4
    ]
    if loose:
        return max(loose, key=lambda h: h.x1)

    # OCR 漏检独立「签到」：从「每日签到领…积分」说明行推算右侧按钮
    labels = [h for h in cands if _is_daily_checkin_label(h.compact)]
    if labels:
        label = max(labels, key=lambda h: h.y1)
        # 实测说明文字右缘(x=216)到按钮左缘(x=285)间距约 69px，按钮宽约 37px
        btn_w, gap = 40, 65
        x1 = label.x2 + gap
        x2 = x1 + btn_w
        y1, y2 = label.y1, label.y2
        print(
            f"  OCR 未单独识别「签到」，按说明文案 {label.text!r} "
            f"推算按钮 @ ({(x1 + x2) // 2},{(y1 + y2) // 2})"
        )
        return Hit(text="签到", score=0.5, x1=x1, y1=y1, x2=x2, y2=y2)
    return None


def account_menu_open(hits: list[Hit]) -> bool:
    """账户菜单是否展开：靠「管理账户 / 退出登录」这类菜单专属项判断。"""
    blob = "".join(h.compact for h in hits)
    return any(k in blob for k in ("管理账户", "退出登录", "报告问题"))



def already_checked_in(hits: list[Hit]) -> bool:
    blob = "".join(h.compact for h in hits)
    return any(k in blob for k in ("今日已签", "明天再来", "已领取"))


def parse_menu_credits(hits: list[Hit]) -> int | None:
    """账户菜单标题右侧形如 +3,852 / + 4,052。"""
    for h in hits:
        if h.y1 < 350 or h.y1 > 480:
            continue
        if "+" not in h.text:
            continue
        m = CREDIT_RE.search(h.text)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# 窗口 / 截图 / 点击
# ---------------------------------------------------------------------------
def candidate_exes() -> list[Path]:
    roots: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Programs")
    home = Path.home()
    roots.append(home / "AppData" / "Local" / "Programs")
    # 部分机器把 LocalAppData 重定向到 D:\Users\...
    if home.drive and home.drive.upper() != "D:":
        roots.append(Path("D:/") / home.as_posix().lstrip(home.drive).lstrip("/\\") / "AppData" / "Local" / "Programs")
    roots.append(Path(r"D:\Users") / home.name / "AppData" / "Local" / "Programs")

    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for name in EXE_NAMES:
            p = root / "TRAE SOLO CN" / name
            key = str(p).lower()
            if p.is_file() and key not in seen:
                found.append(p)
                seen.add(key)
        for p in root.glob("TRAE*/**/*.exe"):
            if p.name in EXE_NAMES:
                key = str(p).lower()
                if key not in seen:
                    found.append(p)
                    seen.add(key)
    return found


def _process_exe(pid: int) -> str:
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return ""


def _is_trae_cn_exe(exe: str) -> bool:
    name = Path(exe).name.lower()
    parent = Path(exe).parent.name.lower()
    if name in {n.lower() for n in EXE_NAMES}:
        return True
    return "trae solo cn" in parent or "traework" in name


def _visible_top_windows() -> list[tuple[int, str, str, int]]:
    """Win32 枚举可见顶层窗口 -> [(hwnd, title, class_name, pid)]。

    这里刻意不用 pywinauto 的 uia 枚举：实测定时任务里「先启动 Trae 再轮询」的
    进程，uia 枚举始终看不到新出现的 Trae 窗口（同一时刻另起一个进程能立刻找到），
    等待必然超时。Win32 EnumWindows 没有这个问题，而且快得多。
    """
    import win32gui
    import win32process

    found: list[tuple[int, str, str, int]] = []

    def _collect(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            cls = win32gui.GetClassName(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            found.append((hwnd, title, cls, pid))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_collect, None)
    return found


def _window_size(hwnd: int) -> tuple[int, int]:
    import win32gui

    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    except Exception:
        return 0, 0
    return right - left, bottom - top


def find_window():
    from pywinauto.controls.hwndwrapper import HwndWrapper

    fallback = None
    for hwnd, title, cls, pid in _visible_top_windows():
        # 跳过安装器/更新器窗口（如「安装 - TraeWork CN (User)」、Squirrel Setup），
        # 否则会在安装界面上误点击。
        if is_installer_title(title):
            continue
        if any(t.lower() in title.lower() for t in WINDOW_TITLES):
            exe = _process_exe(pid)
            if exe and not _is_trae_cn_exe(exe):
                continue  # 标题像 Trae 但进程不是 Trae 本体（多为安装器）
            return HwndWrapper(hwnd)
        # 启动早期主窗口可能还没标题，用进程 + 窗口类兜底（排除 Electron 的辅助小窗）
        if fallback is None and "Chrome_WidgetWin" in cls and _is_trae_cn_exe(_process_exe(pid)):
            w, h = _window_size(hwnd)
            if w >= 600 and h >= 400:
                fallback = HwndWrapper(hwnd)
    return fallback


def window_alive(win) -> bool:
    import win32gui

    try:
        return bool(win32gui.IsWindow(win.handle) and win32gui.IsWindowVisible(win.handle))
    except Exception:
        return False



def is_installer_title(title: str) -> bool:
    t = (title or "").lower()
    markers = ("setup", "installer", "installing", "install - ", " - install")
    if any(m in t for m in markers):
        return True
    stripped = (title or "").strip()
    return stripped.startswith(("安装", "正在安装", "卸载"))


def launch_trae() -> None:
    import subprocess

    if find_window() is not None:
        return
    exes = candidate_exes()
    if not exes:
        raise RuntimeError("未找到 Trae 安装路径（TRAE SOLO CN.exe）")
    exe = exes[0]
    print(f"  启动: {exe}")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(exe)],
        cwd=str(exe.parent),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def has_installer_window() -> bool:
    """桌面上是否存在 Trae 安装/更新窗口。"""
    return any(is_installer_title(title) for _, title, _, _ in _visible_top_windows())


def wait_window(timeout: float, installer_grace: float = 420.0):
    """等待 Trae 主窗口。

    启动可能先触发自动更新的安装器（实测装 4 分钟以上），期间主窗口不存在。
    只要安装器还在，就把截止时间往后顶，最多额外等 installer_grace 秒。
    """
    start = time.time()
    deadline = start + timeout
    hard_deadline = deadline + installer_grace
    notified = False
    next_tick = start + 30.0
    while time.time() < deadline:
        win = find_window()
        if win is not None and window_alive(win):
            return win
        if has_installer_window():
            if not notified:
                print("  检测到 Trae 安装/更新窗口，等待安装完成后再找主窗口...")
                notified = True
            deadline = min(hard_deadline, time.time() + 60.0)
        now = time.time()
        if now >= next_tick:
            print(f"  等待中... 已 {int(now - start)}s，当前可见顶层窗口 {len(_visible_top_windows())} 个")
            next_tick = now + 30.0
        time.sleep(1.0)
    return None



def focus_window(win) -> None:
    try:
        win.set_focus()
    except Exception:
        try:
            win.restore()
            win.set_focus()
        except Exception:
            pass
    time.sleep(0.4)


def grab_window(win, save_as: Path | None = None):
    import mss
    import numpy as np
    from PIL import Image

    r = win.rectangle()
    left = max(0, int(r.left))
    top = max(0, int(r.top))
    right = int(r.right)
    bottom = int(r.bottom)
    width = max(1, right - left)
    height = max(1, bottom - top)
    with mss.MSS() as sct:
        raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    if save_as is not None:
        img.save(save_as)
    return img, np.array(img), left, top


class OcrEngine:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def run(self, arr) -> list[Hit]:
        result, _ = self._ocr(arr)
        return parse_ocr(result)


def click_screen(x: int, y: int) -> None:
    from pywinauto import mouse

    mouse.click(coords=(int(x), int(y)))


def click_hit(hit: Hit, shot_left: int, shot_top: int, dx: int = 0, dy: int = 0) -> tuple[int, int]:
    x = shot_left + hit.cx + dx
    y = shot_top + hit.cy + dy
    click_screen(x, y)
    return x, y


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run(debug: bool, dry_run: bool, launch: bool, timeout: int, ready_timeout: int) -> int:
    print(f"=== Trae UI 签到 {time.strftime('%Y-%m-%d %H:%M:%S')} ===")

    win = find_window()
    if win is None:
        if not launch:
            print("未找到 TraeWork CN 窗口。请先打开 Trae，或去掉 --no-launch。")
            return 1
        launch_trae()
        print(f"  等待窗口（最多 {timeout}s）...")
        win = wait_window(timeout)
        if win is None:
            print("启动后仍未出现 TraeWork CN 窗口。")
            return 1
        try:
            print(f"  窗口: {win.window_text()!r}")
        except Exception:
            pass
        time.sleep(2.0)

    else:
        try:
            print(f"  窗口: {win.window_text()!r}")
        except Exception:
            print("  已找到 Trae 窗口")

    focus_window(win)
    ocr = OcrEngine()

    def snap(tag: str):
        # 截图始终留档，定时任务失败时才有排查依据；逐条 OCR 文本仍只在 --debug 打印
        path = LOG_DIR / f"trae_ui_{tag}.png"
        img, arr, left, top = grab_window(win, path)
        hits = ocr.run(arr)
        print(f"  [{tag}] OCR {len(hits)} 条 -> {path.name}")
        if debug:
            for h in hits:
                print(f"    {h.x1:4d},{h.y1:4d} {h.score:.2f} {h.text}")
        return img, hits, left, top

    def ui_ready(img, hits) -> bool:
        return (
            find_user_chip(hits, img.height) is not None
            or find_checkin_button(hits, img.height) is not None
            or already_checked_in(hits)
        )


    def wait_ui_ready(timeout: float):
        """冷启动时窗口先出现、界面后渲染，等到能认出用户信息/签到入口再动手。"""
        deadline = time.time() + timeout
        while True:
            img, hits, left, top = snap("before")
            if ui_ready(img, hits):
                return img, hits, left, top, True
            if time.time() >= deadline:
                return img, hits, left, top, False
            print("  界面尚未就绪，等待渲染...")
            time.sleep(4.0)
            focus_window(win)

    def click_user(img, hits, left, top) -> None:
        user = find_user_chip(hits, img.height)
        if user is None:
            print("OCR 未找到左下角用户信息，尝试点击窗口左下角兜底位置。")
            click_screen(left + 40, top + img.height - 52)
            return
        dx = min(-24, user.x1 - user.cx - 8)
        sx, sy = click_hit(user, left, top, dx=dx)
        print(f"  已点击用户信息 {user.text!r} -> ({sx},{sy})")
        if debug:
            print(f"    box=({user.x1},{user.y1})-({user.x2},{user.y2})")

    img, hits, left, top, ready = wait_ui_ready(ready_timeout)
    if not ready:
        print(f"  窗口已出现但界面 {ready_timeout:.0f}s 内未就绪（未识别到用户信息/签到入口）。")
        print(f"  可查看 {LOG_DIR / 'trae_ui_before.png'}")
        return 2
    menu_open = account_menu_open(hits) or already_checked_in(hits)

    if dry_run:
        user = find_user_chip(hits, img.height)
        if user is None:
            print("  [dry-run] 未识别到用户信息")
        else:
            print(f"  [dry-run] 用户信息: {user.text!r} @ ({user.cx},{user.cy})")
        btn = find_checkin_button(hits, img.height)
        if btn is not None:
            print(f"  [dry-run] 签到按钮: {btn.text!r} @ ({btn.cx},{btn.cy})")
        if already_checked_in(hits):
            print("  [dry-run] 已识别到「今日已签到」")
        print("dry-run 到此为止（不点击）。")
        return 0

    if menu_open:
        print("  账户菜单已打开，跳过点击用户信息")
    else:
        for attempt in range(1, 4):
            click_user(img, hits, left, top)
            time.sleep(1.2)
            focus_window(win)
            img, hits, left, top = snap("menu" if attempt == 1 else f"menu{attempt}")
            if account_menu_open(hits) or already_checked_in(hits):
                break
            print(f"  账户菜单未展开，重试点击用户信息 ({attempt}/3)")
        else:
            print("多次点击后仍未展开账户菜单。请确认 Trae 窗口在前台且未被遮挡。")
            return 2


    credits_before = parse_menu_credits(hits)
    if credits_before is not None:
        print(f"  菜单积分: {credits_before}")

    if already_checked_in(hits):
        print("  状态: 今日已签到")
        if credits_before is not None:
            print(f"  积分: {credits_before}")
        print("=== 完成 ===")
        return 0

    btn = find_checkin_button(hits, img.height)
    if btn is None:

        print("已打开用户菜单，但 OCR 未找到「签到」按钮。")
        print("请确认 Trae 窗口未被遮挡，账户菜单已展开。")
        return 2

    sx, sy = click_hit(btn, left, top)
    print(f"  已点击签到 {btn.text!r} -> ({sx},{sy})")

    credits_after = None
    for wait in (1.5, 2.0):
        time.sleep(wait)
        focus_window(win)
        img, hits, left, top = snap("after")
        credits_after = parse_menu_credits(hits)
        if already_checked_in(hits) or (
            credits_before is not None and credits_after is not None and credits_after > credits_before
        ):
            break

    if already_checked_in(hits):
        print("  状态: 领取成功（今日已签到）")
        if credits_after is not None:
            extra = ""
            if credits_before is not None and credits_after >= credits_before:
                extra = f" (+{credits_after - credits_before})"
            print(f"  积分: {credits_after}{extra}")
        print("=== 完成 ===")
        return 0

    if credits_before is not None and credits_after is not None and credits_after > credits_before:
        print("  状态: 领取成功")
        print(f"  积分: {credits_after} (+{credits_after - credits_before})")
        print("=== 完成 ===")
        return 0

    print("  状态: 已点击签到，但未识别到成功文案")
    if credits_after is not None:
        print(f"  积分: {credits_after}")
    print("  可用 --debug 查看 logs/trae_ui_after.png")
    print("=== 完成 ===")
    return 3


def main() -> int:
    ap = argparse.ArgumentParser(description="Trae Work 桌面端 UI 自动签到")
    ap.add_argument("--debug", action="store_true", help="保存截图并打印 OCR 文本")
    ap.add_argument("--dry-run", action="store_true", help="只定位用户信息，不点菜单/签到")
    ap.add_argument("--no-launch", action="store_true", help="找不到窗口时不自动启动 Trae")
    ap.add_argument("--timeout", type=int, default=300, help="等待 Trae 窗口出现的秒数")
    ap.add_argument("--ready-timeout", type=int, default=120,
                    help="窗口出现后等界面渲染出用户信息的秒数")
    args = ap.parse_args()
    setup_file_log()
    try:
        return run(
            debug=args.debug,
            dry_run=args.dry_run,
            launch=not args.no_launch,
            timeout=args.timeout,
            ready_timeout=args.ready_timeout,
        )

    except KeyboardInterrupt:
        print("\n已中断")
        return 130
    except Exception as e:
        print(f"发生异常: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())