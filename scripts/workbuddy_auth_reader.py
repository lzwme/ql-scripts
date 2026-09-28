#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取本机已安装 WorkBuddy 客户端的官方加密密钥，解密本地会话中的
phoneNumber / access_token / refresh_token。

@see https://github.com/jlcodes99/cockpit-tools/blob/main/src-tauri/src/modules/workbuddy_account.rs
登录文件查找规则：
  1. $WORKBUDDY_AUTH_FILE（显式覆盖）
  2. 共享登录目录 + workbuddy-desktop.info：
     Windows %LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth
     macOS   ~/Library/Application Support/CodeBuddyExtension/Data/Public/auth
     Linux   ~/.local/share/CodeBuddyExtension/Data/Public/auth
  3. ~/.workbuddy/app/workbuddy_accounts.json（账号索引）
  4. ~/.workbuddy/app/workbuddy_accounts/*.json（单账号详情）
  - 存在 {登录文件}.logged-out 标记即视为已登出，跳过该文件。
  - --deep 时再回退到全盘扫描（默认关闭）。

凭据解析规则：
  - token 取值键序：token → access_token → accessToken → auth.accessToken
    → auth.access_token → session/data 递归。
  - 旧版 token 形如 `uid+token`，只取 `+` 之后的部分；无前缀时用 JWT 的
    payload.sub 作为 uid 回退。
  - 文件不是 JSON 时（legacy），整段文本即 token。

@see https://github.com/jlcodes99/cockpit-tools/blob/v1.3.60/src-tauri/src/modules/workbuddy_auth_crypto.rs
流程与 Rust 实现严格对齐：
  1) 以 ELECTRON_RUN_AS_NODE=1 启动官方 WorkBuddy 客户端执行一次性脚本，
     通过 process._linkedBinding('electron_browser_workbuddy_storage')
     .loggerGet() 取得 {version:1, atRestSecretKey:<base64 32 字节>}；
     密钥只在匿名管道中传递，不落盘、不进命令行参数、不打印。
  2) key = sha256(atRestSecretKey 的 base64 **文本**，而非其字节)。
  3) keyId = hex(sha256(key))[:16]。
  4) AAD = b"WB-AAD\\0\\x01" + (len+"WBEV1") + (len+"sym-v1")
           + u32be(1) + (len+keyId) + b"\\x02\\x00\\x00"。
  5) 载荷 {"$wbEncrypted":1,"envelope":<base64>}，envelope 内为
     {suite,keyId,nonce,authTag,ciphertext}，ciphertext||authTag 一起做
     AES-256-GCM 解密（nonce 12 字节 / tag 16 字节 / suite 必须为 1）。

本脚本只读不写，不修改客户端任何状态；依赖仅 Python 标准库
（内置了一份 AES-256-GCM 实现，无需 cryptography / pycryptodome）。

默认输出末尾会额外打印一行可直接复制的环境变量（供外部脚本读取）：
    WORKBUDDY_REFRESH_TOKEN=手机号:access_token:refresh_token
外部脚本可这样取用：
    python scripts/workbuddy_auth_reader.py | grep '^WORKBUDDY_REFRESH_TOKEN=' | cut -d= -f2-
    python scripts/workbuddy_auth_reader.py --json | jq -r '.env.WORKBUDDY_REFRESH_TOKEN'

用法：
    python scripts/workbuddy_auth_reader.py
    python scripts/workbuddy_auth_reader.py --mask            # 脱敏输出
    python scripts/workbuddy_auth_reader.py --auth-file <path> # 指定会话文件
    python scripts/workbuddy_auth_reader.py --exe <path>       # 指定客户端可执行文件
    python scripts/workbuddy_auth_reader.py --json             # 机器可读输出
    python scripts/workbuddy_auth_reader.py --self-test        # 用官方测试向量自检
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

# --------------------------------------------------------------------------
# 常量：与 Rust 实现保持一致
# --------------------------------------------------------------------------

KEY_TIMEOUT = 15.0  # Rust 里是 5s，Python 冷启动略慢，放宽到 15s

INVALID = "WorkBuddy 官方加密字段校验失败，请更新或重新登录官方客户端后重试"
UNSUPPORTED = "WorkBuddy 官方加密格式不受支持，请更新本脚本后重试"
KEY_MISMATCH = "WorkBuddy 官方加密密钥已变化，请重新运行本脚本"
NO_CLIENT = "未找到已安装的 WorkBuddy 客户端，请用 --exe 指定可执行文件绝对路径"

# 只在子进程内执行，密钥经 stdout 匿名管道回传；不打印 stdout/stderr
KEY_SCRIPT = r"""
try {
  const c = require('crypto');
  const p = JSON.parse(process._linkedBinding('electron_browser_workbuddy_storage').loggerGet());
  if (p.version !== 1 || typeof p.atRestSecretKey !== 'string') process.exit(2);
  const b = Buffer.from(p.atRestSecretKey, 'base64');
  if (b.length !== 32 || b.toString('base64') !== p.atRestSecretKey || b.every(x => x === 0)) process.exit(2);
  const key = c.createHash('sha256').update(p.atRestSecretKey, 'utf8').digest();
  process.stdout.write(key.toString('base64'));
  key.fill(0); b.fill(0);
} catch (_) { process.exit(2); }
"""

# Rust 单元测试里的官方夹具：密钥 [7;32]、nonce [3;12]，明文 "fixture-token-测试"
SELF_TEST_ENVELOPE = (
    '{"suite":1,"keyId":"4bb06f8e4e3a7715","nonce":"AwMDAwMDAwMDAwMD",'
    '"authTag":"8mXI80XfjtTaNENkKD5E5Q==","ciphertext":"Q5fbdy9aO28OLyg5hXoZuWbUT3o="}'
)
SELF_TEST_PLAINTEXT = "fixture-token-测试"


class CryptoError(Exception):
    """解密/校验失败。"""


# --------------------------------------------------------------------------
# AES-256-GCM（纯标准库实现）
# --------------------------------------------------------------------------


def _build_sbox() -> tuple[list[int], list[int]]:
    p = q = 1
    sbox = [0] * 256
    while True:
        p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)) & 0xFF
        q &= 0xFF
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        q &= 0xFF
        x = (
            q
            ^ ((q << 1) | (q >> 7))
            ^ ((q << 2) | (q >> 6))
            ^ ((q << 3) | (q >> 5))
            ^ ((q << 4) | (q >> 4))
        )
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    return sbox, inv


_SBOX, _INV_SBOX = _build_sbox()
assert _SBOX[0x00] == 0x63 and _SBOX[0x01] == 0x7C and _SBOX[0x53] == 0xED

_RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C]


def _xtime(a: int) -> int:
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1B) & 0xFF
    return a & 0xFF


def _gmul(a: int, b: int) -> int:
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        b >>= 1
        a = _xtime(a)
    return r & 0xFF


class _AES:
    """仅实现 GCM 所需的单块加密（ECB 语义）。"""

    __slots__ = ("nk", "nr", "w")

    def __init__(self, key: bytes) -> None:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES key must be 16/24/32 bytes")
        self.nk = len(key) // 4
        self.nr = self.nk + 6
        self.w = self._expand(key)

    def _expand(self, key: bytes) -> list[list[int]]:
        nk, nr = self.nk, self.nr
        w = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
        for i in range(nk, 4 * (nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [_SBOX[b] for b in t]
                t[0] ^= _RCON[i // nk]
            elif nk > 6 and i % nk == 4:
                t = [_SBOX[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        return w

    def encrypt_block(self, block: bytes) -> bytes:
        if len(block) != 16:
            raise ValueError("block must be 16 bytes")
        w, nr = self.w, self.nr
        # state[r][c] == block[4 * c + r]
        s = [[block[4 * c + r] for c in range(4)] for r in range(4)]

        def add_round_key(round_: int) -> None:
            for c in range(4):
                word = w[round_ * 4 + c]
                for r in range(4):
                    s[r][c] ^= word[r]

        add_round_key(0)
        for round_ in range(1, nr):
            for r in range(4):
                for c in range(4):
                    s[r][c] = _SBOX[s[r][c]]
            for r in range(1, 4):  # ShiftRows: 第 r 行循环左移 r
                s[r] = s[r][r:] + s[r][:r]
            for c in range(4):  # MixColumns
                a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                s[0][c] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
                s[1][c] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
                s[2][c] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
                s[3][c] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
            add_round_key(round_)
        # 最后一轮没有 MixColumns
        for r in range(4):
            for c in range(4):
                s[r][c] = _SBOX[s[r][c]]
        for r in range(1, 4):
            s[r] = s[r][r:] + s[r][:r]
        add_round_key(nr)

        out = bytearray(16)
        for c in range(4):
            for r in range(4):
                out[4 * c + r] = s[r][c]
        return bytes(out)


_MASK128 = (1 << 128) - 1
_R = 0xE1 << 120


def _gf128_mul(x: int, y: int) -> int:
    z = 0
    v = x
    for i in range(128):
        if (y >> (127 - i)) & 1:
            z ^= v
        v = (v >> 1) ^ _R if v & 1 else v >> 1
    return z


def _ghash(h: int, data: bytes) -> int:
    y = 0
    for i in range(0, len(data), 16):
        y = _gf128_mul(y ^ int.from_bytes(data[i : i + 16], "big"), h)
    return y


def _inc32(cb: int) -> int:
    return (cb & ~0xFFFFFFFF) | (((cb & 0xFFFFFFFF) + 1) & 0xFFFFFFFF)


def _gctr(aes: _AES, icb: int, data: bytes) -> bytes:
    out = bytearray()
    cb = icb
    for i in range(0, len(data), 16):
        ks = aes.encrypt_block(cb.to_bytes(16, "big"))
        chunk = data[i : i + 16]
        out += bytes(a ^ b for a, b in zip(chunk, ks))
        cb = _inc32(cb)
    return bytes(out)


def _pad16(data: bytes) -> bytes:
    rem = len(data) % 16
    return data if rem == 0 else data + b"\x00" * (16 - rem)


def aes_gcm_decrypt(key: bytes, nonce: bytes, data: bytes, aad: bytes) -> bytes:
    """data = ciphertext || tag(16)。"""
    if len(nonce) != 12:
        raise CryptoError("nonce 长度必须为 12 字节")
    if len(data) < 16:
        raise CryptoError("密文长度不足（缺少 16 字节 auth tag）")
    aes = _AES(key)
    h = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    j0 = (int.from_bytes(nonce, "big") << 32) | 1
    ciphertext, tag = data[:-16], data[-16:]

    plaintext = _gctr(aes, _inc32(j0), ciphertext)
    s = _ghash(
        h,
        _pad16(aad) + _pad16(ciphertext) + (len(aad) * 8).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big"),
    )
    ek = aes.encrypt_block(j0.to_bytes(16, "big"))
    expected = bytes(a ^ b for a, b in zip(s.to_bytes(16, "big"), ek))
    if not _eq(expected, tag):
        raise CryptoError("GCM 认证失败（密钥不匹配或数据被篡改）")
    return plaintext


def _eq(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a, b):
        diff |= x ^ y
    return diff == 0


# --------------------------------------------------------------------------
# 官方密钥与信封
# --------------------------------------------------------------------------


def b64_decode_strict(encoded: str) -> bytes:
    """严格 base64：与 Rust 的 `encode(decode(x)) == x` 校验等价。"""
    if len(encoded) > 16 * 1024 * 1024:
        raise CryptoError("字段过长")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise CryptoError(INVALID) from exc
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise CryptoError(INVALID)
    return raw


class OfficialKey:
    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise CryptoError(INVALID)
        self.bytes = key
        self.id = hashlib.sha256(key).hexdigest()[:16]

    def aad(self) -> bytes:
        out = bytearray(b"WB-AAD\x00\x01")
        for value in (b"WBEV1", b"sym-v1"):
            out += len(value).to_bytes(4, "big") + value
        out += (1).to_bytes(4, "big")
        raw_id = self.id.encode("ascii")
        out += len(raw_id).to_bytes(4, "big") + raw_id
        out += bytes([2, 0, 0])  # field framing, no sequence/final
        return bytes(out)

    def open(self, wrapper: Any) -> str:
        if not isinstance(wrapper, dict):
            raise CryptoError(INVALID)
        if len(wrapper) != 2 or wrapper.get("$wbEncrypted") != 1:
            raise CryptoError(UNSUPPORTED)
        encoded = wrapper.get("envelope")
        if not isinstance(encoded, str):
            raise CryptoError(INVALID)
        try:
            envelope = json.loads(b64_decode_strict(encoded).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CryptoError(INVALID) from exc
        if not isinstance(envelope, dict):
            raise CryptoError(INVALID)
        if envelope.get("suite") != 1:
            raise CryptoError(UNSUPPORTED)
        if envelope.get("keyId") != self.id:
            raise CryptoError(KEY_MISMATCH)
        nonce = b64_decode_strict(envelope.get("nonce", ""))
        tag = b64_decode_strict(envelope.get("authTag", ""))
        if len(nonce) != 12 or len(tag) != 16:
            raise CryptoError(INVALID)
        ciphertext = b64_decode_strict(envelope.get("ciphertext", "")) + tag
        try:
            plaintext = aes_gcm_decrypt(self.bytes, nonce, ciphertext, self.aad())
        except CryptoError:
            raise
        except Exception as exc:
            raise CryptoError(INVALID) from exc
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CryptoError(INVALID) from exc


    def seal(self, plaintext: str) -> dict:
        """对称的加密实现（Rust 的 OfficialKey::seal）。仅用于自检/往返验证。"""
        nonce = os.urandom(12)
        ciphertext = aes_gcm_encrypt(self.bytes, nonce, plaintext.encode("utf-8"), self.aad())
        envelope = {
            "suite": 1,
            "keyId": self.id,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "authTag": base64.b64encode(ciphertext[-16:]).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext[:-16]).decode("ascii"),
        }
        raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return {"$wbEncrypted": 1, "envelope": base64.b64encode(raw).decode("ascii")}


def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """返回 ciphertext || tag(16)。"""
    if len(nonce) != 12:
        raise CryptoError("nonce 长度必须为 12 字节")
    aes = _AES(key)
    h = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    j0 = (int.from_bytes(nonce, "big") << 32) | 1
    ciphertext = _gctr(aes, _inc32(j0), plaintext)
    s = _ghash(
        h,
        _pad16(aad)
        + _pad16(ciphertext)
        + (len(aad) * 8).to_bytes(8, "big")
        + (len(ciphertext) * 8).to_bytes(8, "big"),
    )
    ek = aes.encrypt_block(j0.to_bytes(16, "big"))
    tag = bytes(a ^ b for a, b in zip(s.to_bytes(16, "big"), ek))
    return ciphertext + tag


def is_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and value.get("$wbEncrypted") == 1


def contains_encrypted_wrapper(value: Any) -> bool:
    if isinstance(value, dict):
        return "$wbEncrypted" in value or any(
            contains_encrypted_wrapper(v) for v in value.values()
        )
    if isinstance(value, list):
        return any(contains_encrypted_wrapper(v) for v in value)
    return False


# --------------------------------------------------------------------------
# 步骤 1+2：从官方客户端读取并派生密钥
# --------------------------------------------------------------------------


def resolve_executable() -> Path | None:
    """定位 WorkBuddy 客户端可执行文件（对应 Rust 的 resolve_workbuddy_launch_path）。"""
    for var in ("WORKBUDDY_EXECUTABLE", "WORKBUDDY_TEST_EXECUTABLE"):
        candidate = os.environ.get(var)
        if candidate and Path(candidate).is_file():
            return Path(candidate)

    home = Path.home()
    candidates: list[Path] = []

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        for base in filter(None, (local_app_data, program_files, program_files_x86)):
            candidates.append(Path(base) / "WorkBuddy" / "WorkBuddy.exe")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "WorkBuddy" / "WorkBuddy.exe")
        # 自定义盘符安装（例如 G:\Program Files\WorkBuddy）
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            for folder in ("Program Files", "Program Files (x86)"):
                candidates.append(Path(f"{letter}:\\{folder}\\WorkBuddy\\WorkBuddy.exe"))
        candidates += _windows_registry_candidates()
    elif sys.platform == "darwin":
        candidates += [
            Path("/Applications/WorkBuddy.app/Contents/MacOS/WorkBuddy"),
            home / "Applications/WorkBuddy.app/Contents/MacOS/WorkBuddy",
        ]
    else:
        candidates += [
            Path("/opt/WorkBuddy/workbuddy"),
            Path("/usr/bin/workbuddy"),
            Path("/usr/lib/workbuddy/workbuddy"),
            home / ".local/bin/workbuddy",
        ]

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _windows_registry_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    import winreg

    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    found: list[Path] = []
    for root, subkey in roots:
        try:
            handle = winreg.OpenKey(root, subkey)
        except OSError:
            continue
        index = 0
        while True:
            try:
                name = winreg.EnumKey(handle, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(handle, name) as item:
                    try:
                        display = str(winreg.QueryValueEx(item, "DisplayName")[0])
                    except OSError:
                        continue
                    if "workbuddy" not in display.lower():
                        continue
                    for field in ("InstallLocation", "UninstallString", "DisplayIcon"):
                        try:
                            raw = str(winreg.QueryValueEx(item, field)[0]).strip('"')
                        except OSError:
                            continue
                        if not raw:
                            continue
                        path = Path(raw.split(".exe")[0] + ".exe") if raw.lower().endswith(".exe") else Path(raw)
                        if path.is_dir():
                            found.append(path / "WorkBuddy.exe")
                        elif path.is_file() and path.name.lower().startswith("workbuddy"):
                            found.append(path)
            except OSError:
                continue
        winreg.CloseKey(handle)
    return found


def load_official_key(exe: Path | None = None) -> OfficialKey:
    exe = exe or resolve_executable()
    if not exe or not Path(exe).is_file():
        raise CryptoError(NO_CLIENT)

    env = os.environ.copy()
    env["ELECTRON_RUN_AS_NODE"] = "1"
    env.pop("NODE_OPTIONS", None)

    kwargs: dict[str, Any] = dict(
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=KEY_TIMEOUT,
    )
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    try:
        proc = subprocess.run([str(exe), "-e", KEY_SCRIPT], **kwargs)  # noqa: S603
    except subprocess.TimeoutExpired as exc:
        raise CryptoError("读取 WorkBuddy 官方密钥超时，请重试") from exc
    except OSError as exc:
        raise CryptoError(f"无法启动 WorkBuddy 客户端：{exc}") from exc

    output = proc.stdout or b""
    try:
        if proc.returncode != 0 or len(output) != 44:
            raise CryptoError(
                "当前 WorkBuddy 客户端未提供可用的官方密钥接口，请更新客户端后重试"
            )
        decoded = b64_decode_strict(output.decode("ascii"))
        if len(decoded) != 32:
            raise CryptoError(INVALID)
        return OfficialKey(decoded)
    finally:
        # 尽量抹掉内存中的密钥材料
        if isinstance(output, bytearray):
            output[:] = b"\x00" * len(output)
        del output


# --------------------------------------------------------------------------
# 步骤 3：定位并解密会话文件
# --------------------------------------------------------------------------

_SKIP_DIRS = {
    "logs", "logs-old", "cache", "Cache", "Code Cache", "CodeCache", "GPUCache",
    "blob_storage", "Crashpad", "Service Worker", "Shared Dictionary",
    "SharedStorage", "ShaderCache", "DawnGraphiteCache", "DawnWebGPUCache",
    "traces", "file-history", "media-index", "backup", "backups",
    "node_modules", ".git", "sessions", "plans",
}
_MAX_SCAN_BYTES = 8 * 1024 * 1024
_ENVELOPE_RE = re.compile(rb'"envelope"\s*:\s*"([A-Za-z0-9+/=]{16,})"')


# --------------------------------------------------------------------------
# 官方路径规则（与 workbuddy_account.rs 一致）
# --------------------------------------------------------------------------

WORKBUDDY_AUTH_FILE_NAME = "workbuddy-desktop.info"
ACCOUNTS_INDEX_FILE = "workbuddy_accounts.json"
ACCOUNTS_DIR = "workbuddy_accounts"


def default_workbuddy_data_dir() -> Path:
    """get_default_workbuddy_data_dir() -> home/.workbuddy/app"""
    return Path.home() / ".workbuddy" / "app"


def get_workbuddy_shared_auth_dir() -> Path | None:
    """get_workbuddy_shared_auth_dir()：跨平台共享登录目录。"""
    home = Path.home()
    if sys.platform == "darwin":
        return (
            home / "Library" / "Application Support"
            / "CodeBuddyExtension" / "Data" / "Public" / "auth"
        )
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else home / "AppData" / "Local"
        return root / "CodeBuddyExtension" / "Data" / "Public" / "auth"
    return home / ".local" / "share" / "CodeBuddyExtension" / "Data" / "Public" / "auth"


def get_default_workbuddy_auth_file_path() -> Path | None:
    directory = get_workbuddy_shared_auth_dir()
    return directory / WORKBUDDY_AUTH_FILE_NAME if directory else None


def workbuddy_logout_marker_path(auth_file: Path) -> Path:
    """存在该文件即表示官方客户端已登出，登录信息不可用。"""
    return Path(f"{auth_file}.logged-out")


def get_accounts_index_path() -> Path:
    return default_workbuddy_data_dir() / ACCOUNTS_INDEX_FILE


def get_accounts_dir() -> Path:
    return default_workbuddy_data_dir() / ACCOUNTS_DIR


def auth_file_candidates() -> list[tuple[str, Path]]:
    """按官方优先级列出候选登录文件，附带来源说明。"""
    found: list[tuple[str, Path]] = []

    env_path = os.environ.get("WORKBUDDY_AUTH_FILE")
    if env_path:
        found.append(("env:WORKBUDDY_AUTH_FILE", Path(env_path)))

    default_path = get_default_workbuddy_auth_file_path()
    if default_path:
        found.append(("shared-auth-dir", default_path))

    found.append(("accounts-index", get_accounts_index_path()))

    directory = get_accounts_dir()
    if directory.is_dir():
        for child in sorted(directory.glob("*.json"))[:20]:
            found.append(("accounts-dir", child))
    return found


def default_roots() -> list[Path]:
    """仅在 --deep 兜底扫描时使用。"""
    roots = [Path.home() / ".workbuddy"]
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        roaming = os.environ.get("APPDATA")
        for base in filter(None, (roaming, local)):
            roots.append(Path(base) / "WorkBuddy")
    elif sys.platform == "darwin":
        roots.append(Path.home() / "Library" / "Application Support" / "WorkBuddy")
    else:
        roots.append(Path.home() / ".config" / "WorkBuddy")
    return [r for r in roots if r.is_dir()]


def _shape_score(document: Any) -> int:
    """按官方会话文件的形状打分，避免把会话历史/业务数据误当成凭据文件。"""
    if not isinstance(document, dict):
        return 0
    auth = document.get("auth")
    if isinstance(auth, dict):
        for name in _AUTH_FIELDS:
            if is_wrapper(auth.get(name)) or name in auth:
                return 3
    for container in ("account", "accounts", "allAccounts"):
        node = document.get(container)
        nodes = node if isinstance(node, list) else [node]
        for item in nodes:
            if isinstance(item, dict) and any(
                is_wrapper(item.get(f)) or f in item for f in _ACCOUNT_FIELDS
            ):
                return 2
    return 1


def find_auth_files(roots: Iterable[Path], limit: int = 20) -> list[tuple[Path, int, Any]]:
    """查找包含官方加密封装（$wbEncrypted）的文件，并按凭据文件形状排序。"""
    hits: list[Path] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    if path.stat().st_size > _MAX_SCAN_BYTES:
                        continue
                    data = path.read_bytes()
                except OSError:
                    continue
                if b"$wbEncrypted" in data:
                    hits.append(path)
                    if len(hits) >= limit:
                        break
            if len(hits) >= limit:
                break
    scored: list[tuple[Path, int, Any]] = []
    for path in hits:
        try:
            document = json.loads(path.read_bytes().decode("utf-8"))
        except Exception:
            document = None
        scored.append((path, _shape_score(document), document))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _walk(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")


def decode_tree(node: Any, key: OfficialKey) -> Any:
    """递归解密任意位置的官方加密封装；读取用途，不涉及回写。"""
    if isinstance(node, dict):
        if is_wrapper(node):
            return key.open(node)
        return {k: decode_tree(v, key) for k, v in node.items()}
    if isinstance(node, list):
        return [decode_tree(v, key) for v in node]
    return node


def extract_raw_envelopes(data: bytes, key: OfficialKey) -> list[str]:
    """兜底：文件不是合法 JSON（例如 leveldb 碎片）时，直接抽取 envelope 解密。"""
    out: list[str] = []
    for match in _ENVELOPE_RE.finditer(data):
        try:
            wrapper = {"$wbEncrypted": 1, "envelope": match.group(1).decode("ascii")}
            text = key.open(wrapper)
        except Exception:
            continue
        if text not in out:
            out.append(text)
    return out


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

_ACCOUNT_FIELDS = ("phoneNumber", "departmentFullName", "nickname")
_AUTH_FIELDS = ("accessToken", "refreshToken")


def mask(value: str) -> str:
    if len(value) <= 12:
        return value[:3] + "*" * max(0, len(value) - 3)
    return f"{value[:6]}{'*' * 8}{value[-4:]}"


def _mask_env_value(value: str) -> str:
    """环境变量值按 `手机号:access_token:refresh_token` 分段脱敏。"""
    return ":".join(mask(part) for part in value.split(":"))


def json_object_string_field(obj: dict, keys: Iterable[str]) -> str | None:
    """json_object_string_field：按给定键序取第一个非空字符串。"""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_local_access_token(value: Any) -> str | None:
    """parse_local_access_token：token → access_token → accessToken，
    其次 auth.accessToken → auth.access_token，再其次 session / data 递归。"""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            found = parse_local_access_token(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        direct = json_object_string_field(value, ("token", "access_token", "accessToken"))
        if direct:
            return direct
        auth = value.get("auth")
        if isinstance(auth, dict):
            nested = json_object_string_field(auth, ("accessToken", "access_token"))
            if nested:
                return nested
        for key in ("session", "data"):
            if key in value:
                nested = parse_local_access_token(value[key])
                if nested:
                    return nested
    return None


def extract_local_workbuddy_token_parts(token: str) -> tuple[str | None, str] | None:
    """extract_local_workbuddy_token_parts：拆分 `uid+token` 形式的旧版 token。"""
    trimmed = token.strip()
    if not trimmed:
        return None
    if "+" in trimmed:
        uid, _, suffix = trimmed.partition("+")
        if not suffix.strip():
            return None
        return (uid.strip() or None, suffix.strip())
    return (None, trimmed)


def normalize_local_workbuddy_token(token: str) -> str | None:
    """normalize_local_workbuddy_token：去掉 `uid+` 前缀，只保留真正的凭据。"""
    trimmed = token.strip()
    if not trimmed:
        return None
    if "+" in trimmed:
        suffix = trimmed.partition("+")[2].strip()
        if suffix:
            return suffix
    return trimmed


def extract_uid_from_jwt(token: str) -> str | None:
    """extract_uid_from_jwt：新版 JWT 的 payload.sub 即账号 uid。"""
    parts = token.split(".")
    if len(parts) < 2:
        return None
    segment = parts[1]
    padding = "=" * (-len(segment) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            raw = decoder(segment + padding)
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            sub = payload.get("sub")
            if isinstance(sub, str) and sub.strip():
                return sub.strip()
    return None


def build_local_payload(raw_token: str, parsed: Any) -> dict[str, Any]:
    """build_local_import_payload：按官方键序回填账号画像字段。"""
    root = parsed if isinstance(parsed, dict) else {}
    account_obj = root.get("account") if isinstance(root.get("account"), dict) else {}
    auth_obj = root.get("auth") if isinstance(root.get("auth"), dict) else {}

    uid_from_token, _ = extract_local_workbuddy_token_parts(raw_token) or (None, raw_token)
    uid = (
        json_object_string_field(root, ("uid",))
        or json_object_string_field(account_obj, ("uid", "id"))
        or uid_from_token
        or extract_uid_from_jwt(raw_token)
    )
    nickname = json_object_string_field(root, ("nickname", "name")) or json_object_string_field(
        account_obj, ("nickname", "label")
    )
    email = (
        json_object_string_field(root, ("email",))
        or json_object_string_field(account_obj, ("email",))
        or json_object_string_field(auth_obj, ("email",))
        or nickname
        or uid
        or "unknown"
    )
    refresh_token = json_object_string_field(
        root, ("refreshToken", "refresh_token")
    ) or json_object_string_field(auth_obj, ("refreshToken", "refresh_token"))

    phones: list[str] = []
    containers: list[Any] = [account_obj]
    for name in ("accounts", "allAccounts"):
        items = root.get(name)
        if isinstance(items, list):
            containers.extend(i for i in items if isinstance(i, dict))
    for item in containers:
        phone = json_object_string_field(item, ("phoneNumber", "phone", "phone_number", "mobile"))
        if phone and phone not in phones:
            phones.append(phone)

    return {
        "uid": uid or "",
        "email": email,
        "nickname": nickname or "",
        "phoneNumber": phones[0] if phones else "",
        "access_token": normalize_local_workbuddy_token(raw_token) or "",
        "refresh_token": refresh_token or "",
        "all_phone_numbers": phones,
    }


def collect_dump(decoded: Any) -> list[tuple[str, str]]:
    """列出所有解密成功的字段路径与值，便于排查凭据到底存在哪个文件。"""
    out: list[tuple[str, str]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                visit(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                visit(v, f"{path}[{i}]")
        elif isinstance(node, str) and node:
            out.append((path, node))

    visit(decoded, "")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="读取本机 WorkBuddy 官方密钥并解密 phoneNumber / access_token / refresh_token"
    )
    parser.add_argument("--exe", help="WorkBuddy 客户端可执行文件绝对路径")
    parser.add_argument("--auth-file", help="登录信息文件绝对路径（覆盖自动定位）")
    parser.add_argument("--search-root", action="append", help="配合 --deep 的额外搜索根目录")
    parser.add_argument("--deep", action="store_true", help="官方路径未命中时，全盘扫描兜底")
    parser.add_argument("--mask", action="store_true", help="输出时脱敏")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--dump", action="store_true", help="列出所有解密成功的字段（排查用）")
    parser.add_argument("--self-test", action="store_true", help="用官方测试向量自检后退出")
    args = parser.parse_args(argv)

    if args.self_test:
        key = OfficialKey(bytes([7] * 32))
        if key.id != "4bb06f8e4e3a7715":
            print("[FAIL] keyId 派生与官方夹具不一致")
            return 1
        wrapper = {
            "$wbEncrypted": 1,
            "envelope": base64.b64encode(SELF_TEST_ENVELOPE.encode()).decode(),
        }
        try:
            plain = key.open(wrapper)
        except CryptoError as exc:
            print(f"[FAIL] 官方夹具解密失败：{exc}")
            return 1
        ok = plain == SELF_TEST_PLAINTEXT
        print(f"[{'OK' if ok else 'FAIL'}] 官方夹具解密结果：{plain!r}")
        return 0 if ok else 1

    try:
        exe = Path(args.exe) if args.exe else resolve_executable()
        if not exe or not exe.is_file():
            raise CryptoError(NO_CLIENT)
        official_key = load_official_key(exe)
    except CryptoError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    # 候选文件：默认按官方路径规则定位；--deep 才回退到全盘扫描
    candidates: list[tuple[str, Path]] = []
    if args.auth_file:
        candidates.append(("cli:--auth-file", Path(args.auth_file)))
    else:
        candidates.extend(auth_file_candidates())
        if args.deep:
            roots = default_roots() + [Path(r) for r in (args.search_root or [])]
            for path, score, _document in find_auth_files(roots):
                candidates.append((f"deep-scan(score={score})", path))

    ordered: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for source, path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append((source, path))

    if not ordered:
        print("[ERROR] 无法定位 WorkBuddy 登录信息路径", file=sys.stderr)
        return 3

    payload: dict[str, Any] = {
        "exe": str(exe),
        "keyId": official_key.id,
        "source": "",
        "file": "",
        "uid": "",
        "email": "",
        "nickname": "",
        "phoneNumber": "",
        "access_token": "",
        "refresh_token": "",
        "all_phone_numbers": [],
        "candidates": [],
        "decoded_strings": [],
        "dump": [],
        "env": {},
    }

    for source, path in ordered:
        entry: dict[str, Any] = {"source": source, "file": str(path), "status": ""}
        payload["candidates"].append(entry)

        if not path.is_file():
            entry["status"] = "missing"
            continue
        if workbuddy_logout_marker_path(path).exists():
            entry["status"] = "logged-out"
            continue

        try:
            raw = path.read_bytes()
        except OSError as exc:
            entry["status"] = f"unreadable: {exc}"
            continue
        text = raw.decode("utf-8", errors="replace")

        parsed: Any = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None

        if parsed is not None and contains_encrypted_wrapper(parsed):
            try:
                parsed = decode_tree(parsed, official_key)
                entry["decrypted"] = True
                if args.dump:
                    for field_path, value in collect_dump(parsed)[:50]:
                        payload["dump"].append(
                            {"file": path.name, "field": field_path, "value": value}
                        )
            except CryptoError as exc:
                entry["status"] = f"decrypt-failed: {exc}"
                continue

        # Rust 规则：JSON 登录文件里没有 token 时必须报错，不能把整个 JSON 当凭据
        token = parse_local_access_token(parsed) if parsed is not None else None
        if token is None:
            stripped = text.strip()
            if parsed is None and stripped:
                token = stripped  # legacy：整个文件就是 token
            else:
                entry["status"] = "no-token"
                continue

        info = build_local_payload(token, parsed)
        entry["status"] = "ok"
        entry["uid"] = info["uid"]
        if payload["access_token"]:
            continue  # 已取得更高优先级的凭据

        # 供外部脚本读取：手机号:access_token:refresh_token
        env_value = ""
        if info["phoneNumber"] and info["access_token"] and info["refresh_token"]:
            env_value = ":".join(
                (info["phoneNumber"], info["access_token"], info["refresh_token"])
            )

        payload.update(
            {
                "source": source,
                "file": str(path),
                "uid": info["uid"],
                "email": info["email"],
                "nickname": info["nickname"],
                "phoneNumber": info["phoneNumber"],
                "access_token": info["access_token"],
                "refresh_token": info["refresh_token"],
                "all_phone_numbers": info["all_phone_numbers"],
                "env": {"WORKBUDDY_REFRESH_TOKEN": env_value} if env_value else {},
            }
        )

    if args.json:
        print(json.dumps(_apply_mask(payload, args.mask), ensure_ascii=False, indent=2))
        return 0 if payload["access_token"] else 4

    print("=" * 68)
    print("WorkBuddy 本地凭据读取（只读，不修改客户端任何状态）")
    print("=" * 68)
    print(f"客户端     : {payload['exe']}")
    print(f"密钥 ID    : {payload['keyId']}")
    print("候选路径   :")
    for entry in payload["candidates"][:10]:
        print(f"  [{entry['status']:<10}] {entry['source']:<16} {entry['file']}")
    print("-" * 68)

    def show(label: str, value: str) -> None:
        shown = mask(value) if (args.mask and value) else (value or "(未找到)")
        print(f"{label:<12}: {shown}")

    show("phoneNumber", payload["phoneNumber"])
    show("access_token", payload["access_token"])
    show("refresh_token", payload["refresh_token"])
    if payload["uid"] or payload["nickname"]:
        print("-" * 68)
        show("uid", payload["uid"])
        show("nickname", payload["nickname"])
    if len(payload["all_phone_numbers"]) > 1:
        print("-" * 68)
        print(
            "其他手机号 : "
            + ", ".join(mask(p) if args.mask else p for p in payload["all_phone_numbers"][1:])
        )
    if args.dump and payload["dump"]:
        print("-" * 68)
        print("解密到的字段（--dump）：")
        for item in payload["dump"][:50]:
            print(
                f"  [{item['file']}] {item['field']} = "
                f"{mask(item['value']) if args.mask else item['value'][:120]}"
            )
    print("-" * 68)
    if payload["env"]:
        print("# 可复制为环境变量供外部脚本读取：手机号:access_token:refresh_token")
        for name, value in payload["env"].items():
            print(f"{name}={_mask_env_value(value) if args.mask else value}")
    else:
        print("环境变量   : 未生成（手机号 / access_token / refresh_token 有缺失）")
    if not payload["access_token"]:
        print("-" * 68)
        statuses = {e["status"] for e in payload["candidates"]}
        hint = "（已登出，官方客户端已退出登录）" if "logged-out" in statuses else ""
        print(f"提示：未取到 access token{hint}。可加 --dump 查看详情，或用 --auth-file 指定路径。")
    print("=" * 68)
    return 0 if payload["access_token"] else 4


def _apply_mask(payload: dict[str, Any], do_mask: bool) -> dict[str, Any]:
    if not do_mask:
        return payload
    out = dict(payload)
    for field in ("phoneNumber", "access_token", "refresh_token", "uid", "email", "nickname"):
        if out.get(field):
            out[field] = mask(out[field])
    if out.get("all_phone_numbers"):
        out["all_phone_numbers"] = [mask(p) for p in out["all_phone_numbers"]]
    if out.get("env"):
        out["env"] = {name: _mask_env_value(value) for name, value in out["env"].items()}
    if out.get("decoded_strings"):
        out["decoded_strings"] = [mask(t) for t in out["decoded_strings"]]
    return out


if __name__ == "__main__":
    sys.exit(main())
