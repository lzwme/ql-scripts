#!/usr/bin/env python3
# -*- coding: utf-8 -*-
try:
    from utils import qlenv  # noqa: F401
except Exception:
    pass
"""
@source: https://gh-proxy.org/github.com/L0NE-6/WorkBuddy-Daily/raw/refs/heads/main/workbuddy_intl_daily.py

cron: 10 8 * * *
new Env('WorkBuddy国际版签到')

WorkBuddy AI（国际版）每日活跃 - 青龙脚本
────────────────────────────────────────────────────────────
国际版的每日奖励不是普通签到，而是一条「活跃任务」链：

  1. 探测   POST /billing/meter/checkin-activity-status
            → data.active（活动是否开放）/ data.today_checked_in（今日是否已领）
  2. 领取   POST /v2/billing/meter/daily-checkin（仅当活动开放且今日未领）
  3. 活跃（三件事，互补）：
     · 上报  POST /v2/report（chat_request_send 事件）→ 点亮成长中心「连登」
       （GET /activity/growth/streak 回读天数；userId 必填，缺失会被静默丢弃）
     · 保活  POST /v2/chat/completions（最小流式对话，维持「账号有调用」）
     · 网页  POST /console/as/conversations/（带 prompt 建会话）
       —— 上游「当日活跃」计数只认这一发（桌面端对话与 /v2/report 都不进该计数）

口径说明：
  - 活动未开放是**正常状态**，不会当成失败；
  - 签到成功 ≠ 活跃成功：分开报告；任一发失败只作附加说明，不把签到判成失败；
  - 一个账号只需要跑一轮，结果推送企业微信 / PushPlus。

环境变量：
  WORKBUDDY_INTL_TOKENS  多账号，换行或 & 分隔，每条：`token` / `备注|token` / `备注|token|uid` / `备注|token|uid|refresh_token`（带 RT 可自动续期）
                         （token 是 www.workbuddy.ai 的登录态，与国内版不通用）
  WORKBUDDY_TOKEN        单账号兜底（国际版登录态）
  WORKBUDDY_INTL_MODELS  可选，保活模型链，逗号分隔；默认官方免费的四个
  QYWX_TOKEN             企业微信机器人（也兼容 WECHAT_WEBHOOK）
  PLUSPLUS_TOKEN         PushPlus
  NO_NOTIFY              设 1 关闭推送

用法：
  python workbuddy_intl_daily.py
  python workbuddy_intl_daily.py --only 1
  python workbuddy_intl_daily.py --no-keepalive   # 只探测、领取与活跃上报，不发保活对话与网页会话
  python workbuddy_intl_daily.py --report-only    # 只发 /v2/report 活跃上报，不领取任务或奖励
"""

import base64
import errno
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager

import requests
import urllib3

urllib3.disable_warnings()

BASE = "https://www.workbuddy.ai"
STATUS_PATH = "/billing/meter/checkin-activity-status"
CLAIM_PATH = "/v2/billing/meter/daily-checkin"
CHAT_PATH = "/v2/chat/completions"
REFRESH_PATH = "/v2/plugin/auth/token/refresh"
TOKEN_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wb_intl_tokens.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WORKBUDDY_INTL_ACCESS_TOKEN.txt")

CLIENT_VERSION = "5.5.2"
CLI_VERSION = "2.137.1"
UA = "WorkBuddy/%s WorkBuddy AI/%s CLI/%s" % (CLIENT_VERSION, CLIENT_VERSION, CLI_VERSION)
DEFAULT_MODELS = ("deepseek-v4.1-flash", "hy3", "hy4-preview", "hy4-preview-f")

# 活跃链路的三个端点（见文件头「活跃」一节）
REPORT_PATH = "/v2/report"
STREAK_PATH = "/activity/growth/streak"
WEB_CONVERSATIONS_PATH = "/console/as/conversations/"

# 对话链路身份（国际版客户端 5.8.4 实测；渠道校验 11-128 按这组头识别客户端）
CHAT_IDE_VERSION = "5.8.4"
CHAT_UA = "WorkBuddy/5.8.4 workbuddy-ai/5.8.4 CLI/2.161.0"
# 网页通道浏览器 UA（剔除全部桌面端指纹后，网页链路只认 Bearer + X-User-Id）
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

ONLY = None
NO_KEEPALIVE = False
REPORT_ONLY = False


HELP_TEXT = """用法:
  python workbuddy_intl_daily.py [--only N] [--no-keepalive] [--report-only]

选项:
  --only N          只处理第 N 个账号
  --no-keepalive    跳过保活对话与网页会话
  --report-only     仅复用 /v2/report 活跃上报链路（含连登回读）；
                    业务上不探测或领取每日奖励，不执行任务/奖励领取、保活或网页会话；
                    仍保留只读风控预检与必要令牌续期
  -h, --help        显示本帮助
"""


def log(msg):
    print("%s %s" % (time.strftime("[%H:%M:%S]"), msg), flush=True)


def mask(text, keep=6):
    text = str(text or "")
    if len(text) <= keep + 4:
        return text
    return text[:keep] + "****" + text[-4:]


def uid_of(token):
    """从 JWT 的 sub 取账号标识；取不到返回空串。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload)).get("sub") or "")
    except Exception:
        return ""


def api_headers(token, uid, accept=None):
    headers = {
        "Accept": accept or "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % token,
        "User-Agent": UA,
        "X-IDE-Type": "WorkBuddy",
        "X-IDE-Name": "WorkBuddy AI",
        "X-IDE-Version": CLIENT_VERSION,
        "X-Product": "WorkBuddy AI",
    }
    if uid:
        headers["X-User-Id"] = uid
    return headers


def chat_headers(token, uid):
    """对话链路请求头 —— 对齐国际版客户端 5.8.4 的会话头族与链路头族（渠道校验 11-128 的判据）。

    会话 / 消息 id 每次请求现生成（官方不拿它们存历史，补的是「有」而不是「稳定」）；
    不再发 X-Session-ID —— 官方对话请求不带它，旧的恒定派生值本身是一处网关特征。
    """
    conversation_id = str(uuid.uuid4())
    request_id = uuid.uuid4().hex
    message_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": CHAT_UA,
        "X-IDE-Type": "WorkBuddy",
        "X-IDE-Name": "WorkBuddy",
        "X-IDE-Version": CHAT_IDE_VERSION,
        "X-Product": "SaaS",
        "X-Agent-Intent": "craft",
        "X-Agent-Purpose": "conversation",
        "X-Agent-Type": "main",
        "X-Private-Data": "true",
        "X-Conversation-ID": conversation_id,
        "X-Conversation-Request-ID": request_id,
        "X-Root-Request-ID": request_id,
        "X-Conversation-Message-ID": message_id,
        "X-Request-ID": message_id,
        "X-Trace-ID": trace_id,
        "traceparent": "00-%s-%s-01" % (trace_id, span_id),
        "b3": "%s-%s-1" % (trace_id, span_id),
        "X-B3-TraceId": trace_id,
        "X-B3-SpanId": span_id,
        "X-B3-Sampled": "1",
        "Accept-Language": "en-US",
        "X-Requested-With": "XMLHttpRequest",
        "X-CodeBuddy-Request": "1",
        "Origin": BASE,
        "Referer": BASE + "/",
        "X-Domain": "www.workbuddy.ai",
        "Authorization": "Bearer %s" % token,
    }
    if uid:
        headers["X-User-Id"] = uid
    return headers


def model_chain():
    """保活 / 网页会话共用的免费模型链（WORKBUDDY_INTL_MODELS 覆盖，缺省四个）。"""
    models = [m.strip() for m in (os.environ.get("WORKBUDDY_INTL_MODELS") or "").split(",") if m.strip()]
    return models or list(DEFAULT_MODELS)


def report_event(uid):
    """活跃上报事件（chat_request_send，官方客户端同形状；userId 必填，缺了会被静默丢弃）。"""
    now_ms = int(time.time() * 1000)
    conversation_id = "wbintl-" + uuid.uuid4().hex
    return {
        "eventCode": "chat_request_send",
        "timestamp": now_ms,
        "reportDelay": 0,
        "mode": "craft",
        "conversationId": conversation_id,
        "requestId": conversation_id,
        "inputLength": 12,
        "requestModelId": "deepseek-v4.1-flash",
        "requestModelName": "DeepSeek V4.1 Flash",
        "isPlan": False,
        "isAutoExecuteTerminal": False,
        "isAutoModify": False,
        "codebaseEnable": False,
        "maxToken": 0,
        "maxSteps": 0,
        "temperature": 0,
        "maxRetries": 0,
        "mentionContexts": [],
        "knowledgeId": [],
        "knowledgeName": [],
        "codebaseId": "",
        "mentionContextCount": 0,
        "command": "",
        "expertId": "",
        "recommendId": "",
        "skillId": "",
        "skillCount": 0,
        "totalCount": 0,
        "fileUri": "",
        "presentAt": now_ms,
        "traceId": "",
        "rootRequestId": conversation_id,
        "parentConversationId": conversation_id,
        "agentName": "default",
        "agentType": "conversation",
        "userId": uid,
    }


def report_activity(token, uid):
    """发一条活跃上报（点亮成长中心连登）并回读天数；返回 (ok, note)，失败不阻断签到。"""
    if not uid:
        return False, "缺少账号 uid，无法上报活跃"
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.post(BASE + REPORT_PATH, headers=api_headers(token, uid),
                                json=[report_event(uid)], timeout=25, verify=False)
        payload = json_of(response)
        if (response.status_code != 200 or not isinstance(payload, dict) or
                "code" not in payload or payload.get("code") != 0):
            return False, "上报未确认: HTTP %s code=%s" % (
                response.status_code,
                payload.get("code") if isinstance(payload, dict) else None,
            )
    except Exception as error:
        return False, str(error)

    readback_error = ""
    try:
        session = requests.Session()
        session.trust_env = False
        streak = session.get(BASE + STREAK_PATH, headers=api_headers(token, uid), timeout=20, verify=False)
        streak_payload = json_of(streak)
        if (streak.status_code != 200 or not isinstance(streak_payload, dict) or
                streak_payload.get("code") != 0):
            code = streak_payload.get("code") if isinstance(streak_payload, dict) else None
            readback_error = "HTTP %s code=%s" % (streak.status_code, code)
        else:
            data = streak_payload.get("data")
            data = data if isinstance(data, dict) else {}
            streak_data = data.get("streak")
            streak_data = streak_data if isinstance(streak_data, dict) else {}
            days_value = streak_data.get("days")
            if (isinstance(days_value, bool) or
                    not isinstance(days_value, (int, float))):
                readback_error = "缺少有效 days"
            else:
                return True, "活跃上报成功，连登 %d 天" % int(days_value)
    except Exception as error:
        readback_error = str(error)
    return False, "上报请求已接受但回读失败: %s" % (readback_error or "未知原因")


def web_conversation(token, uid):
    """网页通道建一个带 prompt 的会话（当日活跃计数只认它）；逐个免费模型尝试。"""
    if not uid:
        return False, "缺少账号 uid，无法建网页会话"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": WEB_UA,
        "Origin": BASE,
        "Referer": BASE + "/app",
        "Authorization": "Bearer %s" % token,
        "X-User-Id": uid,
    }
    last = ""
    for model in model_chain():
        body = {
            "prompt": "Hi",
            "model": model,
            "conversationOrigin": "workbuddy-app",
            "plugins": [{"name": "weixinpay", "marketplace": "codebuddy-builtin"}],
        }
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.post(BASE + WEB_CONVERSATIONS_PATH, headers=headers,
                                    json=body, timeout=40, verify=False)
            payload = json_of(response)
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            code = payload.get("code")
            if response.status_code == 200 and code in (0, None) and data.get("id"):
                return True, "网页会话已创建"
            last = "HTTP %s code=%s" % (response.status_code, code)
        except Exception as error:
            last = str(error)
    return False, last or "网页会话创建失败（模型链全部未建成）"


def post_json(path, token, uid, body=None, timeout=25, retries=3):
    url = BASE + path
    last = None
    for attempt in range(1, retries + 1):
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.post(url, headers=api_headers(token, uid), json=body if body is not None else {},
                                    timeout=timeout, verify=False)
            if 500 <= response.status_code < 600 and attempt < retries:
                last = RuntimeError("http %s" % response.status_code)
                time.sleep(1.0 * attempt)
                continue
            return response
        except Exception as error:
            last = error
            if attempt < retries:
                time.sleep(1.0 * attempt)
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


class AccountRestricted(RuntimeError):
    pass


class UnapprovedChannel(RuntimeError):
    pass


def is_account_restricted(status_code, payload):
    """WorkBuddy 国际版账号级风控：11140 / request illegal。"""
    code = payload.get("code") if isinstance(payload, dict) else None
    blob = (
        json.dumps(payload, ensure_ascii=False)
        if isinstance(payload, (dict, list))
        else str(payload or "")
    ).lower()
    if code in (11140, "11140"):
        return True
    markers = (
        "11140", "account restricted", "request illegal",
        "账号受限", "账号被限制", "账户受限",
    )
    return int(status_code or 0) == 403 and any(marker in blob for marker in markers)


def is_unapproved_channel(status_code, payload):
    """WorkBuddy 11-128：请求内容/渠道指纹被拒，不等同于账号风控或 Token 过期。"""
    code = payload.get("code") if isinstance(payload, dict) else None
    blob = (
        json.dumps(payload, ensure_ascii=False)
        if isinstance(payload, (dict, list))
        else str(payload or "")
    ).lower()
    if code == "11-128":
        return True
    markers = (
        "11-128",
        "unapproved channel",
        "illegal api invocation from an unapproved channel",
        "渠道限制",
    )
    return any(marker in blob for marker in markers)


def preflight_restricted(token, uid):
    """在刷新 RT 或执行写操作前只读探测账号级风控。"""
    response = post_json(STATUS_PATH, token, uid)
    payload = json_of(response)
    if is_unapproved_channel(response.status_code, payload or response.text):
        raise UnapprovedChannel(
            "WorkBuddy 国际版渠道指纹拦截（HTTP %s / 11-128）" % response.status_code)
    if is_account_restricted(response.status_code, payload or response.text):
        raise AccountRestricted(
            "WorkBuddy 国际版账号受限（HTTP %s / 11140）" % response.status_code)
    return response, payload


def claim_label(code, msg):
    mapping = {
        41000: "活动未开始或已结束",
        40901: "任务暂不可领取",
        401: "登录状态失效，请重新登录",
        40100: "登录状态失效，请重新登录",
        11140: "账号受限，请检查账号状态",
    }
    return mapping.get(code) or msg or ("code=%s" % code)


def detect_activity(token, uid):
    """返回 (status_available, active, today_checked_in, note)。"""
    response = post_json(STATUS_PATH, token, uid)
    payload = json_of(response)
    code = payload.get("code")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    available = response.status_code == 200 and code == 0
    active = bool(data.get("active"))
    checked = bool(data.get("today_checked_in", data.get("todayCheckedIn")))
    if not available:
        note = "活动未开放（%s）" % claim_label(code, first_text(payload.get("msg"), payload.get("message")) or "HTTP %s" % response.status_code)
    elif checked:
        note = "今日已领取"
    elif active:
        note = "活动开放，今日未领"
    else:
        note = "活动已关闭"
    return available, active, checked, note


def claim_daily(token, uid):
    """领取每日奖励；重复领取（400/409 + 已签文案）算已完成。"""
    response = post_json(CLAIM_PATH, token, uid)
    payload = json_of(response)
    code = payload.get("code")
    message = first_text(payload.get("msg"), payload.get("message"))
    if response.status_code == 200 and code == 0:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        gained = data.get("credits", data.get("reward", data.get("amount")))
        return True, ("领取成功 +%s" % gained) if gained else "领取成功"
    duplicate = ("已签" in message) or ("已领" in message) or ("already" in message.lower())
    if response.status_code in (400, 409) and duplicate:
        return True, "今日已领取"
    return False, claim_label(code, message) or ("HTTP %s" % response.status_code)


def day_completed_note(message, available, active, checked, claim_ok, report_ok, web_ok):
    """活动未开启、但活跃链路已完成时，把结果文案改成「今日活跃已完成」。

    上游 v3.0.8 的判定（issue #277）：活跃上报或网页会话任一成功即算当日活跃
    完成，积分由上游按活跃异步发放；只保活对话成功不算（它只维持「账号有调用」）。
    """
    if claim_ok or not (report_ok or web_ok):
        return message
    reasons = []
    if report_ok:
        reasons.append("连登已点亮")
    if web_ok:
        reasons.append("网页会话已建")
    if not (available and active and not checked):
        return "活动未开启，但今日活跃已完成（%s；积分由上游异步发放）" % "、".join(reasons)
    return "%s；但今日活跃已完成（%s）" % (message, "、".join(reasons))


def keepalive(token, uid):
    """发一次最小流式对话，维持账号「有调用」；逐个尝试免费模型。"""
    last = ""
    for model in model_chain():
        body = {
            "model": model,
            "stream": True,
            "max_tokens": 16,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "hi"},
            ],
        }
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.post(BASE + CHAT_PATH, headers=chat_headers(token, uid),
                                    json=body, timeout=60, verify=False, stream=True)
            status = response.status_code
            payload = {}
            detail = ""
            if status != 200:
                payload = json_of(response)
                try:
                    detail = response.text[:500]
                except Exception:
                    detail = ""
            try:
                response.close()
            except Exception:
                pass
            if status == 200:
                return True, model
            if is_unapproved_channel(status, payload or detail):
                raise UnapprovedChannel(
                    "WorkBuddy 国际版渠道指纹拦截（HTTP %s / 11-128）" % status)
            if is_account_restricted(status, payload or detail):
                raise AccountRestricted(
                    "WorkBuddy 国际版账号受限（HTTP %s / 11140）" % status)
            if status == 403:
                last = "HTTP 403（模型无权限，非账号风控）"
            else:
                last = "HTTP %s" % status
        except (AccountRestricted, UnapprovedChannel):
            raise
        except Exception as error:
            last = str(error)
    return False, last or "未知错误"


# ---------- 令牌续期（可选） ----------
# 需要一条 refresh_token（RT）才能续期；只给 AT 时按短期令牌使用，
# 到期后重新获取即可。续期结果写回 wb_intl_tokens.json。

# 固定锁文件不可删除：所有执行者必须锁住同一个文件，而不是被 os.replace 的令牌库。
_TOKEN_STORE_THREAD_LOCK = threading.Lock()


@contextmanager
def _token_store_lock():
    """串行化同一状态目录的线程与进程；覆盖读取、续期、写回和 AT 重建。"""
    with _TOKEN_STORE_THREAD_LOCK:
        fd = os.open(TOKEN_STORE + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                # 固定锁住偏移 0，空锁文件也能建立跨进程互斥。
                while True:
                    try:
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        break
                    except OSError as exc:
                        if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                            raise
                        time.sleep(0.05)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _write_recovery_file(path, text):
    """在目标同目录写恢复副本，成功后由 os.replace 原子替换目标。"""
    tmp = path + ".tmp-" + uuid.uuid4().hex
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    return tmp


def _write_refresh_recovery(store):
    payload = json.dumps(store, ensure_ascii=False, indent=2)
    return _write_recovery_file(TOKEN_STORE, payload)


def _save_refresh_store(store):
    os.replace(_write_refresh_recovery(store), TOKEN_STORE)


def _load_refresh_store():
    with open(TOKEN_STORE, encoding="utf-8") as handle:
        store = json.load(handle)
    if not isinstance(store, dict) or any(not isinstance(entry, dict) for entry in store.values()):
        raise ValueError("令牌池格式错误")
    return store


def _store_access_token(entry):
    return str((entry or {}).get("access_token") or "")


def _store_refresh_token(entry):
    return str((entry or {}).get("refresh_token") or "")


def _account_uid(account):
    return str(account.get("uid") or uid_of(account.get("token") or ""))


def _find_store_key(store, account):
    """按 uid、备注、JWT sub 和凭据定位账号，兼容别名键及轮换后的 RT。"""
    uid = _account_uid(account)
    for key in (uid, str(account.get("note") or "")):
        entry = store.get(key) if key else None
        if isinstance(entry, dict):
            stored_uid = uid_of(_store_access_token(entry))
            if not uid or not stored_uid or uid == stored_uid:
                return key
    if uid:
        for key, entry in store.items():
            if uid_of(_store_access_token(entry)) == uid:
                return key
    access_token = str(account.get("token") or "")
    refresh_token = str(account.get("refresh_token") or "")
    for key, entry in store.items():
        if access_token and _store_access_token(entry) == access_token:
            return key
        if refresh_token and _store_refresh_token(entry) == refresh_token:
            return key
    return uid or str(account.get("note") or "")


def _apply_store_credentials(account, entry):
    access_token = _store_access_token(entry)
    refresh_token = _store_refresh_token(entry)
    if access_token:
        account["token"] = access_token
    if refresh_token:
        account["refresh_token"] = refresh_token


def _rebuild_token_file(store):
    """按现有 AT 文件顺序匹配 JWT sub，重建成 @ 分隔的国际版 AT 文件。"""
    entries = {
        key: _store_access_token(entry)
        for key, entry in store.items()
        if _store_access_token(entry)
    }
    subjects = {key: uid_of(token) for key, token in entries.items()}
    existing = []
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as handle:
            existing = handle.read().strip().split("@")
    tokens = []
    matched = set()
    for token in existing:
        token = token.strip()
        if not token:
            continue
        subject = uid_of(token)
        candidates = [key for key, value in subjects.items() if subject and value == subject]
        if len(candidates) == 1:
            key = candidates[0]
            if key in matched:
                continue
            matched.add(key)
            token = entries[key]
        if token not in tokens:
            tokens.append(token)
    for key, token in entries.items():
        if key not in matched and token not in tokens:
            tokens.append(token)
    os.replace(_write_recovery_file(TOKEN_FILE, "@".join(tokens)), TOKEN_FILE)


def _hydrate_account_from_store(account, log_fn=log):
    """在预检前载入其他执行者已经写入的最新 RT/AT；不触发网络请求。"""
    with _token_store_lock():
        try:
            store = _load_refresh_store()
        except FileNotFoundError:
            return False
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError("无法安全读取国际版令牌池: %s" % str(exc)[:100]) from exc
        key = _find_store_key(store, account)
        entry = store.get(key)
        if not isinstance(entry, dict):
            return False
        latest_at = _store_access_token(entry)
        latest_rt = _store_refresh_token(entry)
        if not latest_at or not latest_rt:
            return False
        if latest_at == account.get("token") and latest_rt == account.get("refresh_token"):
            return False
        _apply_store_credentials(account, entry)
        log_fn("   🔄 已载入其他执行者更新的令牌，使用最新凭据继续")
        return True


def load_store():
    with _token_store_lock():
        try:
            return _load_refresh_store()
        except FileNotFoundError:
            return {}


def save_store(store):
    if not isinstance(store, dict) or any(not isinstance(entry, dict) for entry in store.values()):
        raise ValueError("令牌池格式错误")
    with _token_store_lock():
        _save_refresh_store(store)
        _rebuild_token_file(store)


def refresh_token(at, rt):
    """用 RT 换新令牌；返回 (新AT, 新RT) 或 (None, 原因)。"""
    if not rt:
        return None, "未提供 refresh token"
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.post(BASE + REFRESH_PATH, json={}, timeout=20, verify=False,
                                headers={"X-Refresh-Token": rt,
                                         "X-Auth-Refresh-Source": "plugin",
                                         "Content-Type": "application/json"})
        payload = response.json()
    except Exception as error:
        return None, str(error)
    if response.status_code != 200:
        return None, "HTTP %s" % response.status_code
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    token = data.get("accessToken") or data.get("access_token")
    if payload.get("code") == 0 and token:
        return token, (data.get("refreshToken") or data.get("refresh_token") or rt)
    return None, first_text(payload.get("msg"), payload.get("message")) or "code=%s" % payload.get("code")


def _refresh_account_once(account, log_fn=log):
    """持共享锁续期当前账号；网络前后按 RT+AT 做 CAS，冲突时采用最新凭据。"""
    with _token_store_lock():
        refresh_token_value = str(account.get("refresh_token") or "")
        if not refresh_token_value:
            log_fn("   ❌ 需要续期，但该账号没有 RT")
            return False
        try:
            store = _load_refresh_store()
        except FileNotFoundError:
            store = {}
        except (OSError, ValueError, TypeError) as exc:
            log_fn("   ❌ 无法安全读取国际版令牌池: %s" % str(exc)[:100])
            raise RuntimeError("国际版令牌池读取失败，已停止该账号续期") from exc

        store_key = _find_store_key(store, account)
        current = store.get(store_key) if store_key else None
        current_at = _store_access_token(current) or str(account.get("token") or "")
        current_rt = _store_refresh_token(current) or refresh_token_value
        if isinstance(current, dict):
            latest_at = _store_access_token(current)
            latest_rt = _store_refresh_token(current)
            if latest_at and latest_rt and (
                    latest_at != account.get("token") or latest_rt != refresh_token_value):
                _apply_store_credentials(account, current)
                log_fn("   🔄 已载入其他执行者续期的令牌，重试当前账号")
                return True

        try:
            access_token, next_refresh = refresh_token(current_at, current_rt)
        except Exception as exc:
            access_token, next_refresh = None, str(exc)

        # 网络期间可能发生非协作写入；必须重读后比较开始时快照的 RT+AT。
        try:
            latest = _load_refresh_store()
        except FileNotFoundError:
            latest = {}
        except (OSError, ValueError, TypeError) as exc:
            rotated = {
                store_key: {
                    **(current if isinstance(current, dict) else {}),
                    "access_token": access_token or current_at,
                    "refresh_token": next_refresh or current_rt,
                    "updated": time.strftime("%Y-%m-%d %H:%M"),
                }
            }
            try:
                _write_refresh_recovery(rotated)
            except Exception as recovery_exc:
                log_fn("   ❌ 续期结果恢复副本写入失败: %s" % str(recovery_exc)[:100])
            log_fn("   ❌ 续期后无法重读最新令牌池: %s" % str(exc)[:100])
            raise RuntimeError("续期后的令牌状态未能安全合并") from exc

        latest_key = _find_store_key(latest, {
            "uid": account.get("uid") or "",
            "note": account.get("note") or "",
            "token": current_at,
            "refresh_token": current_rt,
        })
        latest_entry = latest.get(latest_key) if latest_key else None
        latest_at = _store_access_token(latest_entry) or current_at
        latest_rt = _store_refresh_token(latest_entry) or current_rt
        credentials_changed = False
        if isinstance(current, dict):
            credentials_changed = (
                not isinstance(latest_entry, dict) or
                latest_at != current_at or
                latest_rt != current_rt
            )
        elif isinstance(latest_entry, dict):
            credentials_changed = (
                latest_at != current_at or
                latest_rt != current_rt
            )

        if credentials_changed:
            if _store_access_token(latest_entry) and _store_refresh_token(latest_entry):
                _apply_store_credentials(account, latest_entry)
                log_fn("   🔄 续期期间其他执行者已轮换，采用最新令牌并重试当前账号")
                return True
            raise RuntimeError("续期期间令牌池中的账号凭据不完整")

        if not access_token:
            log_fn("   ⚠️ 令牌续期失败: %s" % str(next_refresh)[:100])
            return False

        rotated = {
            **(latest_entry if isinstance(latest_entry, dict) else {}),
            "access_token": access_token,
            "refresh_token": next_refresh or current_rt,
            "updated": time.strftime("%Y-%m-%d %H:%M"),
        }
        if not latest_key:
            latest_key = _find_store_key(latest, account)
        latest[latest_key] = rotated
        try:
            _save_refresh_store(latest)
        except Exception as exc:
            try:
                _write_refresh_recovery(latest)
            except Exception as recovery_exc:
                log_fn("   ❌ 续期结果恢复副本写入失败: %s" % str(recovery_exc)[:100])
            log_fn("   ❌ 令牌续期成功但令牌池保存失败: %s" % str(exc)[:100])
            raise RuntimeError("续期后的令牌状态未能保存") from exc
        try:
            _rebuild_token_file(latest)
        except Exception as exc:
            log_fn("   ⚠️ 令牌池已保存，但国际版 AT 文件重建失败: %s" % str(exc)[:100])
        _apply_store_credentials(account, rotated)
        log_fn("   🔑 令牌已续期（%s）" % mask(access_token))
        return True


def _prepare_account_for_run(account, hydrated, log_fn=log):
    """预检账号；401 或常规续期后必须用新 AT 再预检一次。"""
    response, _ = preflight_restricted(account["token"], account["uid"])
    preflight_401 = response.status_code == 401
    refresh_needed = preflight_401 or (
        bool(account.get("refresh_token")) and not hydrated
    )
    if not refresh_needed:
        return
    if not account.get("refresh_token"):
        if preflight_401:
            raise RuntimeError("预检 HTTP 401，但账号没有 refresh token")
        return

    refreshed = _refresh_account_once(account, log_fn)
    if preflight_401 and not refreshed:
        raise RuntimeError("预检 HTTP 401 后续期失败，未继续使用旧 AT")
    if not refreshed:
        return

    retry_response, _ = preflight_restricted(account["token"], account["uid"])
    if retry_response.status_code == 401:
        raise RuntimeError("续期成功但预检仍返回 HTTP 401，未继续使用旧 AT")



def parse_accounts(raw):
    accounts = []
    for index, line in enumerate((raw or "").replace("&", "\n").splitlines(), 1):
        line = line.strip().strip('"\'')
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        note, token, uid, rt = "账号%d" % index, "", "", ""
        if len(parts) == 1:
            token = parts[0]
        elif len(parts) == 2:
            note, token = parts
        elif len(parts) == 3:
            note, token, uid = parts
        else:
            note, token, uid, rt = parts[0], parts[1], parts[2], parts[3]
        if not token:
            continue
        accounts.append({"note": note, "token": token, "uid": uid or uid_of(token), "refresh_token": rt})
    return accounts


def notify(text, title="WorkBuddy AI 每日活跃"):
    raw = text.encode("utf-8")[:1800].decode("utf-8", "ignore")
    key = os.getenv("QYWX_TOKEN", "").strip() or os.getenv("WECHAT_WEBHOOK", "").strip()
    if key:
        key = key.split("key=")[-1]
        try:
            requests.post("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + key,
                          json={"msgtype": "text", "text": {"content": title + "\n" + raw}}, timeout=15)
        except Exception as error:
            log("⚠️ 企业微信推送失败: %s" % error)
    token = os.getenv("PLUSPLUS_TOKEN", "").strip()
    if token:
        try:
            requests.post("http://www.pushplus.plus/send",
                          json={"token": token, "title": title, "content": raw, "template": "txt"}, timeout=15)
        except Exception as error:
            log("⚠️ PushPlus 推送失败: %s" % error)


def main():
    global ONLY, NO_KEEPALIVE, REPORT_ONLY
    ONLY = None
    NO_KEEPALIVE = False
    REPORT_ONLY = False
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(HELP_TEXT, end="")
        return 0
    if "--no-keepalive" in args:
        NO_KEEPALIVE = True
    if "--report-only" in args:
        REPORT_ONLY = True
    if "--only" in args:
        try:
            ONLY = int(args[args.index("--only") + 1])
        except Exception:
            ONLY = None

    raw = os.environ.get("WORKBUDDY_INTL_TOKENS", "").strip()
    if not raw:
        single = os.environ.get("WORKBUDDY_TOKEN", "").strip()
        raw = single
    accounts = parse_accounts(raw)
    if not accounts:
        log("❌ 未配置 WORKBUDDY_INTL_TOKENS（或 WORKBUDDY_TOKEN）。")
        log("   国际版登录态与国内版不通用，请从 www.workbuddy.ai 获取。")
        return 1

    log("╔══════════════════════════════════════════╗")
    log("║ 🤖 WorkBuddy AI 国际版 每日活跃          ║" if not REPORT_ONLY else
        "║ 🤖 WorkBuddy AI 国际版 report-only       ║")
    log("╚══════════════════════════════════════════╝")
    log("👥 账号数: %d" % len(accounts))
    if REPORT_ONLY:
        log("🧪 report-only：业务动作仅执行 /v2/report 活跃上报；不探测/领取每日奖励，"
            "不执行任务/奖励领取、保活或网页会话（仍保留只读风控预检与必要令牌续期）")

    lines = []
    for index, account in enumerate(accounts, 1):
        if ONLY and index != ONLY:
            continue
        log("👤 [%d] %s  token=%s" % (index, account["note"], mask(account["token"])))
        try:
            hydrated = _hydrate_account_from_store(account, log)
            _prepare_account_for_run(account, hydrated, log)
            if REPORT_ONLY:
                report_ok, report_note = report_activity(account["token"], account["uid"])
                log("   %s 活跃上报: %s" % ("✅" if report_ok else "⚠️", report_note))
                lines.append("账号%d %s：report-only，不领取任务/奖励；活跃上报%s" % (
                    index, account["note"],
                    ("成功（%s）" % report_note) if report_ok else ("未成功（%s）" % report_note)))
                time.sleep(2)
                continue
            available, active, checked, note = detect_activity(account["token"], account["uid"])
            log("   探测: %s" % note)
            claim_ok = False
            if available and active and not checked:
                claim_ok, message = claim_daily(account["token"], account["uid"])
                log("   %s 领取: %s" % ("✅" if claim_ok else "❌", message))
            else:
                message = note
            report_ok, report_note = report_activity(account["token"], account["uid"])
            log("   %s 活跃上报: %s" % ("✅" if report_ok else "⚠️", report_note))
            if NO_KEEPALIVE:
                keep_ok, keep_note = False, "已跳过（--no-keepalive）"
                web_ok, web_note = False, "已跳过（--no-keepalive）"
            else:
                keep_ok, keep_note = keepalive(account["token"], account["uid"])
                keep_icon = "✅" if keep_ok else ("ℹ️" if "非账号风控" in str(keep_note) else "⚠️")
                log("   %s 保活: %s" % (keep_icon, keep_note))
                web_ok, web_note = web_conversation(account["token"], account["uid"])
                log("   %s 网页会话: %s" % ("✅" if web_ok else "⚠️", web_note))
            message = day_completed_note(message, available, active, checked,
                                         claim_ok, report_ok, web_ok)
            lines.append("账号%d %s：%s；活跃上报%s；保活%s；网页会话%s" % (
                index, account["note"], message,
                ("成功（%s）" % report_note) if report_ok else ("未成功（%s）" % report_note),
                ("成功（%s）" % keep_note) if keep_ok else ("未成功（%s）" % keep_note),
                ("成功（%s）" % web_note) if web_ok else ("未成功（%s）" % web_note)))
        except UnapprovedChannel as error:
            log("   🚫 %s：请求内容/渠道指纹被拒，不刷新、不重试；请检查 system prompt 与脱敏规则" % error)
            lines.append("账号%d %s：🚫 %s" % (index, account["note"], error))
        except AccountRestricted as error:
            log("   🚫 %s：本轮停止，不刷新、不重试" % error)
            lines.append("账号%d %s：🚫 %s" % (index, account["note"], error))
        except Exception as error:
            log("   ❌ 异常: %s" % error)
            lines.append("账号%d %s：❌ %s" % (index, account["note"], error))
        time.sleep(2)

    summary_title = "🤖 WorkBuddy AI 国际版 report-only" if REPORT_ONLY else "🤖 WorkBuddy AI 国际版每日活跃"
    summary = summary_title + "\n" + "\n".join(lines) + "\n🕐 " + time.strftime("%Y-%m-%d %H:%M")
    log(summary)
    if os.getenv("NO_NOTIFY", "").strip() != "1" and lines:
        notify(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
