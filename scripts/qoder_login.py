#!/usr/bin/env python3
"""
@source  https://gh-proxy.org/github.com/L0NE-6/Qoder-Daily/raw/refs/heads/main/qoder_login.py

🧭 Qoder 设备授权登录工具
------------------------------------------------------------
在浏览器里打开授权页确认一次，即可拿到 access token + refresh token。

用法:
  python qoder_login.py                 # 中国版（默认）
  python qoder_login.py --region global # 国际版
  python qoder_login.py --note 主号     # 指定备注名
  python qoder_login.py --no-verify     # 跳过登录后校验

输出（直接作为环境变量的一行；中国版 QODER_TOKENS / 国际版 QODER_GLOBAL_TOKENS）:
  access_token|refresh_token

说明:
  · 设备授权流程，不需要验证码、不需要抓包；
  · 授权页在浏览器打开，用要登录的账号确认即可；
  运行环境：Python 3 + requests。
"""
import base64
import hashlib
import os
import sys
import time
import urllib.parse
import uuid
import webbrowser

import requests

import urllib3
urllib3.disable_warnings()

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

REGIONS = {
    "cn": {"web": "https://qoder.com.cn", "open_api": "https://openapi.qoder.com.cn", "label": "中国版"},
    "global": {"web": "https://qoder.com", "open_api": "https://openapi.qoder.sh", "label": "国际版"},
}
DEVICE_LOGIN_PATH = "/device/selectAccounts"
DEVICE_POLL_PATH = "/api/v1/deviceToken/poll"
CAMPAIGNS_PATH = "/sash/api/v1/me/campaigns"
MACHINE_ID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qoder_machine_id")
POLL_TIMEOUT = 300
POLL_INTERVAL = 2


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


def mask(text, keep=8):
    text = str(text or "")
    return text if len(text) <= keep + 4 else text[:keep] + "****" + text[-4:]


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def load_machine_id():
    home = os.path.expanduser("~")
    for candidate in (os.path.join(home, ".qoder-proxy", "machine_id"),
                      os.path.join(home, ".qoder", ".auth", "machine_id"),
                      os.path.join(home, ".qoder", "machine_id")):
        try:
            with open(candidate, encoding="utf-8") as handle:
                value = handle.read().strip()
            if value and len(value) <= 256:
                return value
        except Exception:
            continue
    try:
        with open(MACHINE_ID_FILE, encoding="utf-8") as handle:
            value = handle.read().strip()
        if value:
            return value
    except Exception:
        pass
    value = str(uuid.uuid4())
    try:
        with open(MACHINE_ID_FILE, "w", encoding="utf-8") as handle:
            handle.write(value)
    except Exception:
        pass
    return value


def request(method, url, headers=None, timeout=20, retries=3):
    last = None
    for attempt in range(retries):
        try:
            session = requests.Session()
            session.trust_env = False
            return session.request(method, url, headers=headers or {}, timeout=timeout, verify=False)
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("请求失败: %s" % last)


def json_of(response):
    try:
        return response.json()
    except Exception:
        return {}


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def start_device_login(region):
    verifier = b64url(os.urandom(32))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    nonce = uuid.uuid4().hex
    machine_id = load_machine_id()
    auth_url = "%s%s?%s" % (region["web"], DEVICE_LOGIN_PATH, urllib.parse.urlencode({
        "challenge": challenge,
        "challenge_method": "S256",
        "machine_id": machine_id,
        "nonce": nonce,
    }))
    poll_url = "%s%s?%s" % (region["open_api"], DEVICE_POLL_PATH, urllib.parse.urlencode({
        "nonce": nonce,
        "verifier": verifier,
        "challenge_method": "S256",
    }))
    return auth_url, poll_url


def poll_once(poll_url):
    headers = {"Cosy-Version": "1.0.1", "Cosy-ClientType": "5", "User-Agent": "qoder-local-proxy"}
    response = request("GET", poll_url, headers=headers)
    if response.status_code in (202, 404):
        return None
    payload = json_of(response)
    if response.status_code >= 400:
        message = first_text(payload.get("message"), payload.get("errorMessage"), payload.get("msg"))
        raise RuntimeError("授权轮询失败（HTTP %s）%s" % (response.status_code, message))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    token = first_text(data.get("token"), data.get("access_token"), data.get("device_token"))
    if not token:
        code = payload.get("code")
        if code not in (None, 0, "0"):
            raise RuntimeError("授权失败（code=%s）：%s" % (code, first_text(payload.get("msg"), payload.get("message"))))
        return None
    return {
        "access_token": token,
        "refresh_token": first_text(data.get("refresh_token"), data.get("refreshToken")),
        "user_id": first_text(data.get("user_id"), data.get("userId")),
        "expires_at": data.get("expires_at") or data.get("expiresAt"),
    }


def verify(region, access_token):
    log("🔎 校验 token ...")
    headers = {
        "authorization": "Bearer %s" % access_token,
        "cosy-clienttype": "10",
        "accept": "application/json",
        "accept-language": "zh-CN",
        "user-agent": "Qoder",
    }
    try:
        response = request("GET", region["open_api"] + CAMPAIGNS_PATH + "?forceRefresh=true", headers=headers)
        payload = json_of(response)
        if response.status_code == 200 and payload.get("campaigns") is not None:
            log("✅ token 可用（已读到活动列表）")
            return True
        if response.status_code in (401, 403):
            log("⚠️ token 未被接受，请确认账号地区是否为「%s」" % region["label"])
            return False
        log("⚠️ 校验返回 HTTP %s" % response.status_code)
    except Exception as error:
        log("⚠️ 校验异常：%s" % error)
    return False


def main():
    args = sys.argv[1:]
    region_key = "cn"
    if "--region" in args:
        try:
            region_key = args[args.index("--region") + 1].strip().lower()
        except Exception:
            region_key = "cn"
    if region_key not in REGIONS:
        print("❌ --region 只支持 cn / global")
        return 1
    region = REGIONS[region_key]
    do_verify = "--no-verify" not in args
    note = ""
    if "--note" in args:
        try:
            note = args[args.index("--note") + 1]
        except Exception:
            note = ""

    print("╔══════════════════════════════════════════╗")
    print("║ 🧭 Qoder 设备授权登录（%s）      ║" % region["label"])
    print("╚══════════════════════════════════════════╝")

    auth_url, poll_url = start_device_login(region)
    print("👉 请在浏览器打开下面的地址，用要登录的账号确认授权：")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    print("⏳ 等待授权（最长 %d 秒）..." % POLL_TIMEOUT)

    deadline = time.time() + POLL_TIMEOUT
    credentials = None
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            credentials = poll_once(poll_url)
        except Exception as error:
            log("⚠️ %s" % error)
            continue
        if credentials:
            break
    if not credentials:
        print("❌ 授权超时或未完成，请重新运行")
        return 1

    log("✅ 授权成功  user_id=%s" % (credentials["user_id"] or "?"))
    if do_verify:
        verify(region, credentials["access_token"])

    env_line = credentials["access_token"]
    if credentials["refresh_token"]:
        env_line += "|" + credentials["refresh_token"]
    if note:
        env_line = note + "|" + env_line
    print("\n" + "-" * 50)
    target = "QODER_GLOBAL_TOKENS" if region_key == "global" else "QODER_TOKENS"
    print("✅ 将下面这行追加到 %s" % target)
    print("-" * 50)
    print(env_line)
    print("-" * 50)
    if region_key == "global":
        print("ℹ️ 国际版签到需要设备风控身份：可设置 QODER_MACHINE_TOKEN / QODER_MACHINE_CODE /")
        print("   QODER_MACHINE_TYPE，或用 QODER_UMID_PATH 指向 runtime-info 组件。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)
    except Exception as error:
        print("❌ %s" % error)
        sys.exit(1)
