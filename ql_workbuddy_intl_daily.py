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

WorkBuddy AI（国际版）每日活跃与等级任务 - 青龙脚本
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
  4. 等级任务（可选，默认执行）：
     · 读取 GET /activity/growth/tasks（等级族，按 code 识别）
     · first_chat / skill_installed / expert_summoned / template_used
       先执行真实动作，再按服务端 status 回读；未确认完成绝不 claim
     · wechat_linked 只检测并提示在官方客户端绑定微信，不伪造完成

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
  python workbuddy_intl_daily.py --no-keepalive   # 只探测、领取与活跃上报；跳过保活、网页会话及依赖它的等级任务
  python workbuddy_intl_daily.py --report-only    # 只发 /v2/report 活跃上报，不领取任务或奖励
  python workbuddy_intl_daily.py --no-tasks       # 跳过图片中的 5 个等级任务
"""

import base64
import errno
import hashlib
import json
import os
import re
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
WEB_TASK_CONVERSATIONS_PATH = "/console/webchat/conversations"
WEB_TASK_SCENES_PATH = "/v2/as/support/scenes?locale=en"
GROWTH_TASKS_SOURCES = (
    ("level", "/activity/growth/tasks", "level"),
    ("desktop", "/v2/activity/growth/tasks", None),
    ("mp", "/v2/activity/growth/tasks", "miniprogram"),
)
GROWTH_ACCEPT_PATH = "/v2/activity/growth/tasks/accept"
GROWTH_CLAIM_PATH = "/activity/growth/tasks/%s/claim"
TARGET_GROWTH_TASKS = (
    "first_chat",
    "skill_installed",
    "wechat_linked",
    "expert_summoned",
    "template_used",
)
GROWTH_TASK_LABELS = {
    "first_chat": "完成一次对话",
    "skill_installed": "完成技能安装",
    "wechat_linked": "链接微信",
    "expert_summoned": "召唤一次专家",
    "template_used": "使用一次模板",
}
CLIENT_ONLY_GROWTH_TASKS = {"wechat_linked"}
TASK_EVENT_MODEL = "fast-model"

# 对话链路身份（国际版客户端 5.8.4 实测；渠道校验 11-128 按这组头识别客户端）
CHAT_IDE_VERSION = "5.8.4"
CHAT_UA = "WorkBuddy/5.8.4 workbuddy-ai/5.8.4 CLI/2.161.0"
TASK_EVENT_EXT_VERSION = CHAT_IDE_VERSION
TASK_EVENT_RELEASE_DATE = 1789036585355
TASK_EVENT_COMMIT = "5f9692923c93033111c51ad7b003eb80204a9b75"
TASK_EVENT_OS_VERSION = "10.0.26220"
TASK_EVENT_CPU_MODEL = "11th Gen Intel(R) Core(TM) i5-11320H @ 3.20GHz"
# 网页通道浏览器 UA（剔除全部桌面端指纹后，网页链路只认 Bearer + X-User-Id）
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

ONLY = None
NO_KEEPALIVE = False
REPORT_ONLY = False
NO_TASKS = False


HELP_TEXT = """用法:
  python workbuddy_intl_daily.py [--only N] [--no-keepalive] [--report-only] [--no-tasks]

选项:
  --only N          只处理第 N 个账号
  --no-keepalive    跳过保活对话与网页会话；依赖网页对话的等级任务动作也跳过
  --report-only     仅复用 /v2/report 活跃上报链路（含连登回读）；
                    业务上不探测或领取每日奖励，不执行任务/奖励领取、保活或网页会话；
                    仍保留只读风控预检与必要令牌续期
  --no-tasks        跳过 first_chat / skill_installed / wechat_linked /
                    expert_summoned / template_used 五个等级任务
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


def web_conversation_session(token, uid, prompt="Hi", session=None):
    """网页通道建一个带 prompt 的真实会话，返回 (ok, note, data, model)。"""
    if not uid:
        return False, "缺少账号 uid，无法建网页会话", {}, ""
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
    session = session or requests.Session()
    session.trust_env = False
    for model in model_chain():
        body = {
            "prompt": prompt,
            "model": model,
            "conversationOrigin": "workbuddy-app",
            "plugins": [{"name": "weixinpay", "marketplace": "codebuddy-builtin"}],
        }
        try:
            response = session.post(BASE + WEB_CONVERSATIONS_PATH, headers=headers,
                                    json=body, timeout=40, verify=False)
            payload = json_of(response)
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            code = payload.get("code")
            if (response.status_code == 200 and code in (0, None)
                    and (data.get("id") or data.get("conversationId"))):
                return True, "网页会话已创建", data, model
            last = "HTTP %s code=%s" % (response.status_code, code)
        except Exception as error:
            last = str(error)
    return False, last or "网页会话创建失败（模型链全部未建成）", {}, ""


def web_conversation(token, uid):
    """网页通道建一个带 prompt 的会话（当日活跃计数只认它）；逐个免费模型尝试。"""
    ok, note, _data, _model = web_conversation_session(token, uid)
    return ok, note


def growth_headers(token, uid, platform=None):
    """等级任务列表/接取/领奖/上报共用的国际版成长中心请求头。"""
    headers = {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Domain": "www.workbuddy.ai",
        "Origin": BASE,
        "Referer": BASE + "/profile/growth-center",
        "User-Agent": CHAT_UA,
        "X-Product": "SaaS",
    }
    if platform:
        headers["X-Client-Platform"] = platform
    if uid:
        headers["X-User-Id"] = uid
    return headers


def level_task_headers(token, uid):
    """等级族 `/activity/growth/tasks` 不发送 web 平台头，避免改变任务下发口径。"""
    headers = {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Domain": "www.workbuddy.ai",
        "Origin": BASE,
        "Referer": BASE + "/profile/growth-center",
        "User-Agent": CHAT_UA,
        "X-Product": "SaaS",
    }
    if uid:
        headers["X-User-Id"] = uid
    return headers


def task_report_headers(token, uid):
    headers = {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": CHAT_UA,
        "X-Domain": "www.workbuddy.ai",
        "X-Product": "SaaS",
        "X-Request-ID": uuid.uuid4().hex,
    }
    if uid:
        headers["X-User-Id"] = uid
    return headers


def web_task_chat_headers(token, uid):
    return {
        "Authorization": "Bearer %s" % token,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Origin": BASE,
        "Referer": BASE + "/",
        "User-Agent": WEB_UA,
        "X-Domain": "www.workbuddy.ai",
        "X-Product": "SaaS",
        "X-Client-Platform": "web",
        "X-Requested-With": "XMLHttpRequest",
        "X-CodeBuddy-Request": "1",
        "Accept-Language": "en-US",
        "X-User-Id": uid,
    }


def _web_task_response_detail(response, payload):
    """Return a short server-side reason without dumping full response data."""
    code = payload.get("code") if isinstance(payload, dict) else None
    message = first_text(
        payload.get("message"), payload.get("msg"), payload.get("errorMessage"),
        payload.get("error")) if isinstance(payload, dict) else ""
    parts = []
    if code not in (None, 0, "0"):
        parts.append("code=%s" % code)
    if message:
        parts.append(message)
    if not parts:
        try:
            text = str(response.text or "").strip()
        except Exception:
            text = ""
        if text:
            parts.append(text[:200])
    return "：%s" % "，".join(parts) if parts else ""


def create_web_task_conversation(token, uid, session=None):
    """Create a webchat conversation accepted by /console/chat/completions."""
    if not uid:
        return False, "缺少账号 uid，无法建网页任务会话", ""
    session = session or requests.Session()
    session.trust_env = False
    headers = web_task_chat_headers(token, uid)
    headers["Accept"] = "application/json"
    body = {"name": "WorkBuddy task-%s" % uuid.uuid4().hex[:8]}
    response = session.post(
        BASE + WEB_TASK_CONVERSATIONS_PATH,
        headers=headers,
        json=body,
        timeout=20,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    data = payload.get("data") if isinstance(payload, dict) else {}
    data = data if isinstance(data, dict) else {}
    conversation_id = first_text(data.get("conversationId"), data.get("id"))
    if response.status_code != 200 or not _growth_code_ok(code) or not conversation_id:
        detail = _web_task_response_detail(response, payload)
        return False, "网页任务会话创建失败（HTTP %s%s）" % (
            response.status_code, detail), ""
    return True, "", conversation_id


def _task_identity(uid):
    machine = hashlib.sha256(("machine:" + str(uid)).encode("utf-8")).hexdigest()[:36]
    session = hashlib.sha256(("session:" + str(uid)).encode("utf-8")).hexdigest()[:36]
    qimei = hashlib.sha256(("qimei:" + str(uid)).encode("utf-8")).hexdigest()[:36]
    return {
        "timezone": "Asia/Shanghai",
        "reportDelay": 2000,
        "userId": str(uid),
        "username": "",
        "userNickname": "",
        "product": "SaaS",
        "releaseDate": TASK_EVENT_RELEASE_DATE,
        "commit": TASK_EVENT_COMMIT,
        "ideName": "WorkBuddy",
        "ideType": "WorkBuddy",
        "ideVersion": TASK_EVENT_EXT_VERSION,
        "machineId": machine,
        "sessionId": session,
        "qimei36": qimei,
        "extName": "workbuddy-desktop",
        "extVersion": TASK_EVENT_EXT_VERSION,
        "os": "win32",
        "osVersion": TASK_EVENT_OS_VERSION,
        "arch": "x64",
        "cpuModel": TASK_EVENT_CPU_MODEL,
        "cpuCores": 20,
        "memorySize": 24,
        "userAgent": CHAT_UA,
        "presentAt": int(time.time() * 1000),
    }


def _parse_task_sse(response):
    """读取 `/console/chat/completions` SSE，返回 (完成, 文本, 服务端 messageId)。"""
    text_parts = []
    server_message_id = ""
    finished = False
    for raw in response.iter_lines(decode_unicode=True):
        if isinstance(raw, bytes):
            line = raw.decode("utf-8", "ignore")
        else:
            line = str(raw or "")
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data in ("[DONE]", "[完成]", "[✅完成]"):
            finished = True
            break
        try:
            item = json.loads(data)
        except Exception:
            continue
        if not server_message_id:
            server_message_id = str(
                item.get("id") or item.get("messageId") or item.get("message_id") or "")
        for choice in item.get("choices") or []:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            content = delta.get("content") if isinstance(delta, dict) else ""
            if content:
                text_parts.append(str(content))
    return finished or bool(server_message_id and text_parts), "".join(text_parts), server_message_id


def web_task_conversation_session(token, uid, prompt, metadata=None):
    """建真实网页会话并完成一次 SSE 对话，返回服务端会话/消息 id。"""
    session = requests.Session()
    session.trust_env = False
    ok, note, conversation_id = create_web_task_conversation(
        token, uid, session=session)
    if not ok:
        return False, note, {}, ""
    last_error = ""
    for model in model_chain():
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "model": model,
            "stream": True,
            "conversationId": conversation_id,
        }
        if isinstance(metadata, dict) and metadata:
            body["_meta"] = metadata
        headers = web_task_chat_headers(token, uid)
        response = session.post(
            BASE + "/console/chat/completions",
            headers=headers,
            json=body,
            timeout=90,
            verify=False,
            stream=True,
        )
        try:
            payload = json_of(response) if response.status_code != 200 else {}
            _check_growth_response(response, payload)
            if response.status_code != 200:
                last_error = "网页对话 HTTP %s%s" % (
                    response.status_code,
                    _web_task_response_detail(response, payload))
                continue
            try:
                finished, text, server_message_id = _parse_task_sse(response)
            except (AccountRestricted, UnapprovedChannel):
                raise
            except Exception as error:
                last_error = "网页对话流读取失败: %s" % str(error)[:80]
                continue
        finally:
            try:
                response.close()
            except Exception:
                pass
        if not finished or not server_message_id:
            last_error = "网页对话未完成或缺少服务端 messageId"
            continue
        return True, "网页对话已完成", {
            "id": conversation_id,
            "requestId": server_message_id,
            "messageId": server_message_id,
            "text": text,
        }, model
    return False, last_error or "网页对话失败（模型链全部未完成）", {}, ""


def growth_task_code(row):
    if not isinstance(row, dict):
        return ""
    return str(row.get("task_code") or row.get("code") or "").strip()


def growth_task_status(row):
    if not isinstance(row, dict):
        return ""
    return str(row.get("accept_status") or row.get("status") or "").strip().lower()


def growth_task_progress(row):
    progress = row.get("progress") if isinstance(row, dict) else None
    if not isinstance(progress, dict):
        return None, None
    current = progress.get("current")
    target = progress.get("target")
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        current = None
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        target = None
    return current, target


def growth_task_is_claimed(row):
    if not isinstance(row, dict):
        return False
    claimed = row.get("claimed")
    return (
        growth_task_status(row) == "claimed"
        or claimed is True
        or str(claimed).strip().lower() == "true"
    )


def growth_task_is_ready(row):
    if not isinstance(row, dict) or growth_task_is_claimed(row) or row.get("locked"):
        return False
    status = growth_task_status(row)
    if status == "completed":
        return True
    if status != "accepted":
        return False
    current, target = growth_task_progress(row)
    return (
        isinstance(current, (int, float))
        and isinstance(target, (int, float))
        and target > 0
        and current >= target
    )


def _growth_task_merge_rank(row):
    """跨 v1/v2 合并时的状态优先级；不能用手头较弱的行覆盖 claimed。"""
    if growth_task_is_claimed(row):
        rank = 50
    else:
        status = growth_task_status(row)
        if status == "completed":
            rank = 40
        elif status in ("accepted", "in_progress", "already_accepted"):
            rank = 30
        elif status == "not_accepted":
            rank = 20
        elif status == "available":
            rank = 10
        elif row.get("locked"):
            rank = 5
        else:
            rank = 0
    source_bonus = {"level": 2, "desktop": 1, "mp": 0}.get(
        str(row.get("_source") or ""), 0)
    return rank, source_bonus


def growth_task_is_locked(row):
    return bool(isinstance(row, dict) and row.get("locked"))


def growth_task_progress_text(row):
    current, target = growth_task_progress(row)
    status = growth_task_status(row) or "unknown"
    if current is None or target is None:
        return status
    return "%s %s/%s" % (status, current, target)


def _growth_code_ok(code):
    return code in (0, 200, "0", "200", None)


def _check_growth_response(response, payload):
    if is_unapproved_channel(response.status_code, payload or response.text):
        raise UnapprovedChannel(
            "WorkBuddy 国际版渠道指纹拦截（HTTP %s / 11-128）" % response.status_code)
    if is_account_restricted(response.status_code, payload or response.text):
        raise AccountRestricted(
            "WorkBuddy 国际版账号受限（HTTP %s / 11140）" % response.status_code)


def fetch_growth_tasks(token, uid):
    """读取等级族与成长族任务列表，返回 (按 code 合并的行, 错误列表)。"""
    merged = {}
    errors = []
    for source, path, platform in GROWTH_TASKS_SOURCES:
        try:
            session = requests.Session()
            session.trust_env = False
            headers = (level_task_headers(token, uid)
                       if source == "level"
                       else growth_headers(token, uid, platform=platform))
            response = session.get(
                BASE + path,
                headers=headers,
                timeout=25,
                verify=False,
            )
            payload = json_of(response)
            _check_growth_response(response, payload)
            code = payload.get("code") if isinstance(payload, dict) else None
            if response.status_code != 200 or not _growth_code_ok(code):
                errors.append("%s HTTP %s code=%s" % (path, response.status_code, code))
                continue
            rows = ((payload.get("data") or {}).get("tasks")
                    if isinstance(payload, dict) else None)
            if not isinstance(rows, list):
                errors.append("%s 未返回 tasks 列表" % path)
                continue
            for row in rows:
                task_code = growth_task_code(row)
                if task_code not in TARGET_GROWTH_TASKS:
                    continue
                item = dict(row)
                item["_path"] = path
                item["_source"] = source
                item["_platform"] = platform
                old = merged.get(task_code)
                if old is None or _growth_task_merge_rank(item) > _growth_task_merge_rank(old):
                    merged[task_code] = item
        except (AccountRestricted, UnapprovedChannel):
            raise
        except Exception as error:
            errors.append("%s %s" % (path, str(error)[:80]))
    return merged, errors


def accept_growth_task(token, uid, task_code):
    """接取 v2 成长任务并回读 accept_status；等级族没有 accept。"""
    settled = ("accepted", "already_accepted", "completed", "claimed")
    last_status = ""
    for attempt in range(2):
        session = requests.Session()
        session.trust_env = False
        response = session.post(
            BASE + GROWTH_ACCEPT_PATH,
            headers=growth_headers(token, uid),
            json={"task_codes": [task_code]},
            timeout=20,
            verify=False,
        )
        payload = json_of(response)
        _check_growth_response(response, payload)
        payload = payload if isinstance(payload, dict) else {}
        code = payload.get("code")
        results = (payload.get("data") or {}).get("results") or []
        result = next(
            (item for item in results
             if isinstance(item, dict)
             and str(item.get("task_code") or item.get("code") or "") == task_code),
            results[0] if results and isinstance(results[0], dict) else {},
        )
        last_status = str(
            result.get("status") or payload.get("msg") or "")
        if response.status_code != 200 or not _growth_code_ok(code):
            if attempt == 0:
                time.sleep(1)
                continue
            return False, "accept HTTP %s code=%s" % (response.status_code, code)
        if attempt == 0:
            time.sleep(1)
        rows, _errors = fetch_growth_tasks(token, uid)
        row = rows.get(task_code) or {}
        status = growth_task_status(row)
        if status in settled:
            return True, "已接取（%s）" % status
        last_status = status or last_status
    return False, "accept 回读仍为 %s" % (last_status or "unknown")


def report_growth_events(token, uid, events):
    """向国际版成长中心上报任务判据事件。"""
    if not events:
        return False, "没有可上报事件"
    now_ms = int(time.time() * 1000)
    identity = _task_identity(uid)
    body = []
    for event in events:
        item = dict(identity)
        item.update(event)
        item.setdefault("timestamp", now_ms)
        item["userId"] = str(uid)
        body.append(item)
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        BASE + REPORT_PATH,
        headers=task_report_headers(token, uid),
        json=body,
        timeout=25,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if response.status_code == 200 and _growth_code_ok(code):
        return True, "任务事件已上报（%d 条）" % len(body)
    return False, "任务事件未确认 HTTP %s code=%s" % (response.status_code, code)


def claim_growth_task(token, uid, task_code):
    """领奖后必须回读 claimed；只收到 HTTP 200 不算完成。"""
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        BASE + GROWTH_CLAIM_PATH % task_code,
        headers=growth_headers(token, uid),
        json={},
        timeout=20,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    payload = payload if isinstance(payload, dict) else {}
    code = payload.get("code")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = first_text(payload.get("msg"), payload.get("message"))
    already = (bool(data.get("already_claimed"))
               or any(marker in message.lower() for marker in ("already", "已领取", "已领过")))
    has_reward = any(
        data.get(key) not in (None, "", 0, "0")
        for key in ("credit", "energy", "reward", "reward_credit", "reward_energy")
    )
    if not (response.status_code == 200 and _growth_code_ok(code)
            and (already or has_reward or data.get("claimed") is True)):
        return False, "领奖未确认 HTTP %s code=%s" % (
            response.status_code, code)
    row = {}
    readback_error = ""
    for attempt in range(3):
        if attempt:
            time.sleep(1)
        try:
            rows, errors = fetch_growth_tasks(token, uid)
            row = rows.get(task_code) or {}
            if growth_task_is_claimed(row):
                return True, "已领取（回读确认）"
            readback_error = "；".join(errors)
        except (AccountRestricted, UnapprovedChannel):
            raise
        except Exception as error:
            readback_error = str(error)
    detail = growth_task_progress_text(row) if row else (readback_error or "未读到任务行")
    return False, "领奖已提交但回读仍为 %s" % detail


def _new_task_request_id():
    return uuid.uuid4().hex


def _chat_event_chain(uid, conversation_id, request_id, message_id=None,
                      model=TASK_EVENT_MODEL):
    """桌面/网页通用对话六连事件，字段对齐成长中心任务判据。"""
    message_id = str(message_id or (conversation_id + "-m"))
    common = {
        "traceId": request_id,
        "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli",
        "agentType": "main",
        "codebuddy.session_id": conversation_id,
        "codebuddy.conversation_request_id": request_id,
    }
    return [
        {
            "eventCode": "agent_task_created",
            "source": "LOCAL", "name": "working", "task_target": "local", "mode": "craft",
            "requestModelId": model, "requestModelName": model, "has_repo": False,
            "repo_type": "none", "workspace_type": "empty", "has_connector": False,
            "connector_types": [], "has_mention": False, "mention_types": [],
            "has_template": False, "action": "", "template_name": "", "has_expert": False,
            "expert_id": "", "expert_name": "", "expert_industry_id": "",
            "has_skill": False, "skill_names": [], "conversationId": conversation_id,
            "messageId": message_id, "buddyId": "", "buddyName": "",
        },
        {
            "eventCode": "chat_message_send", "messageId": message_id + "-assistant",
            "historyCount": 0, "isContextTruncated": False, "currentStepCount": 1,
            **common,
        },
        {
            "eventCode": "chat_request_send", "inputLength": 24, "isPlan": False,
            "isAutoExecuteTerminal": False, "isAutoModify": False, "codebaseEnable": False,
            "maxToken": 0, "maxSteps": 500, "temperature": 0, "maxRetries": 0,
            "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
            "codebaseId": "", "mentionContextCount": 0, "command": "", "recommendId": "",
            "skillId": "", "skillCount": 0, "totalCount": 0, **common,
        },
        {
            "eventCode": "chat_message_response", "messageId": message_id + "-assistant",
            "responseModelId": model, "inputToken": 120, "outputToken": 80,
            "totalToken": 200, "cachedTokens": 0, "cachedWriteTokens": 0,
            "cachedMissTokens": 0, "isSuccessful": True, "messageErrorCode": "",
            "finishReason": "stop", "firstTokenAt": int(time.time() * 1000),
            "conversationId": conversation_id, **common,
        },
        {
            "eventCode": "chat_message_status", "messageId": message_id + "-assistant",
            "messageErrorCode": "0", **common,
        },
        {
            "eventCode": "chat_request_response", "mode": "craft", "toolCallCount": 0,
            "inputToken": 120, "outputToken": 80, "totalToken": 200,
            "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
            "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
            **common,
        },
    ]


def _growth_metadata(events, request_id, expert=None, prompt="", uid=""):
    meta = {
        "growthEvent": json.dumps(events, ensure_ascii=False),
        "promptRequestId": request_id,
        "clientSendTime": int(time.time() * 1000),
        "userId": str(uid),
        "mode": "LOCAL",
        "model": TASK_EVENT_MODEL,
    }
    if expert:
        meta.update({
            "expertId": expert.get("id") or "",
            "expert": {
                "id": expert.get("id") or "",
                "name": expert.get("name") or "",
                "prompt": prompt[:50],
            },
            "tags": ["expert:" + str(expert.get("id") or "")],
        })
    return meta


def fetch_task_expert(token, uid, expected_id=""):
    first = None
    for page in range(1, 4):
        session = requests.Session()
        session.trust_env = False
        response = session.post(
            BASE + "/v2/operation-platform/market/expert/list",
            headers=growth_headers(token, uid),
            json={"page": page, "page_size": 50, "expert_type": "agent"},
            timeout=25,
            verify=False,
        )
        payload = json_of(response)
        _check_growth_response(response, payload)
        code = payload.get("code") if isinstance(payload, dict) else None
        if response.status_code != 200 or not _growth_code_ok(code):
            return None, "专家市场 HTTP %s code=%s" % (response.status_code, code)
        rows = ((payload.get("data") or {}).get("experts")
                if isinstance(payload, dict) else None)
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            expert_id = str(
                row.get("expert_id") or row.get("source_id") or row.get("id") or "")
            if not expert_id:
                continue
            display = row.get("display_name_zh") or row.get("displayName") or row.get("name")
            if isinstance(display, dict):
                display = display.get("zh") or display.get("en")
            profession = row.get("profession_zh") or row.get("profession") or display
            if isinstance(profession, dict):
                profession = profession.get("zh") or profession.get("en")
            item = {
                "id": expert_id,
                "name": str(display or expert_id),
                "profession": str(profession or expert_id),
                "version": str(row.get("version") or "1.0.0"),
                "expertType": str(row.get("expert_type") or "agent"),
            }
            if expected_id and expert_id == expected_id:
                return item, ""
            if first is None:
                first = item
        if len(rows or []) < 50:
            break
    if expected_id:
        return None, "专家市场未找到任务绑定专家 %s" % expected_id
    if first:
        return first, ""
    return None, "专家市场未返回可用专家"


def fetch_task_skill(token, uid):
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        BASE + "/v2/operation-platform/market/skill/list",
        headers=growth_headers(token, uid),
        json={"page": 1, "page_size": 8},
        timeout=25,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if response.status_code != 200 or not _growth_code_ok(code):
        return None, "技能市场 HTTP %s code=%s" % (response.status_code, code)
    rows = ((payload.get("data") or {}).get("skills")
            if isinstance(payload, dict) else None)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        skill_id = str(row.get("skill_id") or row.get("skillId") or row.get("id") or "")
        if not skill_id:
            continue
        skill_name = row.get("name") or row.get("display_name") or row.get("displayName")
        if isinstance(skill_name, dict):
            skill_name = skill_name.get("zh") or skill_name.get("en")
        slug = row.get("slug") or row.get("plugin_name") or row.get("skill_slug")
        slug = str(slug or skill_name or skill_id)
        return {
            "id": skill_id,
            "slug": slug,
            "name": str(skill_name or skill_id),
        }, ""
    return None, "技能市场未返回可用技能"


def fetch_task_scene(token, uid):
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        BASE + WEB_TASK_SCENES_PATH,
        headers={"Accept": "application/json", "User-Agent": WEB_UA},
        timeout=20,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if response.status_code != 200 or not _growth_code_ok(code):
        return None, "场景表 HTTP %s code=%s" % (response.status_code, code)
    rows = ((payload.get("data") or {}).get("scenes")
            if isinstance(payload, dict) else None)
    for row in rows or []:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        return {
            "id": str(row.get("id")),
            "name": str(row.get("name") or row.get("title") or row.get("id")),
        }, ""
    return None, "场景表未返回可用模板"


def install_task_skill(token, uid, skill):
    """调用官方安装接口，并以已安装插件列表回读确认。"""
    session = requests.Session()
    session.trust_env = False

    def installed():
        check = session.get(
            BASE + "/console/as/user/plugins/installed",
            headers=growth_headers(token, uid),
            timeout=20,
            verify=False,
        )
        check_payload = json_of(check)
        _check_growth_response(check, check_payload)
        check_code = check_payload.get("code") if isinstance(check_payload, dict) else None
        if check.status_code != 200 or not _growth_code_ok(check_code):
            return False
        plugins = ((check_payload.get("data") or {}).get("plugins")
                   if isinstance(check_payload, dict) else None)
        for row in plugins or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("plugin_name") or row.get("name") or "")
            plugin_id = str(row.get("id") or row.get("plugin_id") or "")
            if (name in (skill.get("slug"), skill.get("name"))
                    or (skill.get("id") and plugin_id == skill["id"])):
                return True
        return False

    if installed():
        return True, "技能已安装（回读确认）"
    response = session.get(
        BASE + "/console/as/marketplace/sources",
        headers=growth_headers(token, uid),
        timeout=20,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if response.status_code != 200 or not _growth_code_ok(code):
        return False, "技能来源 HTTP %s code=%s" % (response.status_code, code)
    rows = ((payload.get("data") or {}).get("sources")
            if isinstance(payload, dict) else None)
    marketplace_id = next(
        (str(row.get("id")) for row in rows or [] if isinstance(row, dict) and row.get("id")),
        "",
    )
    if not marketplace_id:
        return False, "未取得 marketplace_id"
    response = session.post(
        BASE + "/console/as/user/plugins/install",
        headers=growth_headers(token, uid),
        json={
            "plugin_name": skill.get("slug") or skill["name"],
            "marketplace_id": marketplace_id,
            "version": "latest",
        },
        timeout=30,
        verify=False,
    )
    payload = json_of(response)
    _check_growth_response(response, payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    if response.status_code == 200 and _growth_code_ok(code):
        for _attempt in range(3):
            if installed():
                return True, "技能安装成功（回读确认）"
            time.sleep(1)
        return False, "技能安装接口已接受，但回读未发现已安装插件"
    return False, "技能安装 HTTP %s code=%s" % (response.status_code, code)


def _template_task_events(template, conversation_id, request_id):
    tid = template["id"]
    tname = template["name"]
    return [
        {
            "eventCode": "agent_task_created", "source": "CLOUD", "name": "",
            "mode": "craft", "requestModelId": "default", "action": tid,
            "has_template": True, "template_id": tid, "template_name": tname,
            "requestId": request_id, "conversationId": conversation_id,
        },
        {
            "eventCode": "agent_task_created_with_template", "templateId": tid,
            "templateName": tname, "template_id": tid, "mode": "working",
            "isCustomModel": True, "id": tid, "name": tname,
            "requestId": request_id, "conversationId": conversation_id,
        },
        {
            "eventCode": "template_used", "template_id": tid, "templateId": tid,
            "templateName": tname, "task_mode": "working", "id": tid,
            "name": tname, "source": "growth-center",
            "conversationId": conversation_id,
        },
        {
            "eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()),
            "requestId": request_id, "id": tid, "name": tname, "type": "other",
            "promptLength": 30, "isOfficial": 1, "source": "growth-center",
            "conversationId": conversation_id,
        },
    ]


def _expert_task_events(expert, conversation_id, request_id, message_id, prompt):
    expert_id = expert["id"]
    display_name = expert["name"]
    expert_title = expert.get("profession") or display_name
    expert_type = expert.get("expertType") or "agent"
    version = expert.get("version") or "1.0.0"
    summon = [
        {
            "eventCode": "expert_summon_click", "id": expert_id,
            "name": display_name, "expertTitle": expert_title, "type": "agent",
            "expertType": expert_type, "source": "builtin", "mode": "LOCAL",
        },
        {
            "eventCode": "expert_summoned", "id": expert_id, "name": display_name,
            "expertTitle": expert_title, "type": "agent",
            "expertType": expert_type, "source": "builtin", "version": version,
            "mode": "LOCAL",
        },
    ]
    chain = _chat_event_chain(
        "", conversation_id, request_id, message_id=message_id, model=TASK_EVENT_MODEL)
    for event in chain:
        if event.get("eventCode") == "agent_task_created":
            event.update({
                "has_expert": True,
                "expert_id": expert_id,
                "expert_name": display_name,
                "expert_industry_id": "",
            })
    chain.append({
        "eventCode": "expert_actual_use", "id": expert_id, "name": display_name,
        "expertTitle": expert_title, "type": "", "expertType": expert_type,
        "source": "builtin", "version": version, "cost": 0,
        "characterCount": len(prompt), "mode": "LOCAL",
        "conversationId": conversation_id, "requestId": request_id,
        "messageId": message_id, "requestModelId": TASK_EVENT_MODEL,
        "requestModelName": TASK_EVENT_MODEL,
    })
    return summon + chain


def _skill_task_events(skill, conversation_id, request_id, message_id):
    events = _chat_event_chain(
        "", conversation_id, request_id, message_id=message_id, model=TASK_EVENT_MODEL)
    for event in events:
        if event.get("eventCode") == "chat_message_response":
            event["finishReason"] = "tool_calls"
    events.append({
        "eventCode": "skill_info", "id": skill.get("slug") or skill["name"],
        "skillId": skill["id"],
        "skillVersion": "1.0.0", "toolStatus": "success", "fileCount": 0,
        "source": "workbuddy-desktop", "conversationId": conversation_id,
        "requestId": request_id, "messageId": message_id,
        "requestModelId": TASK_EVENT_MODEL, "requestModelName": TASK_EVENT_MODEL,
        "traceId": request_id,
    })
    return events


def _expert_id_from_task_row(row):
    jump_url = str((row or {}).get("jump_url") or "")
    match = re.search(r"(?:expertId|expert_id|id)=(ex_[A-Za-z0-9]+)", jump_url)
    return match.group(1) if match else ""


def perform_growth_task_action(token, uid, task_code, row=None):
    """执行真实动作并上报对应判据；返回 (动作成功, 说明)。"""
    request_id = _new_task_request_id()
    if task_code == "first_chat":
        ok, note, data, model = web_task_conversation_session(
            token, uid, prompt="Hello, please reply OK.")
        if not ok:
            return False, note
        conversation_id = str(data["id"])
        message_id = str(data["messageId"])
        events = _chat_event_chain(
            "", conversation_id, message_id, message_id=message_id, model=model)
        report_ok, report_note = report_growth_events(token, uid, events)
        return report_ok, "真实对话已完成；%s" % report_note

    if task_code == "template_used":
        template, error = fetch_task_scene(token, uid)
        if not template:
            return False, error
        ok, note, data, _model = web_task_conversation_session(
            token, uid, prompt="Use the %s template and reply OK." % template["name"])
        if not ok:
            return False, note
        conversation_id = str(data["id"])
        message_id = str(data["messageId"])
        events = _template_task_events(template, conversation_id, message_id)
        report_ok, report_note = report_growth_events(token, uid, events)
        return report_ok, "模板=%s；%s" % (template["name"], report_note)

    if task_code == "expert_summoned":
        expected_expert_id = _expert_id_from_task_row(row)
        expert, error = fetch_task_expert(token, uid, expected_id=expected_expert_id)
        if not expert:
            return False, error
        prompt = "Hello, please introduce yourself and reply OK."
        metadata = _growth_metadata(
            [{
                "eventCode": "ExpertActualUse", "id": expert["id"],
                "extra": {
                    "name": expert["name"],
                    "expertTitle": expert.get("profession") or expert["name"],
                    "expertType": expert.get("expertType") or "agent",
                    "source": "builtin", "version": expert.get("version") or "1.0.0",
                    "cost": 0, "characterCount": len(prompt),
                },
                "expertType": expert.get("expertType") or "agent",
            }],
            request_id,
            expert=expert,
            prompt=prompt,
            uid=uid,
        )
        ok, note, data, _model = web_task_conversation_session(
            token, uid, prompt=prompt, metadata=metadata)
        if not ok:
            return False, note
        conversation_id = str(data["id"])
        message_id = str(data["messageId"])
        events = _expert_task_events(
            expert, conversation_id, message_id, message_id, prompt)
        report_ok, report_note = report_growth_events(token, uid, events)
        return report_ok, "专家=%s；%s" % (expert["name"], report_note)

    if task_code == "skill_installed":
        skill, error = fetch_task_skill(token, uid)
        if not skill:
            return False, error
        install_ok, install_note = install_task_skill(token, uid, skill)
        if not install_ok:
            return False, install_note
        prompt = "Please use the %s skill and reply OK." % skill["name"]
        ok, note, data, _model = web_task_conversation_session(
            token, uid, prompt=prompt)
        if not ok:
            return False, note
        conversation_id = str(data["id"])
        message_id = str(data["messageId"])
        events = _skill_task_events(skill, conversation_id, message_id, message_id)
        report_ok, report_note = report_growth_events(token, uid, events)
        return report_ok, "%s；技能=%s；%s" % (
            install_note, skill["name"], report_note)

    return False, "该任务没有自动动作"


def _wait_growth_task(token, uid, task_code, attempts=3, gap=3):
    row = {}
    for index in range(max(1, attempts)):
        if index:
            time.sleep(gap)
        rows, _errors = fetch_growth_tasks(token, uid)
        row = rows.get(task_code) or {}
        if growth_task_is_ready(row) or growth_task_is_claimed(row):
            return row
    return row


def run_growth_tasks(token, uid, log_fn=log, allow_web=True):
    """执行图片中的 5 个等级任务，返回可加入推送的结果列表。"""
    rows, errors = fetch_growth_tasks(token, uid)
    if errors:
        log_fn("   ⚠️等级任务列表部分失败: %s" % "；".join(errors))
    if not rows:
        log_fn("   ⏭️等级任务: 当前账号未下发或列表不可用")
        return []

    results = []
    for task_code in TARGET_GROWTH_TASKS:
        label = GROWTH_TASK_LABELS[task_code]
        row = rows.get(task_code)
        if not row:
            log_fn("   ⏭️%s: 未下发" % label)
            continue
        if growth_task_is_claimed(row):
            log_fn("   ✅%s: 已领取" % label)
            results.append((task_code, "已领取"))
            continue
        if row.get("_source") == "mp":
            log_fn("   ⏭️%s: 仅小程序口径下发，当前不伪造 MP 事件" % label)
            results.append((task_code, "仅 MP 下发，未执行"))
            continue
        if task_code in CLIENT_ONLY_GROWTH_TASKS:
            status = growth_task_status(row)
            if status == "completed":
                note = "服务端已达标，需官方客户端确认绑定"
            else:
                note = "需客户端绑定微信"
            log_fn("   ⚠️%s: %s，本轮不伪造完成" % (label, note))
            results.append((task_code, note))
            continue
        if growth_task_is_locked(row):
            log_fn("   ⏭️%s: 未解锁（%s）" % (
                label, str(row.get("valid_start") or row.get("unlock_at") or "见任务页")[:10]))
            results.append((task_code, "未解锁"))
            continue
        if growth_task_is_ready(row):
            claim_ok, claim_note = claim_growth_task(token, uid, task_code)
            log_fn("   %s%s: %s" % ("🎁" if claim_ok else "⚠️", label, claim_note))
            results.append((task_code, claim_note))
            continue
        if not allow_web:
            log_fn("   ⏭️%s: 已跳过（--no-keepalive 禁止网页对话）" % label)
            results.append((task_code, "已跳过（--no-keepalive）"))
            continue
        if (row.get("_source") == "desktop"
                and growth_task_status(row) in ("not_accepted", "pending", "")):
            accept_ok, accept_note = accept_growth_task(token, uid, task_code)
            log_fn("   %s%s: %s" % ("✅" if accept_ok else "⚠️", label, accept_note))
            if not accept_ok:
                results.append((task_code, accept_note))
                continue
        action_ok, action_note = perform_growth_task_action(
            token, uid, task_code, row=row)
        log_fn("   %s%s: %s" % ("✅" if action_ok else "⚠️", label, action_note))
        if not action_ok:
            results.append((task_code, action_note))
            continue
        row = _wait_growth_task(token, uid, task_code)
        if growth_task_is_claimed(row):
            log_fn("   ✅%s: 服务端已确认完成并领取" % label)
            results.append((task_code, "已领取"))
            continue
        if growth_task_is_ready(row):
            claim_ok, claim_note = claim_growth_task(token, uid, task_code)
            log_fn("   %s%s: %s" % ("🎁" if claim_ok else "⚠️", label, claim_note))
            results.append((task_code, claim_note))
            continue
        state = growth_task_progress_text(row)
        log_fn("   ⚠️%s: 动作已执行但服务端状态仍为 %s，不冒领" % (label, state))
        results.append((task_code, "动作已执行，状态未变(%s)" % state))
    return results


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


def notify(text, title="WorkBuddy AI 每日活跃与等级任务"):
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
    global ONLY, NO_KEEPALIVE, REPORT_ONLY, NO_TASKS
    ONLY = None
    NO_KEEPALIVE = False
    REPORT_ONLY = False
    NO_TASKS = False
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(HELP_TEXT, end="")
        return 0
    if "--no-keepalive" in args:
        NO_KEEPALIVE = True
    if "--report-only" in args:
        REPORT_ONLY = True
    if "--no-tasks" in args:
        NO_TASKS = True
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
    log("║ 🤖 WorkBuddy AI 国际版 每日活跃与等级任务 ║" if not REPORT_ONLY else
        "║ 🤖 WorkBuddy AI 国际版 report-only       ║")
    log("╚══════════════════════════════════════════╝")
    log("👥 账号数: %d" % len(accounts))
    if REPORT_ONLY:
        log("🧪 report-only：业务动作仅执行 /v2/report 活跃上报；不探测/领取每日奖励，"
            "不执行任务/奖励领取、保活或网页会话（仍保留只读风控预检与必要令牌续期）")
    elif NO_TASKS:
        log("⏭️ --no-tasks：跳过 first_chat / skill_installed / wechat_linked / "
            "expert_summoned / template_used 五个等级任务")

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
            task_results = []
            if not NO_TASKS:
                task_results = run_growth_tasks(
                    account["token"], account["uid"], log,
                    allow_web=not NO_KEEPALIVE)
            if task_results:
                task_text = "；".join(
                    "%s=%s" % (GROWTH_TASK_LABELS.get(code, code), result)
                    for code, result in task_results
                )
            else:
                task_text = "未执行或未下发"
            lines.append("账号%d %s：%s；活跃上报%s；保活%s；网页会话%s" % (
                index, account["note"], message,
                ("成功（%s）" % report_note) if report_ok else ("未成功（%s）" % report_note),
                ("成功（%s）" % keep_note) if keep_ok else ("未成功（%s）" % keep_note),
                ("成功（%s）" % web_note) if web_ok else ("未成功（%s）" % web_note))
                + "；等级任务：" + task_text)
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

    summary_title = ("🤖 WorkBuddy AI 国际版 report-only" if REPORT_ONLY
                     else "🤖 WorkBuddy AI 国际版每日活跃与等级任务")
    summary = summary_title + "\n" + "\n".join(lines) + "\n🕐 " + time.strftime("%Y-%m-%d %H:%M")
    log(summary)
    if os.getenv("NO_NOTIFY", "").strip() != "1" and lines:
        notify(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
