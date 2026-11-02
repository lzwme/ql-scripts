#!/usr/bin/env python3
# -*- coding: utf-8 -*-
try:
    from utils import ql_env  # noqa: F401
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
"""

import base64
import json
import os
import sys
import time
import uuid

import requests
import urllib3

urllib3.disable_warnings()

BASE = "https://www.workbuddy.ai"
STATUS_PATH = "/billing/meter/checkin-activity-status"
CLAIM_PATH = "/v2/billing/meter/daily-checkin"
CHAT_PATH = "/v2/chat/completions"
REFRESH_PATH = "/v2/plugin/auth/token/refresh"
TOKEN_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wb_intl_tokens.json")

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
        if response.status_code != 200 or payload.get("code") not in (0, None):
            return False, "HTTP %s code=%s" % (response.status_code, payload.get("code"))
    except Exception as error:
        return False, str(error)
    days = None
    try:
        session = requests.Session()
        session.trust_env = False
        streak = session.get(BASE + STREAK_PATH, headers=api_headers(token, uid), timeout=20, verify=False)
        streak_payload = json_of(streak)
        days_value = ((streak_payload.get("data") or {}).get("streak") or {}).get("days")
        if isinstance(days_value, (int, float)):
            days = int(days_value)
    except Exception:
        days = None
    if days is not None:
        return True, "活跃上报成功，连登 %d 天" % days
    return True, "活跃上报成功"


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


def preflight_restricted(token, uid):
    """在刷新 RT 或执行写操作前只读探测账号级风控。"""
    response = post_json(STATUS_PATH, token, uid)
    payload = json_of(response)
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
            if is_account_restricted(status, payload or detail):
                raise AccountRestricted(
                    "WorkBuddy 国际版账号受限（HTTP %s / 11140）" % status)
            if status == 403:
                last = "HTTP 403（模型无权限，非账号风控）"
            else:
                last = "HTTP %s" % status
        except AccountRestricted:
            raise
        except Exception as error:
            last = str(error)
    return False, last or "未知错误"


# ---------- 令牌续期（可选） ----------
# 需要一条 refresh_token（RT）才能续期；只给 AT 时按短期令牌使用，
# 到期后重新获取即可。续期结果写回 wb_intl_tokens.json。


def load_store():
    try:
        with open(TOKEN_STORE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_store(store):
    try:
        with open(TOKEN_STORE, "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=2)
    except Exception as error:
        log("⚠️ 令牌缓存写入失败: %s" % error)


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
    global ONLY, NO_KEEPALIVE
    args = sys.argv[1:]
    if "--no-keepalive" in args:
        NO_KEEPALIVE = True
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
    log("║ 🤖 WorkBuddy AI 国际版 每日活跃          ║")
    log("╚══════════════════════════════════════════╝")
    log("👥 账号数: %d" % len(accounts))

    lines = []
    for index, account in enumerate(accounts, 1):
        if ONLY and index != ONLY:
            continue
        log("👤 [%d] %s  token=%s" % (index, account["note"], mask(account["token"])))
        try:
            preflight_restricted(account["token"], account["uid"])
            if account.get("refresh_token"):
                new_at, new_rt = refresh_token(account["token"], account["refresh_token"])
                if new_at:
                    account["token"], account["refresh_token"] = new_at, new_rt
                    log("   🔑 令牌已续期（%s）" % mask(new_at))
                    store = load_store()
                    store[account["uid"] or account["note"]] = {"access_token": new_at, "refresh_token": new_rt}
                    save_store(store)
                else:
                    log("   ⚠️ 令牌续期失败: %s（改用现有令牌）" % new_rt)
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
        except AccountRestricted as error:
            log("   🚫 %s：本轮停止，不刷新、不重试" % error)
            lines.append("账号%d %s：🚫 %s" % (index, account["note"], error))
        except Exception as error:
            log("   ❌ 异常: %s" % error)
            lines.append("账号%d %s：❌ %s" % (index, account["note"], error))
        time.sleep(2)

    summary = "🤖 WorkBuddy AI 国际版每日活跃\n" + "\n".join(lines) + "\n🕐 " + time.strftime("%Y-%m-%d %H:%M")
    log(summary)
    if os.getenv("NO_NOTIFY", "").strip() != "1" and lines:
        notify(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
