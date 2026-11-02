#!/usr/bin/env python3
# -*- coding: utf-8 -*-
try:
    from utils import ql_env  # noqa: F401
except Exception:
    pass
"""
@source: https://gh-proxy.org/github.com/L0NE-6/Qoder-Daily/raw/refs/heads/main/qoder_daily.py

cron: 10 8 * * *
new Env('Qoder每日签到')

🧭 Qoder 每日签到（中国版 / 国际版）- 青龙脚本
------------------------------------------------------------

📌 功能
   Qoder 每日签到（活动领取制，中国版 / 国际版）：
   1. GET  /sash/api/v1/me/campaigns  拉活动列表（官方客户端不发送 forceRefresh）
   2. 找 actionType=CLAIM_BENEFIT 且 claimStatus=CLAIMABLE 的活动
   3. POST /sash/api/v1/me/campaigns/{campaignId}/claim  领取 credits
   4. 已领取（CLAIMED / replayed / 409 ALREADY_CLAIMED）识别为今日已领，不算失败
    5. Pro 升级包：从 campaigns 中发现，GET /reward 只读核实面值后再 claim

   中国版和国际版（每日 100 Credits）的活动只下发给带对应官方设备身份的请求
   （Cosy-MachineToken / Cosy-MachineCode / Cosy-MachineType，由本机 UMID
   组件生成）。中国版使用 Qoder CN 的 runtime-info / qoderclicn 与 UMID 环境 0，
   国际版使用 Qoder 的 runtime-info / qodercli 与 UMID 环境 3。脚本会按地区
   查找组件；Linux 容器里找不到时会从对应官方 npm 包提取（sha512 校验，可用
   QODER_UMID_NO_INSTALL=1 关闭）。
   中国版活动列表若在完整设备头下返回 HTTP 200 空表，会按上游实测形态改用
   最小鉴权四件套复取一次；国际版不做该降级。
   官方活动窗口每天 10:00（UTC+8）开启，没到点或未下发时按中性文案说明。

🔑 环境变量
   QODER_TOKENS        【中国版】多账号用换行或 & 分隔，每条支持三种写法：
       access_token
       access_token|refresh_token
       备注|access_token|refresh_token
   QODER_GLOBAL_TOKENS 【国际版】同上，第 4 段可选填 uid（备注|access|refresh|uid）
   # 中国版 / 国际版风控身份分层（任选其一）：
   #   1) QODER_MACHINE_TOKEN / QODER_MACHINE_CODE / QODER_MACHINE_TYPE 三件套；
   #   2) QODERCN_RUNTIME_INFO（中国版）或 QODER_RUNTIME_INFO（国际版）；
   #   3) QODER_UMID_PATH 指向通用 runtime-info 组件；
   #   4) 本机对应地区客户端 / CLI（找不到时自动从官方包提取，QODER_UMID_NO_INSTALL=1 可关闭）。
       access_token 形如 dt-xxxx；refresh_token 形如 drt-xxxx（可选，配了可自动续期）

   PUSHPLUS_TOKEN    微信推送通道（可选）
   BARK_URL        iOS 推送地址（可选）
   WECOM_WEBHOOK   企微群机器人地址或 key（可选）
   DINGTALK_WEBHOOK  钉钉机器人 webhook（可选）
   DINGTALK_SECRET   钉钉加签密钥（可选）
QODER_WINDOW_RETRY  【可选】10:00-11:00 CST 内暂未下发时按 10 分钟重试（默认 1）

⌨️ 命令
   python qoder_daily.py                 正常签到
   python qoder_daily.py --only 2        只跑第 2 个账号
   python qoder_daily.py --refresh-only  只刷新 token（结果存入 qoder_tokens.json）
   python qoder_daily.py --no-notify     不推送

📄 依赖：requests
"""
import base64
import hashlib
import hmac
import io
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests

import urllib3
urllib3.disable_warnings()

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGIONS = {
    "cn": {"base": "https://openapi.qoder.com.cn", "label": "中国版"},
    "global": {"base": "https://openapi.qoder.sh", "label": "国际版"},
}
CAMPAIGNS_PATH = "/sash/api/v1/me/campaigns"
CAMPAIGN_REWARD_PATH = "/sash/api/v1/me/campaigns/%s/reward"
QUOTA_USAGE_PATH = "/api/v2/quota/usage"
DEVICE_REFRESH_PATH = "/api/v1/deviceToken/refresh"
JOB_REFRESH_PATH = "/api/v1/jobToken/refresh"
SASH_CLIENT_TYPE = "10"
SASH_USER_AGENT = "Qoder"
STORE_FILE = os.path.join(SCRIPT_DIR, "qoder_tokens.json")
CN_TZ = timezone(timedelta(hours=8))
CLAIM_FAILURE_TEXT = {
    "REDEMPTION_CODE_OUT_OF_STOCK": "今日名额已发完，等待下一轮",
    "SAME_PERSON_ALREADY_CLAIMED": "同一设备身份下的其他账号已领取",
    "CAMPAIGN_NOT_ACTIVE": "活动尚未开放或已结束",
    "ACHIEVEMENT_NOT_COMPLETED": "活动条件尚未完成",
    "RISK_BLOCKED": "设备风控未通过",
    "RISK_DEPENDENCY_UNAVAILABLE": "设备风控依赖暂不可用",
}
QUOTA_112_COOLDOWN = 30 * 60
QUOTA_110_MAX_COOLDOWN = 6 * 60 * 60
QUOTA_110_MIN_COOLDOWN = 60

ONLY = None
REFRESH_ONLY = False
NO_NOTIFY = False


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


def mask(text, keep=6):
    text = str(text or "")
    if len(text) <= keep + 4:
        return text
    return text[:keep] + "****" + text[-4:]


def split_accounts(raw):
    out = []
    for chunk in (raw or "").replace("&", "\n").splitlines():
        chunk = chunk.strip().strip('"\'')
        if chunk and not chunk.startswith("#"):
            out.append(chunk)
    return out


def request(method, url, headers=None, body=None, timeout=20, retries=3):
    last = None
    for attempt in range(retries):
        try:
            session = requests.Session()
            session.trust_env = False
            return session.request(
                method, url,
                headers=headers or {},
                json=body if body is not None else None,
                timeout=timeout, verify=False,
            )
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
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def token_fp(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


# ---------- token 本地存储（续期会轮换 token，必须落盘才能二次运行） ----------

def load_store():
    try:
        with open(STORE_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_store(store):
    try:
        with open(STORE_FILE, "w", encoding="utf-8") as handle:
            json.dump(store, handle, ensure_ascii=False, indent=2)
    except Exception as error:
        log("⚠️ token 存储写入失败: %s" % error)


def _remember_store_keys(account):
    """Keep fingerprints of the configured credentials before restore/rotation."""
    keys = account.setdefault("_store_keys", [])
    for token in (account.get("refresh"), account.get("access")):
        if token:
            key = token_fp(token)
            if key not in keys:
                keys.append(key)
    return keys


def apply_store(account):
    store = load_store()
    keys = _remember_store_keys(account)
    for key in keys:
        saved = store.get(key)
        if not isinstance(saved, dict):
            continue
        if saved.get("access"):
            account["access"] = saved["access"]
            account["refresh"] = saved.get("refresh", account.get("refresh", ""))
            return True
    return False


def persist(account):
    store = load_store()
    value = {
        "access": account["access"],
        "refresh": account.get("refresh", ""),
        "note": account.get("note", ""),
        "at": int(time.time()),
    }
    # The next process still starts with the original environment/Secret values.
    # Update those aliases as well as the current fingerprints, without storing
    # the original credential strings in the payload.
    for key in _remember_store_keys(account):
        store[key] = value
    save_store(store)


# ---------- 上游协议 ----------

# ---------- 设备风控身份（中国版 / 国际版签到依赖） ----------

UMID_DIR = os.path.join(SCRIPT_DIR, "cache/qoder_umid")
MACHINE_ID_FILE = os.path.join(SCRIPT_DIR, "qoder_machine_id")
RISK_TTL = 50 * 60
DEFAULT_CLIENT_VERSION = "1.1.69"
NPM_PACKAGES = ("https://registry.npmmirror.com", "https://registry.npmjs.org")
NPM_AUTHORITY = "https://registry.npmjs.org"
NPM_PACKAGE_PATHS = {
    "cn": "@qodercn-ai%2fqoderclicn",
    "global": "@qoder-ai%2fqodercli",
}
UMID_RUNTIME_ENV = {"cn": 0, "global": 3}
UMID_OVERRIDE_ENV = {"cn": "QODERCN_RUNTIME_INFO", "global": "QODER_RUNTIME_INFO"}
RISK_CACHE = {}


def machine_os():
    arch = platform.machine().lower()
    arch = "x86_64" if arch in ("amd64", "x86_64") else (
        "aarch64" if arch in ("arm64", "aarch64") else "unknown")
    if sys.platform.startswith("win"):
        system = "win32"
    elif sys.platform == "darwin":
        system = "darwin"
    else:
        system = "linux"
    return "%s_%s" % (arch, system)


def machine_hostname():
    raw = (os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "").strip()
    if not raw:
        return ""
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    printable = all(0x21 <= ord(ch) <= 0x7e or ch == " " for ch in raw)
    if printable:
        text = raw
    else:
        cleaned = "".join(ch if 0x21 <= ord(ch) <= 0x7e else "-" for ch in raw)
        cleaned = "-".join(part for part in cleaned.split("-") if part)
        text = ("%s-%s" % (cleaned, digest)) if cleaned else ("unknown-%s" % digest)
    if len(text) > 96:
        text = text[:87].rstrip("- ") + "-" + digest
    return text


def machine_id(account):
    device = first_text(account.get("device_id"))
    if device:
        return device
    try:
        with open(MACHINE_ID_FILE, encoding="utf-8") as handle:
            saved = handle.read().strip()
        if saved:
            return saved
    except Exception:
        pass
    value = uuid.uuid4().hex
    try:
        with open(MACHINE_ID_FILE, "w", encoding="utf-8") as handle:
            handle.write(value)
    except Exception:
        pass
    return value


def region_key(region):
    return "global" if str(region or "").lower() in ("global", "intl", "international") else "cn"


def region_names(region):
    if region_key(region) == "global":
        return ("Qoder",)
    return ("Qoder CN", "QoderCN")


def resource_dirs(region, names):
    dirs = []
    for name in names:
        if sys.platform.startswith("win"):
            roots = []
            local = os.environ.get("LOCALAPPDATA")
            if local:
                roots.append(os.path.join(local, "Programs", name))
            for variable in ("ProgramFiles", "ProgramFiles(x86)"):
                base = os.environ.get(variable)
                if base:
                    roots.append(os.path.join(base, name))
            for install in roots:
                versions = os.path.join(install, ".qoder-versions")
                try:
                    entries = sorted(os.listdir(versions), reverse=True)
                except Exception:
                    entries = []
                for entry in entries[:8]:
                    dirs.append(os.path.join(versions, entry, "resources"))
                dirs.append(os.path.join(install, "resources"))
        elif sys.platform == "darwin":
            dirs.append("/Applications/%s.app/Contents/Resources" % name)
            dirs.append(os.path.join(os.path.expanduser("~"), "Applications",
                                     "%s.app" % name, "Contents", "Resources"))
        else:
            slug = name.lower().replace(" ", "-")
            dirs.append("/opt/%s/resources" % name)
            dirs.append("/opt/%s/resources" % slug)
            dirs.append("/usr/lib/%s/resources" % slug)
            dirs.append("/snap/%s/current/resources" % slug)
    if not sys.platform.startswith("win") and sys.platform != "darwin" \
            and region_key(region) == "cn":
        dirs.extend(("/opt/Qoder-CN/resources", "/opt/QoderCN/resources"))
    return dirs


def client_version(region):
    for resources in resource_dirs(region, region_names(region)):
        try:
            with open(os.path.join(resources, "build-manifest.json"), encoding="utf-8") as handle:
                value = json.load(handle).get("productVersion")
        except Exception:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return DEFAULT_CLIENT_VERSION


def umid_directory(region):
    return os.path.join(UMID_DIR, region_key(region))


def cli_runtime_cache_dirs(region):
    key = region_key(region)
    prefix = "QODERCN_" if key == "cn" else "QODER_"
    default_name = ".qoder-cn" if key == "cn" else ".qoder"
    explicit = _env(prefix + "CONFIG_DIR")
    if explicit:
        return [explicit]
    home = _env(prefix + "CLI_HOME") or _env("GEMINI_CLI_HOME") or os.path.expanduser("~")
    config_name = _env(prefix + "CONFIG_DIR_NAME") or default_name
    return [os.path.join(home, config_name)]


def find_umid_component(region):
    key = region_key(region)
    exe_name = "runtime-info.exe" if sys.platform.startswith("win") else "runtime-info"
    runtime_env = UMID_RUNTIME_ENV[key]
    custom = _env(UMID_OVERRIDE_ENV[key]) or _env("QODER_UMID_PATH")
    if custom and os.path.isfile(custom):
        return custom, runtime_env, "env"
    for resources in resource_dirs(key, region_names(key)):
        path = os.path.join(resources, "umid", exe_name)
        if os.path.isfile(path):
            return path, runtime_env, "app"
    for config in cli_runtime_cache_dirs(key):
        base = os.path.join(config, ".bin")
        try:
            entries = sorted(os.listdir(base), reverse=True)
        except Exception:
            continue
        for entry in entries:
            candidate = os.path.join(base, entry)
            if os.path.isdir(candidate) and entry.startswith("umid-"):
                path = os.path.join(candidate, exe_name)
            elif not os.path.isdir(candidate) and entry.startswith("runtime-info"):
                path = candidate
            else:
                continue
            if os.path.isfile(path):
                return path, runtime_env, "cli"
    data = os.path.join(umid_directory(key), exe_name)
    if os.path.isfile(data):
        return data, runtime_env, "data"
    return None


def run_umid_component(component, uid):
    path, env, _source = component
    args = [path, str(env)]
    payload = None
    if sys.platform.startswith("win") or sys.platform == "darwin":
        args.append("--account-stdin")
        payload = (json.dumps({"account": uid or ""}) + "\n").encode("utf-8")
    proc = subprocess.run(args, input=payload, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, timeout=25)
    output = proc.stdout or b""
    if len(output) > 1024 * 1024:
        raise RuntimeError("组件输出过大")
    line = output.decode("utf-8", "replace").splitlines()[0].strip() if output else ""
    data = json.loads(line) if line else {}
    values = {}
    for key in ("machineToken", "machineCode", "machineType"):
        value = data.get(key) if isinstance(data, dict) else None
        if not isinstance(value, str) or not value.strip() or len(value) > 4096:
            raise RuntimeError("组件输出缺少 %s" % key)
        values[key] = value.strip()
    return values


def http_get_bytes(url, timeout=60):
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, timeout=timeout, verify=False)
    response.raise_for_status()
    return response.content


def npm_meta(registry, region):
    package_path = NPM_PACKAGE_PATHS[region_key(region)]
    body = http_get_bytes("%s/%s/latest" % (registry, package_path), timeout=20)
    payload = json.loads(body.decode("utf-8"))
    dist = payload.get("dist") if isinstance(payload.get("dist"), dict) else {}
    tarball = first_text(dist.get("tarball"))
    integrity = first_text(dist.get("integrity"))
    if not tarball or not integrity:
        raise RuntimeError("元数据缺少 tarball / integrity")
    return {"version": first_text(payload.get("version")), "tarball": tarball,
            "integrity": integrity}


def extract_elf(bundle, machine):
    mark = '"f0VMRgIB'
    position = 0
    while True:
        hit = bundle.find(mark, position)
        if hit < 0:
            return None
        end = bundle.find('"', hit + 1)
        if end < 0:
            return None
        encoded = bundle[hit + 1:end]
        try:
            head = base64.b64decode(encoded[:min(4096, len(encoded))])
        except Exception:
            head = b""
        if len(head) >= 20 and int.from_bytes(head[18:20], "little") == machine:
            try:
                return base64.b64decode(encoded)
            except Exception:
                return None
        position = end + 1


def install_umid_component(region):
    key = region_key(region)
    arch = machine_os().rsplit("_", 1)[0]
    machine = {"x86_64": 62, "aarch64": 183}.get(arch)
    if not machine:
        raise RuntimeError("当前 CPU 架构不受支持")
    try:
        authority = npm_meta(NPM_AUTHORITY, key)
    except Exception:
        authority = None
    errors = []
    for registry in NPM_PACKAGES:
        try:
            meta = npm_meta(registry, key)
        except Exception as error:
            errors.append("%s：%s" % (registry, error))
            continue
        if registry != NPM_AUTHORITY and authority:
            if authority["version"] and meta["version"] and authority["version"] != meta["version"]:
                errors.append("%s：版本与官方源不一致" % registry)
                continue
            if authority["integrity"] != meta["integrity"]:
                errors.append("%s：integrity 与官方源不一致" % registry)
                continue
        try:
            body = http_get_bytes(meta["tarball"], timeout=180)
        except Exception as error:
            errors.append("%s：下载失败 %s" % (registry, error))
            continue
        if meta["integrity"].startswith("sha512-"):
            actual = base64.b64encode(hashlib.sha512(body).digest()).decode()
            if actual != meta["integrity"][7:]:
                errors.append("%s：下载内容与 integrity 不一致" % registry)
                continue
        try:
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
                bundle = ""
                for member in ("package/bundle/qoder-worker-runtime.mjs",
                               "package/bundle/qodercli.js"):
                    try:
                        handle = archive.extractfile(member)
                    except KeyError:
                        handle = None
                    if handle:
                        bundle = handle.read().decode("utf-8", "replace")
                        if bundle:
                            break
        except Exception as error:
            errors.append("%s：解包失败 %s" % (registry, error))
            continue
        elf = extract_elf(bundle, machine)
        if not elf:
            errors.append("%s：包里没有本机架构的 UMID 程序" % registry)
            continue
        target_dir = umid_directory(key)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, "runtime-info")
        with open(path, "wb") as output:
            output.write(elf)
        try:
            os.chmod(path, 0o755)
        except Exception:
            pass
        package_name = "qoderclicn" if key == "cn" else "qodercli"
        log("   ✅ 已从官方 %s %s 提取 UMID 组件" % (
            package_name, meta["version"] or "?"))
        return path
    raise RuntimeError("；".join(errors) if errors else "没有可用来源")


def risk_identity(region, uid):
    region = region_key(region)
    key = "%s:%s" % (region, uid)
    cached = RISK_CACHE.get(key)
    if cached and time.time() - cached[0] < RISK_TTL:
        return cached[1], None
    env_values = [_env(name) for name in
                  ("QODER_MACHINE_TOKEN", "QODER_MACHINE_CODE", "QODER_MACHINE_TYPE")]
    if any(env_values):
        if all(env_values):
            values = {"machineToken": env_values[0], "machineCode": env_values[1],
                      "machineType": env_values[2]}
            RISK_CACHE[key] = (time.time(), values)
            return values, None
        return None, ("设备风控环境变量不完整（需要 QODER_MACHINE_TOKEN / "
                      "QODER_MACHINE_CODE / QODER_MACHINE_TYPE 三件套）")
    component = find_umid_component(region)
    if component is None and not _env("QODER_UMID_NO_INSTALL"):
        try:
            package_name = "qoderclicn" if region == "cn" else "qodercli"
            log("   📦 未找到本机 UMID 组件，尝试从官方 %s 包提取（sha512 校验）" %
                package_name)
            install_umid_component(region)
        except Exception as error:
            return None, "设备风控组件安装失败：%s" % error
        component = find_umid_component(region)
    if component is None:
        label = "Qoder CN / qoderclicn" if region == "cn" else "Qoder / qodercli"
        return None, "本机没有 %s 的 UMID 组件" % label
    try:
        values = run_umid_component(component, uid)
    except Exception as error:
        return None, "设备风控身份生成失败：%s" % error
    RISK_CACHE[key] = (time.time(), values)
    return values, None


def risky_sash_headers(account, uid=""):
    headers = sash_headers(account["access"])
    region = account.get("region", "cn")
    headers["Cosy-Version"] = client_version(region)
    headers["Cosy-MachineOS"] = machine_os()
    headers["Cosy-MachineId"] = machine_id(account)
    hostname = machine_hostname()
    if hostname:
        headers["Cosy-MachineHostname"] = hostname
    risk, note = risk_identity(region, uid)
    if risk:
        headers["Cosy-MachineToken"] = risk["machineToken"]
        headers["Cosy-MachineCode"] = risk["machineCode"]
        headers["Cosy-MachineType"] = risk["machineType"]
    return headers, note

def sash_headers(token):
    return {
        "authorization": "Bearer %s" % token,
        "cosy-clienttype": SASH_CLIENT_TYPE,
        "accept": "application/json",
        "accept-language": "zh-CN",
        "user-agent": SASH_USER_AGENT,
    }


def minimal_sash_headers(token):
    """中国版空表复取使用上游实测的最小鉴权四件套。"""
    return {
        "authorization": "Bearer %s" % token,
        "cosy-clienttype": SASH_CLIENT_TYPE,
        "user-agent": SASH_USER_AGENT,
        "content-type": "application/json",
    }


def refresh_account(account):
    refresh = account.get("refresh", "")
    if not refresh:
        raise RuntimeError("账号没有 refresh_token，无法续期")
    _remember_store_keys(account)
    path = JOB_REFRESH_PATH if refresh.startswith("jrt-") else DEVICE_REFRESH_PATH
    response = request("POST", account["base"] + path,
                       headers={"User-Agent": "qoder-local-proxy"},
                       body={"refresh_token": refresh})
    if response.status_code in (401, 403):
        raise RuntimeError("刷新令牌已失效或与地区不符，请重新登录")
    payload = json_of(response)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    token = first_text(data.get("device_token"), data.get("deviceToken"),
                       data.get("token"), data.get("access_token"))
    if not token:
        raise RuntimeError("续期响应缺少 access token（HTTP %s）" % response.status_code)
    new_refresh = first_text(data.get("refresh_token"), data.get("refreshToken")) or refresh
    account["access"] = token
    account["refresh"] = new_refresh
    persist(account)
    log("   🔄 token 已续期并保存")
    return True


def quota_cooldown(response, now=None):
    """额度类 403 的 (病因, 冷却秒数)；不是额度问题返回 ("", 0)。

    上游对「额度耗尽」和「每日计费次数上限」也回 403，与凭证被拒同码不同因：
    112 / pricingUrl -> 30 分钟；110 / Billing daily count exceeded -> 到本地
    零点，封顶 6 小时。响应体可能被日志转义，先去掉反斜杠再匹配。
    """
    payload = json_of(response)
    text = json.dumps(payload, ensure_ascii=False) if isinstance(payload, (dict, list)) else ""
    text = (text + " " + str(getattr(response, "text", "") or "")).replace("\\", "")
    if "pricingUrl" in text or re.search(r'"code"\s*:\s*"?112\b', text):
        return "exhausted", QUOTA_112_COOLDOWN
    if "Billing daily count exceeded" in text or re.search(r'"code"\s*:\s*"?110\b', text):
        current = time.time() if now is None else float(now)
        local = datetime.fromtimestamp(current)
        midnight = datetime(local.year, local.month, local.day) + timedelta(days=1)
        seconds = int((midnight - local).total_seconds())
        return "daily", max(QUOTA_110_MIN_COOLDOWN,
                            min(QUOTA_110_MAX_COOLDOWN, seconds))
    return "", 0


def quota_cooldown_message(kind, seconds):
    if kind == "exhausted":
        return "额度已耗尽（112 / pricingUrl），账号冷却 30 分钟；请充值或更换账号"
    until = time.strftime("%m-%d %H:%M", time.localtime(time.time() + seconds))
    return "每日计费次数已达上限（110），账号冷却至 %s（最长 6 小时）；请稍后或更换账号" % until


def auth_dead_response(response):
    """HTTP 401/403 或已知业务码表示会话已失效，需要立即强制续期。"""
    if response.status_code in (401, 403):
        return quota_cooldown(response)[0] == ""
    payload = json_of(response)
    if not isinstance(payload, dict):
        return False
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    codes = (
        first_text(payload.get("code"), payload.get("Code")),
        first_text(data.get("code"), data.get("Code")),
    )
    return any(code in ("105", "10019901001") for code in codes)


def campaign_response_is_empty(response):
    """仅在成功且明确为空/未展示活动列表时返回 True。"""
    if response.status_code != 200 or auth_dead_response(response):
        return False
    payload = json_of(response)
    if not isinstance(payload, dict):
        return False
    bodies = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        bodies.append(data)
    for body in bodies:
        campaigns = body.get("campaigns")
        if isinstance(campaigns, list):
            return not campaigns
        if campaigns is None and body.get("showCampaign") is False:
            return True
    return False


def _fetch_campaigns_once(account, headers):
    response = request("GET", account["base"] + CAMPAIGNS_PATH,
                       headers=headers)
    if (region_key(account.get("region", "cn")) == "cn"
            and campaign_response_is_empty(response)):
        original = response
        response = request(
            "GET", account["base"] + CAMPAIGNS_PATH,
            headers=minimal_sash_headers(account["access"]),
            retries=1,
        )
        if campaign_response_is_empty(response):
            return original
    return response


def fetch_campaigns(account):
    headers, risk_note = risky_sash_headers(account, account.get("uid", ""))
    response = _fetch_campaigns_once(account, headers)
    if auth_dead_response(response) and account.get("refresh"):
        refresh_account(account)
        headers, risk_note = risky_sash_headers(account, account.get("uid", ""))
        response = _fetch_campaigns_once(account, headers)
    return response, risk_note


def campaign_rows_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    direct = payload.get("campaigns")
    if isinstance(direct, list):
        return direct
    data = payload.get("data")
    rows = data.get("campaigns") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def campaign_id_of(row):
    return first_text(row.get("campaignId"), row.get("id"))


def amount_of(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def campaign_benefit(row):
    benefit = row.get("benefit") if isinstance(row, dict) else None
    if not isinstance(benefit, dict):
        return "", 0.0
    return first_text(benefit.get("kind")).upper(), amount_of(benefit.get("amount"))


def campaign_looks_like_pro_upgrade(row):
    for key in ("campaignKey", "actionType", "title", "name", "campaignName"):
        value = str(row.get(key) or "").lower()
        if "pro" in value or "upgrade" in value:
            return True
    kind, amount = campaign_benefit(row)
    return kind == "CREDITS" and amount >= 1000


def fetch_campaign_reward(account, campaign_id):
    """只读读取活动真实面值；官方活动页使用浏览器头，不带 Cosy-Machine*。"""
    headers = sash_headers(account["access"])
    headers["origin"] = account["base"]
    response = request("GET", account["base"] + CAMPAIGN_REWARD_PATH % campaign_id,
                       headers=headers, retries=1)
    if response.status_code != 200:
        return None
    payload = json_of(response)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    benefit = data.get("benefit") if isinstance(data, dict) else None
    kind = first_text(data.get("kind") if isinstance(data, dict) else "",
                      benefit.get("kind") if isinstance(benefit, dict) else "").upper()
    amount = amount_of(benefit.get("amount") if isinstance(benefit, dict) else
                       (data.get("amount") if isinstance(data, dict) else None))
    return {"kind": kind, "amount": amount}


def quota_total_remaining(account):
    """读取账户总剩余额度，用于 claim 前后核对真实增量。"""
    headers, _note = risky_sash_headers(account, account.get("uid", ""))
    response = request("GET", account["base"] + QUOTA_USAGE_PATH,
                       headers=headers, retries=1)
    if response.status_code != 200:
        return None
    payload = json_of(response)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None
    total = 0.0
    seen = False
    for key in ("userQuota", "addOnQuota"):
        pool = data.get(key)
        if isinstance(pool, dict) and pool.get("remaining") is not None:
            total += amount_of(pool.get("remaining"))
            seen = True
    for pool in data.get("dedicatedResourcePackages") or []:
        if isinstance(pool, dict) and pool.get("remaining") is not None:
            total += amount_of(pool.get("remaining"))
            seen = True
    org = data.get("orgResourcePackage")
    if isinstance(org, dict) and org.get("remaining") is not None:
        total += amount_of(org.get("remaining"))
        seen = True
    return total if seen else None


def claim_response_verdict(response):
    """把 campaigns claim 响应归一为 claimed / already / blocked / error。"""
    payload = json_of(response)
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(body, dict):
        body = {}
    status = first_text(body.get("status"), payload.get("status")).upper()
    failure = first_text(body.get("failureCode"), payload.get("failureCode"),
                         body.get("errorCode"), payload.get("errorCode")).upper()
    result = first_text(body.get("result"), payload.get("result")).upper()
    message = first_text(body.get("message"), body.get("msg"),
                         payload.get("message"), payload.get("msg"))
    replayed = body.get("replayed") is True or payload.get("replayed") is True
    if "ALREADY" in result or "REPLAYED" in result:
        return "already", 0.0, "活动已领取"
    if response.status_code == 409:
        if "ALREADY" in failure or "REPLAYED" in failure or replayed:
            return "already", 0.0, "活动已领取"
        return "error", 0.0, message or ("HTTP 409 %s" % (failure or "领取冲突"))
    if status in ("CLAIMED", "GRANTED", "SUCCESS"):
        if replayed:
            return "already", 0.0, "活动已领取"
        redemption = first_text(body.get("redemptionCode"))
        amount = amount_of((body.get("benefit") or {}).get("amount")
                           if isinstance(body.get("benefit"), dict) else None)
        if redemption:
            return "claimed", 0.0, "已领取兑换券：" + redemption
        return "claimed", amount, message or "领取成功"
    if status == "BLOCKED" or failure == "SAME_PERSON_ALREADY_CLAIMED":
        return "blocked", 0.0, CLAIM_FAILURE_TEXT.get(failure) or message or "领取被阻塞"
    if failure in CLAIM_FAILURE_TEXT:
        return "error", 0.0, CLAIM_FAILURE_TEXT[failure]
    if 200 <= response.status_code < 300:
        return "error", 0.0, message or "上游未确认成功"
    return "error", 0.0, message or ("HTTP %s" % response.status_code)


def daily_window_retry_enabled():
    raw = _env("QODER_WINDOW_RETRY")
    if not raw:
        return True
    return raw.lower() not in ("0", "false", "no", "off")


def daily_window_active():
    now = datetime.now(CN_TZ)
    # 官方窗口 10:00 开启；上游可能延迟到 11:00 前才下发，重试窗口同步放宽到 1 小时。
    return now.hour == 10


def fetch_campaign_rows(account):
    response, risk_note = fetch_campaigns(account)
    quota_kind, quota_seconds = quota_cooldown(response)
    if quota_kind:
        return [], response, risk_note, quota_cooldown_message(quota_kind, quota_seconds)
    if response.status_code in (401, 403):
        return [], response, risk_note, "签到活动查询失败（HTTP %s），请确认凭证有效且地区选择正确" % response.status_code
    if auth_dead_response(response):
        return [], response, risk_note, (
            "签到活动查询失败（业务码 105 / 10019901001，续期后仍无效），"
            "请重新登录或稍后重试"
        )
    if response.status_code == 429:
        return [], response, risk_note, "签到活动查询失败（HTTP 429），请稍后重试"
    if response.status_code != 200:
        return [], response, risk_note, "活动列表返回 HTTP %s" % response.status_code
    return campaign_rows_from_payload(json_of(response)), response, risk_note, ""


def pick_daily_campaign(rows):
    target = None
    claimed = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        action_type = first_text(row.get("actionType")).upper()
        if action_type not in ("", "CLAIM_BENEFIT"):
            continue
        if campaign_looks_like_pro_upgrade(row):
            continue
        status = row.get("claimStatus")
        if status == "CLAIMABLE" and target is None:
            target = row
        elif status == "CLAIMED":
            claimed = True
    return target, claimed


def claim_campaign(account, campaign_id):
    headers, _note = risky_sash_headers(account, account.get("uid", ""))
    headers["content-type"] = "application/json"
    headers["origin"] = account["base"]
    return request("POST", "%s%s/%s/claim" % (account["base"], CAMPAIGNS_PATH, campaign_id),
                   headers=headers, body={})


def do_checkin(account):
    rows, response, risk_note, error = fetch_campaign_rows(account)
    if error:
        return False, error
    target, claimed = pick_daily_campaign(rows)

    if (target is None and not claimed and daily_window_retry_enabled()
            and daily_window_active()):
        try:
            max_attempts = min(6, max(1, int(_env("QODER_WINDOW_RETRY_MAX") or "6")))
        except ValueError:
            max_attempts = 6
        try:
            gap = max(1, int(_env("QODER_WINDOW_RETRY_GAP") or "600"))
        except ValueError:
            gap = 600
        for _attempt in range(max_attempts):
            if not daily_window_active():
                break
            log("   ⏳ 10:00 开窗延迟，%d 秒后重试活动列表" % gap)
            time.sleep(gap)
            rows, response, risk_note, error = fetch_campaign_rows(account)
            if error:
                return False, error
            target, claimed = pick_daily_campaign(rows)
            if target is not None or claimed:
                break

    if target is None:
        if claimed:
            return False, "今日已领取"
        if risk_note:
            region_label = "中国版" if region_key(account.get("region")) == "cn" else "国际版"
            return False, (
                "未领取：%s。%s签到需要对应地区的官方设备身份（UMID）；"
                "请安装并登录对应客户端，或配置地区 runtime-info 覆盖变量"
            ) % (risk_note, region_label)
        return False, (
            "上游暂未给该账号下发每日积分活动（官方活动窗口每天 10:00 UTC+8 "
            "开启；若今天已在客户端领过则活动行会消失），稍后再试"
        )

    campaign_id = campaign_id_of(target)
    if not campaign_id:
        return False, "活动数据里没有 campaignId，无法领取"

    claim = claim_campaign(account, campaign_id)
    verdict, amount, verdict_message = claim_response_verdict(claim)
    if verdict == "already":
        return False, "今日已领取"
    if verdict != "claimed":
        return False, "领取失败：%s" % verdict_message

    if amount <= 0:
        _kind, amount = campaign_benefit(target)
    days = None
    payload = json_of(claim)
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    benefit = body.get("benefit") if isinstance(body, dict) and isinstance(body.get("benefit"), dict) else {}
    validity = benefit.get("validity") if isinstance(benefit.get("validity"), dict) else {}
    if validity.get("days") is not None:
        days = validity.get("days")
    if amount > 0:
        text = "获得 %s credits" % int(amount)
    elif verdict_message.startswith("已领取兑换券"):
        text = verdict_message
    else:
        text = "领取已确认，积分回读稍后刷新"
    if days:
        text += "，%s 天有效" % days
    return True, text


def discover_pro_campaign(account, rows):
    """从 campaigns 中找 Pro 升级包；隐藏面值用只读 /reward 核实。"""
    claimed = None
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = first_text(row.get("claimStatus")).upper()
        if status == "CLAIMED" and campaign_looks_like_pro_upgrade(row) and claimed is None:
            claimed = row
        if status == "CLAIMABLE" and campaign_looks_like_pro_upgrade(row):
            candidates.append(row)
    if candidates:
        return candidates[0], claimed, []

    probes = []
    for row in rows:
        if len(probes) >= 5:
            break
        if not isinstance(row, dict) or first_text(row.get("claimStatus")).upper() != "CLAIMABLE":
            continue
        campaign_id = campaign_id_of(row)
        if not campaign_id:
            continue
        reward = fetch_campaign_reward(account, campaign_id)
        if not reward:
            probes.append("%s:面值不可读" % (campaign_id or "?"))
            continue
        kind = str(reward.get("kind") or "").upper()
        amount = amount_of(reward.get("amount"))
        probes.append("%s:%s %.0f" % (campaign_id, kind or "?", amount))
        if kind == "CREDITS" and amount >= 1000:
            return row, claimed, probes
    return None, claimed, probes


def do_pro_upgrade(account):
    """从 campaigns 领取一次性 Pro 升级包，并用额度回读核对增量。"""
    if account.get("region") != "cn":
        return True, False, "国际版暂无 Pro 升级活动"
    rows, response, _risk_note, error = fetch_campaign_rows(account)
    if error:
        return False, False, "Pro 活动查询失败：%s" % error
    target, claimed, probes = discover_pro_campaign(account, rows)
    if target is None:
        if claimed is not None:
            return True, False, "Pro 升级包已领取过（campaigns 状态 CLAIMED）"
        detail = "；已核实 " + "、".join(probes) if probes else ""
        return True, False, "当前未发现 Pro 升级活动（官方已不再常规投放）" + detail
    campaign_id = campaign_id_of(target)
    if not campaign_id:
        return False, False, "Pro 活动缺少 campaignId"

    before = quota_total_remaining(account)
    claim = claim_campaign(account, campaign_id)
    verdict, amount, message = claim_response_verdict(claim)
    if verdict == "already":
        return True, False, "Pro 升级包已领取过，本次不计新增"
    if verdict != "claimed":
        return False, False, "Pro 升级包领取失败：%s" % message

    time.sleep(2)
    after = quota_total_remaining(account)
    delta = None
    if before is not None and after is not None:
        delta = after - before
    if delta is not None and delta > 0:
        return True, True, "Pro 升级包领取成功，额度回读 +%d" % int(delta)
    if delta is not None:
        return True, True, "Pro 领取已受理，额度回读暂未增加（%.0f → %.0f）" % (before, after)
    if amount > 0:
        return True, True, "Pro 升级包领取已受理，活动面值 %.0f（余额回读暂不可用）" % amount
    return True, True, "Pro 升级包领取已受理，积分到账待回读确认"


# ---------- 推送 ----------

def post_json(url, payload, timeout=20):
    session = requests.Session()
    session.trust_env = False
    return session.post(url, json=payload, timeout=timeout, verify=False)


def _env(name):
    return os.environ.get(name, "").strip()


def notify_pushplus(title, content):
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        text = (content[:18000] + "\n...(已截断)") if len(content) > 18000 else content
        answer = post_json("https://www.pushplus.plus/send",
                           {"token": token, "title": title, "content": text, "template": "txt"})
        return str(json_of(answer).get("code")) == "200"
    except Exception:
        return False


def notify_bark(title, content):
    endpoint = _env("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        answer = post_json(endpoint, {"title": title, "body": content, "group": "Qoder"})
        return json_of(answer).get("code") == 200
    except Exception:
        return False


def notify_wecom(title, content):
    hook = _env("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith("http"):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": ("%s\n%s" % (title, content))[:2000]}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_dingtalk(title, content):
    hook = _env("DINGTALK_WEBHOOK")
    if not hook:
        return False
    try:
        secret = _env("DINGTALK_SECRET")
        if secret:
            stamp = str(int(time.time() * 1000))
            digest = hmac.new(secret.encode(), ("%s\n%s" % (stamp, secret)).encode(),
                              hashlib.sha256).digest()
            hook += ("&" if "?" in hook else "?") + "timestamp=%s&sign=%s" % (
                stamp, requests.utils.quote(base64.b64encode(digest)))
        answer = post_json(hook, {"msgtype": "text",
                                  "text": {"content": "%s\n%s" % (title, content)}})
        return json_of(answer).get("errcode") == 0
    except Exception:
        return False


def notify_ql(title, content):
    try:
        from notify import send as panel_send
        panel_send(title, content)
        return True
    except Exception:
        pass
    endpoint = _env("QL_URL").rstrip("/")
    token = _env("QL_TOKEN")
    if not endpoint or not token:
        return False
    try:
        session = requests.Session()
        session.trust_env = False
        answer = session.post(endpoint + "/api/system/notify?token=" + token,
                              json={"title": title, "content": content}, timeout=15, verify=False)
        return str(json_of(answer).get("code")) in ("0", "200")
    except Exception:
        return False


def notify_all(title, content):
    handlers = (notify_pushplus, notify_bark, notify_wecom, notify_dingtalk, notify_ql)
    if not any(handler(title, content) for handler in handlers):
        log("（未配置推送渠道，本次只记录日志）")


# ---------- 账号解析与主流程 ----------

def looks_like_token(value):
    value = (value or "").strip()
    return (value.startswith(("dt-", "drt-", "jt-", "jrt-", "eyJ"))
            or value.count(".") >= 2 or len(value) > 80)


def parse_accounts(raw, region="cn"):
    accounts = []
    for index, line in enumerate(split_accounts(raw), 1):
        parts = [part.strip() for part in line.split("|")]
        fallback = ("账号%d" if region == "cn" else "国际版账号%d") % index
        note = fallback
        uid = ""
        if len(parts) >= 4:
            note, access, refresh, uid = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            note, access, refresh = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            first, second = parts[0], parts[1]
            if looks_like_token(first) and looks_like_token(second):
                access, refresh = first, second          # access|refresh
            elif looks_like_token(second):
                note, access, refresh = first, second, ""  # 备注|access
            else:
                access, refresh = first, second          # access|（空 refresh）
        else:
            access, refresh = parts[0], ""
        if access:
            accounts.append({"note": note or fallback, "access": access, "refresh": refresh,
                             "uid": uid, "region": region, "base": REGIONS[region]["base"]})
    return accounts


def main():
    global ONLY, REFRESH_ONLY, NO_NOTIFY
    args = sys.argv[1:]
    if "--refresh-only" in args:
        REFRESH_ONLY = True
    if "--no-notify" in args:
        NO_NOTIFY = True
    if "--only" in args:
        try:
            ONLY = int(args[args.index("--only") + 1])
        except Exception:
            ONLY = None

    accounts = parse_accounts(os.environ.get("QODER_TOKENS", ""), "cn")
    accounts += parse_accounts(os.environ.get("QODER_GLOBAL_TOKENS", ""), "global")
    if not accounts:
        log("❌ 未配置 QODER_TOKENS / QODER_GLOBAL_TOKENS（多条用换行或 & 分隔；每条: access_token 或 access_token|refresh_token）")
        return

    log("╔════════════════════════════════════╗")
    log("║ 🧭 Qoder 每日签到（中国版 / 国际版）║")
    log("╚════════════════════════════════════╝")
    cn_total = len([item for item in accounts if item["region"] == "cn"])
    log("👥 账号数: %d（中国版 %d / 国际版 %d）" % (len(accounts), cn_total, len(accounts) - cn_total))

    report = []
    for index, account in enumerate(accounts, 1):
        if ONLY and index != ONLY:
            continue
        apply_store(account)
        log("👤 [%d] %s [%s] token=%s" % (index, account["note"],
            REGIONS[account["region"]]["label"], mask(account["access"])))
        if REFRESH_ONLY:
            try:
                refresh_account(account)
                report.append("账号%d %s: ✅ token 续期成功" % (index, account["note"]))
            except Exception as error:
                report.append("账号%d %s: ❌ token 续期失败: %s" % (index, account["note"], error))
            continue
        try:
            success, message = do_checkin(account)
            icon = "✅" if success else "ℹ️"
            log("   %s %s" % (icon, message))
            report.append("账号%d %s: %s %s" % (index, account["note"], icon, message))
            pro_ok, pro_new, pro_message = do_pro_upgrade(account)
            pro_icon = "✅" if pro_ok and pro_new else ("ℹ️" if pro_ok else "❌")
            log("   %s %s" % (pro_icon, pro_message))
            report.append("账号%d %s: %s %s" % (index, account["note"], pro_icon, pro_message))
        except Exception as error:
            log("   ❌ 异常: %s" % error)
            report.append("账号%d %s: ❌ %s" % (index, account["note"], error))
        time.sleep(1.5)

    summary = "🧭 Qoder 签到报告\n" + "\n".join(report) + "\n🕐 " + time.strftime("%Y-%m-%d %H:%M")
    log(summary)
    if not NO_NOTIFY and not REFRESH_ONLY:
        notify_all("🧭 Qoder 签到报告", summary)


if __name__ == "__main__":
    main()