#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@source: https://gh-proxy.org/github.com/L0NE-6/Trae-AutoCheckin/blob/main/trae_get_token.py

Trae Token 提取器 · trae_get_token.py
────────────────────────────────────────────────────────────
一键从 Trae 官方客户端本地数据里解出 refreshToken / accessToken，
免抓包、免装依赖（纯 Python 标准库，自己实现 AES-128-CBC）。

✨ 特性
  • 零依赖     纯标准库，无需 pip install
  • 免抓包     直接读客户端 storage.json 并自动解密
  • 一键输出   直接打印 refreshToken，复制进青龙环境变量即可
  • 自动找路径 自动探测 Trae CN / TRAE SOLO 等常见目录

🚀 使用方法
  1. 打开 Trae 客户端并登录一次（确保已产生凭据）
  2. 运行：python trae_get_token.py
  3. 复制输出的 TRAE_REFRESH_TOKEN 值，填入青龙面板环境变量

  多账号一键生成 TRAE_ACCOUNTS（推荐）：
  python trae_get_token.py --accounts
  会把「本机登录态 + 账号目录里的 trae-<uid>.json」合并成一个 JSON 数组打印出来，
  整行复制进 TRAE_ACCOUNTS 环境变量即可，不用再手动拼 JSON。

  导出设备密钥（新版续期必需）：
  python trae_get_token.py --export-keys
  会打印 TRAE_DEVICE_KEY_PEM / TRAE_DEVICE_PUB_PEM / TRAE_DEVICE_ID / TRAE_MACHINE_ID
  四个值，填入青龙 / GitHub Actions 的环境变量或 Secrets 即可。
  原因：Trae 新版 ExchangeToken 要求带设备签名，缺了会报 20405 Device proof required。

📌 说明
  • 只读取本机自己的客户端凭据，不联网、不上传，安全无风险。
  • 多账号：在客户端依次登录每个账号，各跑一次 --accounts 就会累积到同一个数组里。
  • 账号目录可用 TRAE_ACCOUNT_DIR 指定，默认扫当前目录和脚本所在目录的 trae-*.json。
────────────────────────────────────────────────────────────
"""
import base64, hashlib, json, os, sys, re

# ── 让 Windows 控制台也能正常打印 emoji ──
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SALT_A = bytes([82,9,106,213,48,54,165,56,191,64,163,158,129,243,215,251,124,227,57,130,155,47,255,135,52,142,67,68,196,222,233,203,84,123,148,50,166,194,35,61,238,76,149,11,66,250,195,78,8,46,161,102,40,217,36,178,118,91,162,73,109,139,209,37])
SALT_B = bytes([31,221,168,51,136,7,199,49,177,18,16,89,39,128,236,95,96,81,127,169,25,181,74,13,45,229,122,159,147,201,156,239,160,224,59,77,174,42,245,176,200,235,187,60,131,83,153,97,23,43,4,126,186,119,214,38,225,105,20,99,85,33,12,125])
SALT_AES = bytes(a ^ b for a, b in zip(SALT_A, SALT_B))
STORAGE_KEY = "iCubeAuthInfo://icube.cloudide"

# ══════════ 纯标准库 AES-128-CBC 解密 ══════════
def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1: p ^= a
        hi = a & 0x80; a = (a << 1) & 0xFF
        if hi: a ^= 0x1B
        b >>= 1
    return p

def _build_sbox():
    inv = [0] * 256
    for i in range(1, 256):
        for j in range(1, 256):
            if _gmul(i, j) == 1:
                inv[i] = j; break
    sb = [0] * 256
    for i in range(256):
        x = inv[i] if i else 0; s = x
        for _ in range(4):
            x = ((x << 1) | (x >> 7)) & 0xFF; s ^= x
        sb[i] = s ^ 0x63
    return sb

SBOX = _build_sbox()
INV = [0] * 256
for _i, _v in enumerate(SBOX): INV[_v] = _i
RC = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1B,0x36]

def _expand(key):
    w = [list(key[i*4:i*4+4]) for i in range(4)]
    for i in range(4, 44):
        t = w[i-1][:]
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [SBOX[b] for b in t]
            t[0] ^= RC[i//4-1]
        w.append([w[i-4][j] ^ t[j] for j in range(4)])
    return w

def _rk(w, r):
    ws = w[r*4:r*4+4]
    return [ws[c][k] for c in range(4) for k in range(4)]

def _addrk(s, k): return [s[i] ^ k[i] for i in range(16)]
def _isub(s): return [INV[b] for b in s]
def _ishift(s): return [s[0],s[13],s[10],s[7], s[4],s[1],s[14],s[11], s[8],s[5],s[2],s[15], s[12],s[9],s[6],s[3]]

def _imix(s):
    o = []
    for c in range(4):
        a = s[c*4:c*4+4]
        o += [_gmul(a[0],14)^_gmul(a[1],11)^_gmul(a[2],13)^_gmul(a[3],9),
              _gmul(a[0],9)^_gmul(a[1],14)^_gmul(a[2],11)^_gmul(a[3],13),
              _gmul(a[0],13)^_gmul(a[1],9)^_gmul(a[2],14)^_gmul(a[3],11),
              _gmul(a[0],11)^_gmul(a[1],13)^_gmul(a[2],9)^_gmul(a[3],14)]
    return o

def aes128_cbc_decrypt(key, iv, data):
    w = _expand(key); out = b""; prev = list(iv)
    for off in range(0, len(data), 16):
        blk = list(data[off:off+16]); s = _addrk(blk, _rk(w, 10))
        for r in range(9, 0, -1):
            s = _ishift(s); s = _isub(s); s = _addrk(s, _rk(w, r)); s = _imix(s)
        s = _ishift(s); s = _isub(s); s = _addrk(s, _rk(w, 0))
        out += bytes(a ^ b for a, b in zip(s, prev)); prev = blk
    return out

# ══════════ 解密 storage.json 里的凭据 ══════════
def decrypt_storage_value(b64):
    buf = base64.b64decode(b64)
    rb, enc = buf[6:38], buf[38:]
    h = hashlib.sha512(rb).digest()
    fh = hashlib.sha512(h + SALT_AES).digest()
    pt = aes128_cbc_decrypt(fh[:16], fh[16:32], enc)[64:]
    # 桌面端写盘用 PKCS7 填充；老版本可能用零填充，两种都兼容
    pad = pt[-1] if pt else 0
    if 1 <= pad <= 16:
        return pt[:-pad]
    return pt.rstrip(b"\x00").rstrip()

def candidate_paths():
    home = os.path.expanduser("~")
    names = ("Trae CN", "TRAE SOLO CN", "TRAE SOLO", "Trae")
    sub = ("User", "globalStorage", "storage.json")
    ad = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    for n in names:
        p = os.path.join(ad, n, *sub)
        if os.path.isfile(p): yield p
    lib = os.path.join(home, "Library", "Application Support")
    for n in names:
        p = os.path.join(lib, n, *sub)
        if os.path.isfile(p): yield p
    for base in (home, os.path.join(home, ".config")):
        for n in (".trae-cn", ".trae", "Trae CN", "TRAE SOLO CN"):
            p = os.path.join(base, n, *sub)
            if os.path.isfile(p): yield p

_DEVICE_ID_RE = re.compile(r"^\d{12,20}$")


def is_valid_device_id(d):
    """设备号是否为客户端注册过的那种十进制数字串（位数不固定，15/16 位都见过）。"""
    return bool(_DEVICE_ID_RE.match(str(d or "").strip()))


def device_id_in(path):
    """从 storage.json 里取客户端真实设备号；取不到返回空串（纯读文件）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception:
        return ""
    if not isinstance(s, dict):
        return ""
    for k, v in s.items():
        if k.startswith("iCubeAuthInfo://icube-dc:"):
            d = k[len("iCubeAuthInfo://icube-dc:"):].strip()
            if is_valid_device_id(d):
                return d
        elif k.rstrip(":") == "iCubeAuthInfo://icube-dc" and is_valid_device_id(v):
            return str(v).strip()
    return ""

def extract(path):
    s = json.load(open(path, encoding="utf-8"))
    enc = s.get(STORAGE_KEY)
    if not enc: return None
    txt = decrypt_storage_value(enc).decode("utf-8", "replace")
    rt = re.search(r'"refreshToken"\s*:\s*"([^"]+)"', txt)
    at = re.search(r'"token"\s*:\s*"([^"]+)"', txt)
    uid = re.search(r'"userId"\s*:\s*"(\d+)"', txt)
    nick = re.search(r'"username"\s*:\s*"([^"]*)"', txt)
    return {"refreshToken": rt.group(1) if rt else None,
            "accessToken": at.group(1) if at else None,
            "uid": uid.group(1) if uid else None,
            "nickname": nick.group(1) if nick else None}

def device_keys():
    """从本机 storage.json 取设备私钥/公钥/设备号/machineId（新版续期用）。"""
    for path in candidate_paths():
        try:
            s = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        did = device_id_in(path)
        if not did:
            print("[!] %s 里没找到客户端真实设备号（键 iCubeAuthInfo://icube-dc:<数字>）" % path,
                  file=sys.stderr)
            continue
        enc = s.get("iCubeAuthInfo://icube-dc:%s" % did)
        if not enc:
            continue
        try:
            dev = json.loads(decrypt_storage_value(enc.strip()).decode("utf-8", "replace"))
        except Exception:
            continue
        priv = (dev.get("privateKeyPEM") or "").strip()
        pub = (dev.get("publicKeyPEM") or "").strip()
        if priv and pub:
            return {"deviceId": did, "privateKeyPem": priv, "publicKeyPem": pub,
                    "machineId": (s.get("telemetry.machineId") or "").strip(), "from": path}
    return None


def export_keys_mode():
    """打印新版续期所需的设备密钥环境变量。"""
    k = device_keys()
    if not k:
        print("[X] 没找到设备密钥。请先在 Trae 客户端登录一次，再运行本脚本。")
        return 1
    print("=" * 64)
    print("设备密钥（来源: %s）" % k["from"])
    print("=" * 64)
    print("TRAE_DEVICE_ID=%s" % k["deviceId"])
    print("TRAE_MACHINE_ID=%s" % k["machineId"])
    print()
    print("TRAE_DEVICE_KEY_PEM=%s" % k["privateKeyPem"].replace("\n", "\\n"))
    print()
    print("TRAE_DEVICE_PUB_PEM=%s" % k["publicKeyPem"].replace("\n", "\\n"))
    print("=" * 64)
    print("提示：PEM 里的换行已写成 \\n，直接整行复制即可（脚本会自动还原）。")
    return 0


def jwt_uid(token):
    """从 accessToken 里解出 uid，用来判断 token 属于哪个账号。"""
    try:
        p = token.split(".")[1]
        pad = "=" * (-len(p) % 4)
        return str(json.loads(base64.urlsafe_b64decode(p + pad)).get("data", {}).get("id", ""))
    except Exception:
        return ""


def cache_files():
    """token 缓存的候选位置（与签到脚本保持一致）。"""
    env = os.environ.get("TRAE_TOKEN_CACHE", "").strip()
    if env:
        yield env
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.join("/ql/data/config", ".trae_token_cache.json")
    yield os.path.join(here, ".trae_token_cache.json")
    yield os.path.join(os.getcwd(), ".trae_token_cache.json")


def load_cache_tokens():
    """读 token 缓存，按 uid 归位。缓存里是最近一次续期的结果，通常比账号文件新。"""
    out = {}
    for p in cache_files():
        if not os.path.isfile(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for v in d.values():
            at = (v or {}).get("accessToken") or ""
            rt = (v or {}).get("refreshToken") or ""
            allow = (v or {}).get("expiresAt") or 0
            if not (at and rt):
                continue
            u = jwt_uid(at)
            if not u:
                continue
            old = out.get(u)
            if not old or (allow or 0) > (old.get("expiresAt") or 0):
                out[u] = {"accessToken": at, "refreshToken": rt, "expiresAt": allow}
    return out


def load_from_dir(d):
    """扫描目录里的 trae-<uid>.json（账号凭据文件），取出可用账号。"""
    out = []
    if not d or not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or not fn.startswith("trae-"):
            continue
        try:
            o = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        except Exception:
            continue
        a = o.get("auth") or {}
        if not a.get("refreshToken"):
            continue
        acc = o.get("account") or {}
        uid = str(acc.get("uid") or "")
        nick = str(acc.get("nickname") or "")
        out.append({"accessToken": a.get("accessToken") or "",
                    "refreshToken": a["refreshToken"],
                    "uid": uid or nick or fn,
                    "name": nick or uid or fn})
    return out


def accounts_mode():
    """把本机登录态 + 账号目录里的 trae-*.json 合并成一个 TRAE_ACCOUNTS JSON。"""
    entries, seen = [], set()
    seen_entries = {}

    def add(rec):
        key = rec.get("uid") or rec["refreshToken"][:24]
        if not rec.get("refreshToken") or key in seen:
            return
        seen.add(key)
        n = len(entries) + 1
        rec.setdefault("uid", "账号%d" % n)
        rec.setdefault("name", rec["uid"])
        entries.append(rec)
        seen_entries[str(rec.get("uid"))] = rec

    for p in candidate_paths():
        try:
            r = extract(p)
        except Exception as e:
            print("[!] 解析失败 %s: %s" % (p, e), file=sys.stderr); continue
        if not r or not r.get("refreshToken"):
            continue
        entry = {"accessToken": r.get("accessToken") or "",
                 "refreshToken": r["refreshToken"],
                 "uid": r.get("uid") or "",
                 "name": r.get("nickname") or r.get("uid") or ""}
        real_did = device_id_in(p)
        if real_did:
            entry["realDeviceId"] = real_did
        else:
            print("[!] %s 里没有客户端设备号，该账号签到会被服务端拒成 9074" % p,
                  file=sys.stderr)
        add(entry)

    dirs = [os.environ.get("TRAE_ACCOUNT_DIR", "").strip(),
            os.getcwd(),
            os.path.dirname(os.path.abspath(__file__))]
    for d in dirs:
        for rec in load_from_dir(d):
            add(rec)

    # 缓存里的 token 是最近一次续期的结果，通常比账号文件新 —— 覆盖掉旧的
    upgraded = 0
    for u, v in load_cache_tokens().items():
        old = seen_entries.get(u)
        if old:
            old["accessToken"] = v["accessToken"]
            old["refreshToken"] = v["refreshToken"]
            upgraded += 1
    if upgraded:
        print("[i] 已用 token 缓存里的最新凭据覆盖 %d 个账号" % upgraded, file=sys.stderr)

    if not entries:
        print("[X] 没找到任何可用账号。")
        print("    请先在 Trae 客户端登录一次，或把 trae-<uid>.json 放到当前目录。")
        return 1

    line = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    print("=" * 64)
    print("TRAE_ACCOUNTS  (共 %d 个账号，整行复制到环境变量)" % len(entries))
    print("=" * 64)
    for i, e in enumerate(entries, 1):
        print("  %d) %s  UID %s" % (i, e.get("name") or "-", e.get("uid") or "-"))
    print("-" * 64)
    print(line)
    print("=" * 64)
    print("提示：换行会被 JSON 破坏，请整行复制（不要手动折行）。")
    return 0


def main():
    args = [a.lower() for a in sys.argv[1:]]
    if args and args[0] in ("--export-keys", "--keys", "-k"):
        return export_keys_mode()
    if args and args[0] in ("--accounts", "-a", "accounts"):
        return accounts_mode()
    found = False
    for p in candidate_paths():
        try:
            r = extract(p)
        except Exception as e:
            print("[!] 解析失败 %s: %s" % (p, e)); continue
        if not r or not r.get("refreshToken"): continue
        found = True
        print("=" * 64)
        print("[来源] %s" % p)
        if r.get("uid"):
            print("[账号] %s (UID %s)" % (r.get("nickname") or "-", r["uid"]))
        print("-" * 64)
        print("TRAE_REFRESH_TOKEN = %s" % r["refreshToken"])
        print("=" * 64)
    if not found:
        print("[X] 没找到可用的 refreshToken。")
        print("    请先打开 Trae 客户端并登录一次，再运行本脚本。")
        print("    多账号一键生成：python trae_get_token.py --accounts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
