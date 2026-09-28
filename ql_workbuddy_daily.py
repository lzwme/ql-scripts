#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@source:  https://gh-proxy.org/github.com/L0NE-6/WorkBuddy-Daily/raw/refs/heads/main/workbuddy_daily.py

cron: 0 7,12 * * *
new Env('WorkBuddy每日签到')

🌱 WorkBuddy Daily - 全能签到脚本 v2.5
════════════════════════════════════════════════════════════════

📌 这是什么
   一个脚本搞定 WorkBuddy 全部自动化：Token 自动续期、积分/用量查询、
   18 项成长任务、8 项互动玩法、开学季活动 + 大转盘、小程序成长任务、
   自动领奖，全部无人值守。

✨ 特性
   🔐 Token 永续     只配一个刷新令牌变量，脚本自动续期（90 天滚动，永不过期）
   ✅ 成长任务       18 项云端/桌面全覆盖 + 轻量云专家（仅公益专家需真实捐款）
   🏫 开学季活动     分享/对话/桌面对话/专家 + 幸运大转盘（含瑞幸/KFC/酷狗实物券）
                     ※ 以服务端 in_period 判定活动期，非进行期自动跳过（不会误报失败）
   📱 小程序任务     Tasks_1~7 链式任务（均已到账；每日零点解锁一环，日志给出解锁日期）
                     校园日随开学季结束已从列表撤下（奖励此前已入账）
   🎮 8 项互动玩法   抽奖、盲盒、Buddy、派猫猫旅行、连签兑换、补签卡、礼包补偿、徽章
   💰 三类查询       积分套餐（剩余/总量/已用）、用量统计、成长数据（等级/连签/能量）
   🎁 自动领奖       扫描全部已完成任务自动领取；completed 未领的自动补领
   📢 三渠道推送     PushPlus（微信）+ Bark（iOS）+ 企业微信机器人，可同时配置
   🧩 幂等安全       重复运行只补缺口，不会重复领取或重复操作
   🔄 API 重试       网络/5xx 自动指数退避重试，写动作间隔可调（--gap）
   🔗 稳定指纹       每账号 md5 派生固定 machineId，桌面/web/小程序三域对齐官方埋点
   🐧 青龙友好       非 Windows 走指纹上报，纯 API 直接跑

🚀 使用方法（青龙面板三步）
   1. 上传脚本     workbuddy_daily.py
   2. 设置变量     WORKBUDDY_REFRESH_TOKEN = 每行一个 "手机号:AT:RT"（多账号换行分隔）
   3. 定时任务     0 7,12 * * *    日常全流程
                  30 23 * * *     夜猫子活动窗口（23:00-08:00，必须单独排程）

⌨️ 命令行参数
   python workbuddy_daily.py               全流程：续期 → 查询 → 任务 → 开学季 → 领奖
   python workbuddy_daily.py --refresh     仅刷新所有账号 Token
   python workbuddy_daily.py --query       仅查询积分/用量/成长
   python workbuddy_daily.py --no-desktop  跳过桌面任务（非 Windows 默认走指纹上报）
   python workbuddy_daily.py --no-school   跳过开学季活动
   python workbuddy_daily.py --school-only 只跑开学季活动（不做成长中心任务）
   python workbuddy_daily.py --only 3      只跑第 3 个账号
   python workbuddy_daily.py --gap 2.0     写动作间隔秒数（默认 1.5，最低 1.0）

🔑 环境变量
   WORKBUDDY_REFRESH_TOKEN   【必填】多账号刷新令牌，换行分隔
   PUSHPLUS_TOKEN            【可选】PushPlus 推送（微信）
   BARK_URL                  【可选】Bark 推送（iOS），如 https://api.day.app/xxxxxxxx
   WECOM_WEBHOOK             【可选】企业微信群机器人（完整 URL 或仅 key）

获取 WORKBUDDY_REFRESH_TOKEN 变量值（首次必看）
   第一步：在电脑上安装并登录 WorkBuddy 桌面端
   第二步：下载如下脚本至本地任意目录
        wget https://gh-proxy.org/github.com/lzwme/ql-scripts/raw/refs/heads/main/scripts/workbuddy_auth_reader.py
   第三步：从终端进入该目录，执行 python3 workbuddy_auth_reader.py，若一切正常，最后一行会输出以 `WORKBUDDY_REFRESH_TOKEN=` 开头的信息，其格式为 `手机号:AT:RT` 复制它

    多个账号就写多行。示例（1个账号写一行，换行分隔）：
      1XXXXXXXXXX:eyJhbGciOiJSUzI1NiIs...很长...:eyJhbGciOiJIUzUxMiIs...也很长...
      1XXXXXXXXXX:eyJhbGciOiJSUzI1NiIs...:eyJhbGciOiJIUzUxMiIs...

   ⚠️ 注意：AT 和 RT 之间用英文冒号 : 分隔，等号后面的引号不要带
   ⚠️ 顺序不能反（手机号:AT:RT），且要取 WorkBuddy 自己的文件（目录下可能还有别的应用）
   ⚠️ RT 是你唯一的续期凭据，泄露了别人就能操作你的账号

📦 任务清单
   ☁️ 成长中心任务（18 项，云端 + 桌面）
      每日签到 · 设计创意模式 · 探索优秀灵感 · 桌面端对话 · 尝鲜热门技能
      体验资料库 · 腾讯轻量云专家 · 和平精英主题 · 发现应用 · 企鹅教师助手
      GLM-5.2模型对话 · 和AI聊天5次 · 夜猫子活动 · 召唤3次专家团 · 召唤5次专家
      使用5个模板 · 设置自动化任务 · 领取Buddy
      ❌ 公益专家（需真实捐款，脚本不做）
   🏫 开学季活动（4 项 + 大转盘）
      ※ 活动期自适应：非进行期自动跳过；2026 开学季已于 9 月下旬结束
      分享活动给好友 · 与AI对话3次 · 桌面端对话1次 · 召唤开学季专家
      ❌ 学生认证（需微信实名，人工环节）
      🎰 幸运大转盘：抽到余额为 0（积分 6/66 + 瑞幸/KFC/酷狗实物券）
   📱 小程序成长任务（8 项，需 X-Client-Platform: miniprogram 头）
      Sequential_Tasks_1 完成 1 次对话（+100c+5e）
      Sequential_Tasks_2 选中专家并完成对话（+200c+5e）
      Sequential_Tasks_3 完成 5 次对话（+300c+5e）
      Sequential_Tasks_4 创建 1 个定时任务（+100c+5e）
      Sequential_Tasks_5 使用 1 次 GLM5.2（+100c+5e）
      Sequential_Tasks_6 完成 10 次对话
      Sequential_Tasks_7 体验灵感功能
      school_season 校园日（+100c+5e，开学季结束已撤下）
      ※ Tasks_1~7 为链式任务，完成一环后次日零点解锁下一环（脚本自动推进，日志给出解锁日期）
   🎮 互动玩法（8 项）
      抽奖 · 盲盒 · Buddy信息 · 派猫猫旅行 · 连签兑换 · 补签卡 · 礼包补偿 · 徽章

⚙️ 特别之处
   · 续期节奏：距上次刷新 >10 天 或 AT 7 天内过期，自动刷新（离线会话 30 天失效）
   · RT 轮换：每次刷新都会换发新令牌并立即保存，形成永续循环
   · 桌面任务：Windows 走真实桌面换血；非 Windows 自动降级为指纹上报（无需真实桌面端）
   · 夜猫子：官方规则为「每日 1 次 × 累计 3 天」，有响应即停，不空跑
   · accept 校验：解析接口逐任务状态 + 回读验证，未落账的自动逐个重试
   · 前置依赖：accept 报 prerequisite not met 时先补跑前置任务（如先领养首只 Buddy）再重试
   · 真实会话 id：专家/技能任务的 requestId/messageId 取自真实对话的服务端消息 id（cmb- 形态）
   · 真实场景表：模板任务取服务端 /console/as/support/scenes 的 id（拉不到回落内置表）
   · 签到读数：签到后读 /billing/meter/checkin-activity-status（连签天数/累计积分/连签奖励日）
     并做活动到期预警：距 end_time ≤7 天或活动已关闭时，日志给出 ⚠️ 提示
   · mp 定时任务：Sequential_Tasks_4 用官方 mp 指纹形状（mode=CLOUD、无 rrule），失败回落桌面域
   · 画布与灵感：真实对话 + 桌面链（wbx_design_canvas_* / playbook_cta_click），失败回落 web 裸事件
   · 主题目录：和平精英主题取 /v2/operation-platform/appearance/resources 真 resource_key + meta
   · 备用口径：抽奖的 chances 支持 lottery/summary、兑换状态支持 redeem/summary 补位
   · 凭据失效隔离：AT/RT 过期或格式错只跳过该账号并给出排障提示，不再整轮崩溃
   · 凭据体检：续期前本地看 RT/AT 结构与签发域（typ=Offline / codebuddy.cn realm），
     把 12153 token format error 提前翻译成“粘反了 / 粘错了文件 / 截断了”
   · 微信关注任务：需真人扫码关注满 24 小时，脚本识别并提示，不自动完成
   · 数据文件：wb_refresh_tokens.json 自动生成与维护，无需手动管理
   · 新增账号：变量值末尾追加一行 "手机号:AT:RT" 即可，下次运行自动并入

📄 依赖：requests（pip3 install requests）

🔒 隐私说明
   脚本不含任何账号、手机号、Token 或设备信息，所有凭据均由环境变量注入。
"""
import sys, os, re, json, time, uuid, base64, glob, hashlib, glob as _glob, shutil, subprocess, threading, queue
import requests


class TransientError(RuntimeError):
    """网络/5xx 可重试错误。"""

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass

BASE = "https://www.workbuddy.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) WorkBuddy/5.5.4 Chrome/138.0.7204.251 Electron/37.10.3 Safari/537.36"

# ---------- 任务代码 → 中文名映射 ----------
TASK_NAME_CN = {
    "create_canvas": "设计创意模式",
    "playbook_prompt": "探索优秀灵感",
    "RichMeow_Chat": "桌面端对话",
    "Library_read": "体验资料库",
    "Expert_lighthouse": "腾讯轻量云专家",
    "Expert_Philanthropy": "公益专家",
    "Hp_Appearance": "和平精英主题",
    "Buddy_App": "发现应用",
    "Buddy_App_QQ": "企鹅教师助手",
    "Model_chat_GLM5.2": "GLM-5.2模型对话",
    "black_cat": "夜猫子活动",
    "Expert_team_use_3": "召唤3次专家团",
    "first_buddy": "领取Buddy",
    "chat_5": "和AI聊天5次",
    "skill_1": "尝鲜热门技能",
    "expert_5": "召唤5次专家",
    "template_5": "使用5个模板",
    "automation_1": "设置自动化任务",
    "workstation_expert": "工作台搭建师",
    "wb_wechat_oa_subscribe_task": "关注公众号",
    "Sequential_Tasks_1": "小程序对话",
    "Sequential_Tasks_2": "小程序专家对话",
    "Sequential_Tasks_3": "小程序对话5次",
    "Sequential_Tasks_4": "小程序定时任务",
    "Sequential_Tasks_5": "小程序GLM5.2",
    "Sequential_Tasks_6": "小程序对话10次",
    "Sequential_Tasks_7": "小程序灵感功能",
    "school_season": "校园日活动",
}

def task_cn(code):
    return TASK_NAME_CN.get(code, code)


QQ_TPL = "cb_y5Dy46tPQGGWtueMxXbe"          # 企鹅教师助手模板


# ---------- 专家市场数据（内联，无需外部模块） ----------
EXPERT_MARKETPLACE_URL = "https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/expert_center.json"
_expert_cache = None


def _extract_name(val):
    if isinstance(val, dict):
        return val.get("zh", val.get("en", str(val)))
    return str(val)


def fetch_expert_marketplace():
    """拉取专家市场配置（带缓存）"""
    global _expert_cache
    if _expert_cache is not None:
        return _expert_cache
    try:
        s = requests.Session()
        s.trust_env = False
        s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        r = s.get(EXPERT_MARKETPLACE_URL, timeout=15, verify=False)
        if r.status_code == 200:
            _expert_cache = r.json()
            return _expert_cache
    except Exception:
        pass
    return None


def get_team_experts(count=5):
    """专家团列表"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    team = []
    for e in data.get("experts", []):
        meta = e.get("_meta", {})
        if meta.get("expertType") == "team" or e.get("expertType") == "team":
            team.append({"id": e["id"], "name": _extract_name(e.get("displayName", e.get("name", {}))),
                         "industryId": meta.get("industryId", e.get("industryId", "")),
                         "profession": _extract_name(e.get("profession", "")),
                         "defaultInitPrompt": _extract_name(e.get("defaultInitPrompt", ""))})
    return team[:count]


def get_normal_experts(count=10):
    """普通专家列表"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    normal = []
    for e in data.get("experts", []):
        meta = e.get("_meta", {})
        if meta.get("expertType", e.get("expertType", "")) == "agent":
            normal.append({"id": e["id"], "name": _extract_name(e.get("displayName", e.get("name", {}))),
                           "industryId": meta.get("industryId", e.get("industryId", "")),
                           "profession": _extract_name(e.get("profession", "")),
                           "defaultInitPrompt": _extract_name(e.get("defaultInitPrompt", ""))})
    return normal[:count]


def get_template_scenes(count=5):
    """模板场景列表（失败时用内置兜底）"""
    data = fetch_expert_marketplace()
    fallback = [{"id": "01-ProductDesign", "name": "产品设计"}, {"id": "02-Marketing", "name": "营销文案"},
                {"id": "03-DataAnalysis", "name": "数据分析"}, {"id": "04-CodeReview", "name": "代码审查"},
                {"id": "05-Report", "name": "报告撰写"}]
    if not data:
        return fallback[:count]
    scenes = [{"id": c["id"], "name": _extract_name(c.get("name", {}))} for c in data.get("categories", [])[:count]]
    return scenes or fallback[:count]

THEME_KEY = "theme-tkmw7j"                   # 和平精英激战金秋
LIB_DOC_URL = "https://www.workbuddy.cn/space/d/o0KWYeynteVv06UnAZqIFm"
SKILL_NAME = "algorithmic-trading"
SKILL_FALLBACK = ("skill_2097350077599879168", "润泽小馆·日报撰写")   # 上游实测可点亮的技能 id
INFO_BACKUP = os.path.join(os.path.expanduser("~"), "AppData", "Local", "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info")

# ---------- 账号 ----------
# ---------- Token 自动续期（内联实现，无需外部文件） ----------
REFRESH_URL = "https://copilot.tencent.com/v2/plugin/auth/token/refresh"
REFRESH_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wb_refresh_tokens.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WORKBUDDY_ACCESS_TOKEN.txt")



def _parse_env_tokens(raw):
    """解析环境变量：支持换行或 @ 分隔；每项格式 "手机号:AT:RT" 或 "手机号:RT" 或 纯token"""
    items = []
    if not raw:
        return items
    for line in raw.replace("@", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        # maxsplit=2：RT 里若含冒号也不会被截断（旧写法取 parts[2] 会丢尾巴）
        parts = line.split(":", 2)
        if len(parts) >= 3 and not parts[0].startswith("eyJ"):
            items.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
        elif len(parts) == 2 and not parts[0].startswith("eyJ"):
            items.append((parts[0].strip(), "", parts[1].strip()))
        else:
            items.append(("", line, ""))
    return items


def _bootstrap_store():
    """自举：json不存在时从环境变量 WORKBUDDY_REFRESH_TOKEN 生成（唯一变量）"""
    if os.path.exists(REFRESH_STORE):
        try:
            if json.load(open(REFRESH_STORE, encoding="utf-8")):
                return
        except Exception:
            pass
    store = {}
    for user, at, rt in _parse_env_tokens(os.environ.get("WORKBUDDY_REFRESH_TOKEN", "")):
        if not rt:
            continue
        key = user or (jwt_user(at) if at else "acct-%d" % (len(store) + 1))
        store[key] = {"refresh_token": rt, "access_token": at}
    if store:
        json.dump(store, open(REFRESH_STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("📝 已自动生成 wb_refresh_tokens.json（%d 个账号）" % len(store))


_bootstrap_store()


def _jwt_payload_local(tok):
    """本地解 JWT payload（不验签，仅用于体检与取名）。失败返回 {}。"""
    try:
        seg = tok.split(".")
        if len(seg) != 3:
            return {}
        s = seg[1]; s += "=" * (4 - len(s) % 4)
        d = json.loads(base64.urlsafe_b64decode(s))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _token_sanity(rt, at):
    """凭据本地体检：把 RT/AT 的结构问题翻译成可执行的排障提示（不联网）。

    合法 CN WorkBuddy 凭据（实测 2026-09-28）：
      · AT：RS256 JWT，typ=Bearer，iss=https://www.codebuddy.cn/auth/realms/copilot
      · RT：HS512 JWT，typ=Offline，iss/aud 同为上述 realm，azp=console
    服务端对不合规凭据只回一句 12153 ... token format error，这里提前说清楚是哪一种。
    """
    tips = []
    for name, tok in (("RT", rt), ("AT", at)):
        tok = (tok or "").strip()
        if not tok:
            continue
        if not tok.startswith("eyJ") or tok.count(".") != 2:
            tips.append("%s 不是 eyJ 开头的三段式 JWT（长度 %d）——被截断、带了引号/空格，或粘错了字段" % (name, len(tok)))
            continue
        pl = _jwt_payload_local(tok)
        typ = str(pl.get("typ", ""))
        iss = str(pl.get("iss", ""))
        if name == "RT" and typ and typ != "Offline":
            tips.append("RT 的 typ=%s（应为 Offline）——%s" % (
                typ, "很可能把 AT 粘到了 RT 位置，正确顺序是 手机号:AT:RT" if typ == "Bearer" else "字段粘错了"))
        if name == "AT" and typ and typ != "Bearer":
            tips.append("AT 的 typ=%s（应为 Bearer）——AT/RT 可能写反了" % typ)
        if iss and ("codebuddy.cn" not in iss):
            tips.append("%s 的签发域是 %s，不是 CN 站（www.codebuddy.cn/auth/realms/copilot）——国际版/其他应用的 token 在 CN 刷不了" % (name, iss[:70]))
    return tips


def jwt_user(tok):
    try:
        pay = tok.split(".")[1]; pay += "=" * (4 - len(pay) % 4)
        return json.loads(base64.urlsafe_b64decode(pay)).get("preferred_username", "?")
    except Exception:
        return "?"


def refresh_one(rt):
    """刷新单个RT，返回 (新AT, 新RT) 或 (None, 错误信息)"""
    s = requests.Session(); s.trust_env = False
    r = s.post(REFRESH_URL, json={}, timeout=20, verify=False,
               headers={"X-Refresh-Token": rt, "X-Auth-Refresh-Source": "plugin",
                        "Content-Type": "application/json"})
    d = r.json()
    inner = d.get("data") or {}
    if d.get("code") == 0 and inner.get("accessToken"):
        return inner["accessToken"], inner.get("refreshToken") or rt
    return None, str(d.get("msg", ""))[:120]


def refresh_all(verbose=True):
    """刷新 wb_refresh_tokens.json 中所有账号，重建 token 文件。返回 {user: at}"""
    store = {}
    if os.path.exists(REFRESH_STORE):
        try:
            store = json.load(open(REFRESH_STORE, encoding="utf-8"))
        except Exception:
            store = {}
    updated = {}
    for user, ent in list(store.items()):
        rt = ent.get("refresh_token")
        if not rt:
            continue
        try:
            at, nrt = refresh_one(rt)
        except Exception as e:
            at, nrt = None, str(e)[:60]
        if at:
            real_user = jwt_user(at)
            if real_user and real_user != "?" and real_user != user:
                store.pop(user, None)
                user = real_user
            store[user] = {"refresh_token": nrt, "access_token": at,
                           "updated": time.strftime("%Y-%m-%d %H:%M")}
            updated[user] = at
            if verbose:
                print("   🔄 %s token已续期" % user)
        elif verbose:
            print("   ⚠️ %s 续期失败: %s" % (user, nrt))
        time.sleep(1)
    if updated:
        json.dump(store, open(REFRESH_STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        _rebuild_token_file(store)
    return updated


def _rebuild_token_file(store):
    """按现有 token 文件的顺序替换为新 AT；文件不存在则从 store 全新构建"""
    toks, seen = [], set()
    src = ""
    if os.path.exists(TOKEN_FILE):
        src = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if src:
        for t in src.split("@"):
            t = t.strip()
            if not t:
                continue
            u = jwt_user(t)
            if u in seen:
                continue
            seen.add(u)
            toks.append(store.get(u, {}).get("access_token", t))
    else:
        # 全新构建：直接用 store 里所有有效 AT
        for u, ent in store.items():
            at = ent.get("access_token", "")
            if at and u not in seen:
                seen.add(u)
                toks.append(at)
    if toks:
        open(TOKEN_FILE, "w", encoding="utf-8").write("@".join(toks))


def auto_refresh():
    """启动前自动续期：距上次刷新超10天(或AT快过期)的账号自动刷新"""
    # 环境变量里的新RT合并进 store（支持随时用变量补充账号）
    env_rt = os.environ.get("WORKBUDDY_REFRESH_TOKEN", "").strip()
    if env_rt:
        try:
            store = json.load(open(REFRESH_STORE, encoding="utf-8")) if os.path.exists(REFRESH_STORE) else {}
        except Exception:
            store = {}
        existing_rt = {v.get("refresh_token") for v in store.values()}
        added = 0
        for user, at, rt in _parse_env_tokens(env_rt):
            if not rt:
                continue
            key = user or (jwt_user(at) if at else "env-%d" % (len(store) + 1))
            if rt not in existing_rt:
                store[key] = {"refresh_token": rt, "access_token": at or store.get(key, {}).get("access_token", "")}
                existing_rt.add(rt)
                added += 1
        if added:
            json.dump(store, open(REFRESH_STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("📝 从 WORKBUDDY_REFRESH_TOKEN 新增 %d 个账号的刷新令牌" % added)
    if not os.path.exists(REFRESH_STORE):
        return
    try:
        store = json.load(open(REFRESH_STORE, encoding="utf-8"))
    except Exception:
        return
    now = time.time()
    due = {}
    for user, ent in list(store.items()):
        at = ent.get("access_token", "")
        if not at:
            # 只有RT没有AT（首次自举）：立即刷新
            due[user] = ent
            continue
        try:
            pay = at.split(".")[1]; pay += "=" * (4 - len(pay) % 4)
            exp = json.loads(base64.urlsafe_b64decode(pay)).get("exp", 0)
        except Exception:
            exp = 0
        try:
            lt = time.mktime(time.strptime(ent.get("updated", ""), "%Y-%m-%d %H:%M"))
        except Exception:
            lt = 0
        # 触发条件: 距上次刷新>10天(离线会话30天失效) 或 AT 7天内过期
        if (now - lt > 10 * 86400) or (exp and exp - now < 7 * 86400):
            due[user] = ent
    if not due:
        return
    print("🔑 检查到 %d 个账号需要续期..." % len(due))
    updated = {}
    bad_rt = 0
    for user, ent in due.items():
        tips = _token_sanity(ent.get("refresh_token", ""), ent.get("access_token", ""))
        if tips:
            print("   🩺 %s 凭据体检:" % user)
            for t in tips[:3]:
                print("      · %s" % t)
        try:
            at, nrt = refresh_one(ent.get("refresh_token", ""))
        except Exception:
            at, nrt = None, "err"
        if at:
            store[user] = {"refresh_token": nrt, "access_token": at,
                           "updated": time.strftime("%Y-%m-%d %H:%M")}
            updated[user] = at
            print("   🔄 %s token已自动续期(新有效期90天)" % user)
        else:
            print("   ⚠️ %s 续期失败: %s" % (user, nrt))
            if ("token format error" in str(nrt)) or ("12153" in str(nrt)):
                bad_rt += 1
        time.sleep(1)
    if updated:
        json.dump(store, open(REFRESH_STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        _rebuild_token_file(store)
    if bad_rt:
        print("   💡 RT 被服务端判为非法格式（token format error / 12153），常见原因：")
        print("      1) 变量格式不是 手机号:AT:RT（顺序写反、带了引号/空格/换行也算）")
        print("      2) 粘成了别的应用的 token（例：CodeBuddy CLI，或旧版 workbuddy-desktop.info 里另一套）")
        print("      3) 该 RT 已被其他工具轮换过——最稳：python workbuddy_login.py 重新登录拿最新一行")


def load_accounts():
    auto_refresh()  # 依据 RT 变量/json 续期，并同步 token 文件
    # 续期池优先：与变量实时同步、以手机号为名；本地 token 文件仅作回退
    # (否则新加账号在下次续期前会被旧 token 文件吞掉)
    if os.path.exists(REFRESH_STORE):
        try:
            store = json.load(open(REFRESH_STORE, encoding="utf-8"))
            accs = [{"note": user, "access_token": v.get("access_token", "")}
                    for user, v in store.items()]
            if accs:
                no_at = [a["note"] for a in accs if not a["access_token"]]
                if no_at:
                    print("⚠️ 以下账号无 AT（续期可能失败），仍会尝试执行: %s" % ", ".join(no_at))
                return accs
        except Exception:
            pass
    env = ""
    if os.path.exists(TOKEN_FILE):  # 回退：本地文件(续期后最新)
        env = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if env:
        items = [x.strip() for x in env.replace("@", "\n").splitlines() if x.strip()]
        return [{"note": "账号%d" % (i + 1), "access_token": t}
                for i, t in enumerate(items)]
    print("未找到账号：请设置环境变量 WORKBUDDY_REFRESH_TOKEN（每行 手机号:AT:RT）")
    sys.exit(1)


ACCOUNTS = load_accounts()
ONLY = int(sys.argv[sys.argv.index("--only") + 1]) - 1 if "--only" in sys.argv else None
if ONLY is not None:
    ACCOUNTS = [ACCOUNTS[ONLY]]
WRITE_GAP = 1.5  # 写动作间隔秒数（--gap 可覆盖，最低 1.0）
QUERY_ONLY = "--query" in sys.argv
NO_DESKTOP = "--no-desktop" in sys.argv
NO_SCHOOL = "--no-school" in sys.argv
SCHOOL_ONLY = "--school-only" in sys.argv
if "--gap" in sys.argv:
    try:
        WRITE_GAP = max(1.0, float(sys.argv[sys.argv.index("--gap") + 1]))
    except (ValueError, IndexError):
        pass

# ---------- 基础 ----------
def new_api(tok):
    s = requests.Session(); s.trust_env = False
    _uid = uid_of(tok)
    s.headers.update({"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                      "Accept": "application/json, text/plain, */*", "Origin": BASE,
                      "Referer": BASE + "/profile/growth-center", "User-Agent": UA,
                      "X-User-Id": _uid})
    return s


def api_retry(s, method, url, body=None, retries=3, gap=1.0, **kw):
    """带指数退避重试的 API 请求：网络错误/5xx 自动重试，4xx 不重试。"""
    last_err = None
    for i in range(1, retries + 1):
        try:
            if method == "GET":
                r = s.get(url, timeout=25, verify=False, **kw)
            else:
                r = s.post(url, json=body, timeout=25, verify=False, **kw)
            if 500 <= r.status_code < 600 and i < retries:
                last_err = RuntimeError("http %s" % r.status_code)
                time.sleep(gap * i)
                continue
            return r
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(gap * i)
            continue
    if last_err:
        raise last_err
    return r


def interpret_failure(st, r_json):
    """结构化错误分类：返回 (描述, 是否应跳过该账号)。"""
    code = r_json.get("code") if isinstance(r_json, dict) else None
    msg = str(r_json.get("msg", "") or r_json.get("message", ""))[:120] if isinstance(r_json, dict) else str(r_json)[:80]
    if st == 401 or code in (401, "401", 40100, "40100"):
        return "401/40100 Token 失效或未绑定", True
    if st == 403:
        return "403 禁止访问", True
    if code in (41000, "41000"):
        return "41000 活动未开始或已结束", False
    if code in (40901, "40901"):
        return "40901 任务暂不可领取", False
    return "http=%s code=%s %s" % (st, code, msg), False


def uid_of(tok):
    try:
        return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "==")).get("sub", "")
    except Exception:
        return ""


def nickname_of(tok):
    try:
        return json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "==")).get("nickname", "") or "用户"
    except Exception:
        return "用户"


def prog(s, code):
    try:
        r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=False).json()
        for t in r.get("data", {}).get("tasks", []):
            if t.get("task_code") == code:
                pr = t.get("progress") or {}
                return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    except Exception:
        pass
    return None, None, None


def claim(s, code, log):
    """M15 领奖：chat 域 400 时自动降级 web 域（x-client-platform: web）。"""
    r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={}, timeout=20, verify=False)
    if r.status_code == 400:
        # 降级 web 域
        r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={},
                   timeout=20, verify=False,
                   headers={"Origin": BASE, "Referer": BASE + "/profile/growth-center",
                            "x-client-platform": "web"})
    try:
        d = r.json().get("data", {})
        log("   🎁领奖[%s]: %s" % (code, "已领过" if d.get("already_claimed") else "+%s积分+%s能量" % (d.get("credit"), d.get("energy"))))
    except Exception:
        log("   领奖[%s]: HTTP %s" % (code, r.status_code))


def report(s, uid, nick, events):
    """events: list of dict；自动补全信封"""
    UA_SHORT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 WorkBuddy/5.5.4"
    mid = derive_id(uid, "machine")   # 稳定指纹：同账号每次相同
    out = []
    for e in events:
        env = {"timestamp": int(time.time() * 1000), "reportDelay": 0,
               "userId": uid, "userNickname": nick,
               "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": "5.5.6",
               "machineId": mid, "sessionId": derive_id(uid, "session"),
               "mode": "CLOUD", "userAgent": UA_SHORT, "os": "Win32", "arch": "x64",
               "osVersion": "10.0.26220", "timezone": "Asia/Shanghai",
               "product": "SaaS", "releaseDate": 1789036585355,
               "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
               "extName": "workbuddy-desktop", "extVersion": "5.5.6",
               "cpuCores": 20, "memorySize": 24}
        env.update(e)
        out.append(env)
    try:
        r = s.post(BASE + "/v2/report", json=out, timeout=15, verify=False)
        return r.status_code
    except Exception:
        return 0


def webchat2(s, conv_name, prompt, meta=None, model="glm-5.2"):
    """真实对话：返回 (conversationId, 回复正文, 服务端消息id)。

    服务端消息 id 取 SSE 首块的 "id"（形如 cmb-<32hex>）——上游 panel 实测：专家/技能类
    任务的 requestId / messageId 必须是真实会话的服务端 id，自造 uuid 不计数。
    """
    conv = s.post(BASE + "/console/webchat/conversations", json={"name": conv_name + "-" + str(uuid.uuid4())[:8]},
                  timeout=20, verify=False).json()
    conv_id = conv.get("data", {}).get("conversationId", "")
    payload = {"messages": [{"role": "user", "content": prompt}], "model": model, "stream": True,
               "conversationId": conv_id}
    if meta:
        payload["_meta"] = meta
    headers = dict(s.headers); headers["Accept"] = "text/event-stream"
    txt = ""; srv_mid = ""
    try:
        with s.post(BASE + "/console/chat/completions", json=payload, timeout=90, verify=False,
                    stream=True, headers=headers) as r:
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    d = line[6:]
                    if d.strip() in ("[DONE]", "[完成]", "[✅完成]"):
                        break
                    try:
                        jj = json.loads(d)
                        if not srv_mid and jj.get("id"):
                            srv_mid = str(jj["id"])
                        for c in jj.get("choices", []):
                            cp = c.get("delta", {}).get("content", "")
                            if cp:
                                txt += cp
                    except Exception:
                        pass
    except Exception:
        pass
    return conv_id, txt, srv_mid


def webchat(s, conv_name, prompt, meta=None, model="glm-5.2"):
    """真实对话（兼容包装）：返回 (conversationId, 回复正文)。"""
    conv_id, txt, _ = webchat2(s, conv_name, prompt, meta=meta, model=model)
    return conv_id, txt


def chat_request_events(uid, nick, conv_id, prompt, txt, mode="craft"):
    now = int(time.time() * 1000)
    rid = "cmb-" + str(uuid.uuid4())
    common = {"userId": uid, "userNickname": nick, "ideName": "web-Agents", "ideType": "web-Agents",
              "machineId": derive_id(uid, "machine"), "mode": "CLOUD", "userAgent": UA, "os": "Win32",
              "timezone": "Asia/Shanghai"}
    return [
        {"eventCode": "chat_request_send", "timestamp": now, "reportDelay": 0, **common,
         "mode": mode,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "inputLength": len(prompt), "customAgentName": ""},
        {"eventCode": "chat_request_response", "timestamp": now + 100, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "toolCallCount": 0, "inputToken": max(1, len(prompt) // 4),
         "outputToken": max(1, len(txt) // 4), "totalToken": max(2, (len(prompt) + len(txt)) // 4)},
        {"eventCode": "chat_message_send", "timestamp": now + 50, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "messageId": "cmb-" + str(uuid.uuid4()),
         "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2", "historyCount": 1,
         "isContextTruncated": False, "currentStepCount": 1, "traceId": rid, "rootRequestId": rid,
         "parentConversationId": conv_id, "agentName": "cli", "agentType": "main"}], rid


# ---------- 查询 ----------
def _json_or_empty(r):
    """容错取 JSON：非 JSON 响应（401/403 空体、HTML 错误页）返回 {}，不抛异常。

    背景（issue #12/#13）：AT/RT 失效时上游返回非 JSON，旧代码直接 .json() 会把
    JSONDecodeError 抛出 run_account，整个运行崩掉、后续账号全部丢失。
    """
    try:
        d = r.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def queryCredits(s):
    """积分查询：套餐总量/剩余/已用"""
    try:
        r = s.post(BASE + "/billing/meter/get-user-resource-summary", json={}, timeout=20, verify=False).json()
        pkgs = r.get("data", {}).get("Packages", [])
        paid = r.get("data", {}).get("IsPaidUser")
        out = []
        for i, p in enumerate(pkgs):
            remain = p.get("CycleRemainCapacity", "0")
            total = p.get("CycleTotalCapacity", "0")
            used = p.get("CycleUsedCapacity", "0")
            # 清理小数尾巴
            remain = remain.rstrip("0").rstrip(".") if "." in remain else remain
            used = used.rstrip("0").rstrip(".") if "." in used else used
            total = total.rstrip("0").rstrip(".") if "." in total else total
            pkg_name = "主套餐" if i == 0 else "加量包%d" % i
            out.append("%s剩余%s积分(共%s,已用%s)" % (pkg_name, remain, total, used))
        return ("；".join(out) if out else "暂无套餐"), paid
    except Exception as e:
        return "查询失败:" + str(e)[:40], False


def queryUsage(s):
    """用量查询：资源总数/总用量"""
    try:
        r = s.post(BASE + "/billing/meter/get-user-resource", json={}, timeout=20, verify=False).json()
        resp = r.get("data", {}).get("Response", {}).get("Data", {}) or {}
        return "共%d类资源，本月已使用%s次" % (resp.get("TotalCount", "?"), resp.get("TotalDosage", "?"))
    except Exception:
        return "用量数据延迟2-3小时"


# ---------- 各任务配方（全部经过实测） ----------
def _checkin_activity_warn(sd):
    """签到活动到期预警（只读判断，对齐上游 checkin_activity.go 口径）。

    CN 字段：active / end_time（"YYYY-MM-DD HH:MM:SS" CST）/ activity_name。
    距 end_time 不足 7 天、或活动已关闭时给出提示，避免“活动结束才发现收入断档”。
    """
    import datetime
    name = sd.get("activity_name") or "签到活动"
    if sd.get("active") is False:
        return "⚠️%s已结束" % name
    raw = str(sd.get("end_time") or "")
    if len(raw) < 19:
        return ""
    try:
        end = datetime.datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""
    days = (end - beijing_now().replace(tzinfo=None)).total_seconds() / 86400.0
    if days < 0:
        return "⚠️%s已到期" % name
    if days <= 7:
        # 当日用「今日」，其余直接给日期（天数四舍五入容易歧义）
        when = "今日" if end.date() == beijing_today() else "%d-%d" % (end.month, end.day)
        return "⚠️%s%s结束" % (name, when)
    return ""


def _checkin_tail(s):
    """签到活动读数尾注：连签天数 / 累计积分 / 连签奖励日 / 到期预警（只读，失败返回空串）。

    上游多仓共用口径：POST /v2/billing/meter/checkin-activity-status 返回
    today_checked_in / streak_days / total_credits / is_streak_day / next_streak_day。
    """
    try:
        sd = (s.post(BASE + "/v2/billing/meter/checkin-activity-status", json={}, timeout=20,
                     verify=False).json().get("data") or {})
        parts = []
        if sd.get("streak_days") is not None:
            parts.append("连签%s天" % sd["streak_days"])
        if sd.get("total_credits") is not None:
            parts.append("累计%s" % sd["total_credits"])
        if sd.get("is_streak_day"):
            parts.append("🎉今日为连签奖励日")
        elif sd.get("next_streak_day"):
            parts.append("距下一连签奖励 %s 天" % sd["next_streak_day"])
        warn = _checkin_activity_warn(sd)
        if warn:
            parts.append(warn)
        return "（%s）" % "，".join(parts) if parts else ""
    except Exception:
        return ""


def t_sign(s, uid, nick, log):
    """每日签到 + 签到活动读数（连签天数 / 累计积分 / 连签奖励日）"""
    credit = None; msg = ""
    try:
        d = s.post(BASE + "/v2/billing/meter/daily-checkin", json={}, timeout=20, verify=False).json()
        if d.get("code") in (0, 200):
            credit = (d.get("data") or {}).get("credit")
        msg = (d.get("msg") or "")[:40]
    except Exception:
        msg = "签到请求失败"
    tail = _checkin_tail(s)
    if credit is not None:
        log("   ✅签到成功 +%s积分%s" % (credit, tail))
    else:
        log("   ✅签到: %s%s" % (msg or "今天已签到，请明天再来", tail))


def t_accept_all(s, uid, nick, log):
    """接受全部未接受任务：批量 accept → 解析逐项结果 → 前置依赖补救 → 未落账逐个重试。

    ⚠️ accept 响应是**逐任务**返回状态：
        {"code":0, "data":{"results":[{"task_code":..,"status":"accepted"|"error","message":..}]}}
    顶层 code=0 只代表请求送达，不代表每项都登记成功（实测存在整体 error 的形态）。
    ⚠️ 部分任务带前置条件：message 为 `prerequisite not met: <task_code>`（如 first_buddy
       表示该账号还没有 Buddy 实例），此时先补跑前置任务再重试登记。
    """
    r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=False).json()
    todo = [t.get("task_code") for t in r.get("data", {}).get("tasks", [])
            if isinstance(t, dict) and t.get("accept_status") == "not_accepted"]
    if not todo:
        return
    # ---- 1) 批量接受 + 解析逐项结果 ----
    resp = {}
    bad = []
    try:
        r2 = s.post(BASE + "/v2/activity/growth/tasks/accept",
                    json={"task_codes": todo}, timeout=20, verify=False)
        d2 = r2.json()
        for x in ((d2.get("data") or {}).get("results") or []):
            if isinstance(x, dict) and x.get("task_code"):
                resp[x["task_code"]] = (x.get("status") or "", x.get("message") or "")
        ok = [c for c in todo if resp.get(c, ("", ""))[0] == "accepted"]
        bad = [(c, resp[c][0], resp[c][1]) for c in todo if c in resp and resp[c][0] != "accepted"]
        nolog = [c for c in todo if c not in resp]
        log("   📋批量接受 %d 项 → 成功 %d / 未登记 %d%s" % (
            len(todo), len(ok), len(bad) + len(nolog),
            ("（%d 项无返回）" % len(nolog)) if nolog else ""))
        for c, st, m in bad[:6]:
            log("      ✗ %s: %s %s" % (c, st, m[:70]))
        if len(bad) > 6:
            log("      ...另 %d 项" % (len(bad) - 6))
    except Exception as e:
        log("   📋批量接受异常: %s" % str(e)[:60])
    # ---- 1.5) 前置依赖补救：message 形如 "prerequisite not met: first_buddy (...)" ----
    need = {}
    for c, st, m in bad:
        if "prerequisite not met:" in m:
            pcode = m.split("prerequisite not met:", 1)[1].strip().split(" ")[0].strip("()[]")
            need.setdefault(pcode, []).append(c)
    for pcode, ptasks in need.items():
        log("   🧩 %d 项待前置「%s」满足: %s" % (len(ptasks), pcode, ",".join(ptasks[:6])))
        if pcode == "first_buddy":
            if ensure_first_buddy(s, uid, nick, log):
                log("      ✅ Buddy 已就绪，进入重试登记")
            else:
                log("      ⚠️ 服务端仍无 Buddy 实例：该账号需先在桌面端/小程序完成一次领养引导，本次 %d 项保持未登记" % len(ptasks))
        else:
            log("      ⚠️ 前置「%s」脚本暂无法自动完成" % pcode)
    # ---- 2) 回读验证 + 逐个重试（上游存在 200+OK 但未落账的形态）----
    time.sleep(2)
    pending = [c for c in todo if prog(s, c)[0] in (None, "not_accepted")]
    if not pending:
        log("   ✅ 全部登记生效（%d 项）" % len(todo))
        return
    log("   🔁 %d 项未落账，逐个重试..." % len(pending))
    still = []
    for c in pending:
        if not _accept_with_verify(s, c, log):
            still.append(c)
        time.sleep(1.0)
    if still:
        log("   ⚠️ 仍无法登记 %d 项: %s" % (len(still), ",".join(still[:10])))
        log("      （这些任务的上报可能不被计数，请把本段日志反馈给作者）")
    else:
        log("   ✅ 重试后全部登记生效")


def t_team_3(s, uid, nick, log):
    """召唤3次专家团：真实团队对话+全字段遥测"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    teams = get_team_experts(10)
    if not teams:
        return
    for rd in range(3):
        st, cur, tgt = prog(s, "Expert_team_use_3")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 3):
            break
        team = teams[rd % len(teams)]
        prompt = "你好，请简单介绍一下你们团队能帮我做什么，回答OK即可"
        req_id = str(uuid.uuid4()); msg_id = "cmb-" + str(uuid.uuid4())
        ge = [{"eventCode": "ExpertActualUse", "id": team["id"],
               "extra": {"name": team["name"], "expertTitle": team.get("profession", ""),
                         "type": team.get("industryId", "") or "", "expertType": "team",
                         "source": "builtin", "version": "", "cost": 8, "characterCount": len(prompt),
                         "requestId": req_id, "messageId": msg_id,
                         "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2"},
               "expertType": "team"}]
        meta = {"codebuddy.ai": {"growthEvent": json.dumps(ge, ensure_ascii=False), "promptRequestId": req_id,
                                 "clientSendTime": int(time.time() * 1000), "userId": uid,
                                 "mode": "craft", "model": "glm-5.2", "expertId": team["id"],
                                 "expert": {"id": team["id"], "name": team["name"],
                                            "profession": team.get("profession", ""), "prompt": prompt[:50]},
                                 "tags": ["expert:" + team["id"]]}}
        conv_id, txt = webchat(s, "team", prompt, meta)
        report(s, uid, nick, [{"eventCode": "expert_actual_use", "id": team["id"], "name": team["name"],
                               "expertTitle": team.get("profession", ""), "type": team.get("industryId", "") or "",
                               "expertType": "team", "source": "builtin", "version": "", "cost": 8,
                               "characterCount": len(prompt), "conversationId": conv_id, "requestId": req_id,
                               "messageId": msg_id, "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2"}])
        time.sleep(5)
    st, cur, tgt = prog(s, "Expert_team_use_3")
    log("   召唤3次专家团: %s %s/%s" % (st, cur, tgt))


def t_buddy_apps(s, uid, nick, log):
    """发现应用/企鹅教师助手：desktop_buddy5_sequence + report_desktop_events"""
    for task in ("Buddy_App", "Buddy_App_QQ"):
        st, cur, tgt = prog(s, task)
        if st in ("completed", "claimed"):
            continue
        buddy_id = QQ_TPL if "QQ" in task else "buddy-app-default"
        buddy_name = "企鹅教师助手" if "QQ" in task else "发现应用"
        evs = desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name)
        try:
            report_desktop_events(s, uid, nick, evs)
            log("   %s: buddyapp 五连 OK" % task)
            time.sleep(WRITE_GAP)
        except Exception as e:
            log("   %s: buddyapp failed %s" % (task, str(e)[:60]))
    log("   发现应用/企鹅教师助手: %s / %s" % (prog(s, "Buddy_App")[0], prog(s, "Buddy_App_QQ")[0]))


def _fetch_hp_theme(s):
    """appearance/resources 目录里找和平精英主题 → (resource_key, meta)；失败回落内置表。

    上游多仓共用口径：POST /v2/operation-platform/appearance/resources
    {platform:client, kind:theme, version, lang} → resources[] 含 id/name/vip_level/series。
    """
    try:
        d = s.post(BASE + "/v2/operation-platform/appearance/resources",
                   json={"platform": "client", "kind": "theme", "version": "5.5.6", "lang": "zh-CN"},
                   timeout=20, verify=False).json()
        for x in ((d.get("data") or {}).get("resources") or []):
            nm = x.get("name") or ""
            if "和平精英" in nm or "pubg" in (x.get("id") or "").lower():
                return x.get("id") or THEME_KEY, {"name": nm,
                                                      "vipLevel": x.get("vip_level", "free"),
                                                      "series": x.get("series", "craft")}
    except Exception:
        pass
    return THEME_KEY, {"name": "和平精英激战金秋", "vipLevel": "free", "series": "craft"}


def t_theme(s, uid, nick, log):
    """和平精英主题（Hp_Appearance）：主题目录取真 resource_key + meta，set 后补 skin_apply 事件"""
    st, cur, tgt = prog(s, "Hp_Appearance")
    if st is None:
        log("   和平精英主题: 不在任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   和平精英主题: 已 %s" % st)
        return
    key, meta = _fetch_hp_theme(s)
    r = s.post(BASE + "/portal/user-asset/appearance/set", json={"kind": "theme", "resource_key": key},
               timeout=20, verify=False)
    if r.json().get("code") == 0:
        time.sleep(2)
        report(s, uid, nick, [{"eventCode": "appearance_skin_apply", "action": "apply",
                               "source": "settings_close", "id": key,
                               "vipLevel": meta["vipLevel"], "series": meta["series"],
                               "type": "personal"}])
        time.sleep(6)
    log("   和平精英主题: %s" % prog(s, "Hp_Appearance")[0])


def t_library(s, uid, nick, log):
    st, cur, tgt = prog(s, "Library_read")
    if st is None:
        log("   体验资料库: 不在任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   体验资料库: 已 %s" % st)
        return
    report_web_event(s, uid, nick, "web_element_click", LIB_DOC_URL,
                     "library_doc_intro_click", "WorkBuddy资料库介绍")
    time.sleep(6)
    log("   体验资料库: %s" % prog(s, "Library_read")[0])


def t_chat_n(s, uid, nick, log, code, n, prompts):
    """通用聊天任务: chat_5 / Model_chat_GLM5.2"""
    for i in range(n):
        st, cur, tgt = prog(s, code)
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or n):
            break
        conv_id, txt = webchat(s, code, prompts[i % len(prompts)])
        if txt:
            evs, _ = chat_request_events(uid, nick, conv_id, prompts[i % len(prompts)], txt)
            report(s, uid, nick, evs)
        time.sleep(4)
    st, cur, tgt = prog(s, code)
    log("   %s: %s %s/%s" % (code, st, cur, tgt))


def t_black_cat(s, uid, nick, log):
    st, cur, tgt = prog(s, "black_cat")
    if st in ("completed", "claimed"):
        log("   夜猫子: 已 %s %s/%s" % (st, cur, tgt))
        return
    if not within_night_window():
        # 显式用北京时间：GitHub Actions runner 是 UTC，localtime() 会误导排查
        log("   夜猫子: 仅23:00-08:00计数（CST），当前北京时间%d点，跳过" % beijing_now().hour)
        return
    prompts = ["今天天气怎么样？", "1+1等于几？", "讲个笑话"]
    # 官方规则：每天完成 1 次对话、累计满 3 天（≠ 一晚聊 3 次）。
    # 因此有响应即 break（当日计数已完成），首次失败最多重试 2 次（合计 3 次尝试）。
    for attempt in range(3):
        conv_id, txt = webchat(s, "night", prompts[attempt % len(prompts)])
        if txt:
            evs, _ = chat_request_events(uid, nick, conv_id, "聊天", txt, mode="night")
            report(s, uid, nick, evs)
            log("   夜猫子: 第%d次对话 ✅（回复%d字）——当日计数完成" % (attempt + 1, len(txt)))
            break
        log("   夜猫子: 第%d次对话 ❌（无回复，%s）" % (
            attempt + 1, "将重试" if attempt < 2 else "已达重试上限"))
        time.sleep(5)
    st, cur, tgt = prog(s, "black_cat")
    log("   夜猫子: %s %s/%s（每日1次×累计3天）" % (st, cur, tgt))


def t_expert_5(s, uid, nick, log):
    """召唤5次专家：普通专家遥测"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    experts = get_normal_experts(20)
    st0, cur0, tgt0 = prog(s, "expert_5")
    need = max(0, (tgt0 or 5) - (cur0 or 0))
    if st0 in ("completed", "claimed"):
        need = 0
    for i in range(need):
        st, cur, tgt = prog(s, "expert_5")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 5):
            break
        e = experts[i % len(experts)] if experts else {"id": "expert-" + str(uuid.uuid4())[:8], "name": "Expert", "profession": ""}
        report(s, uid, nick, [
            {"eventCode": "expert_summoned", "id": e["id"], "name": e["name"], "type": "agent",
             "expertTitle": e.get("profession", ""), "expertType": "agent"},
            {"eventCode": "expert_actual_use", "id": e["id"], "name": e["name"], "type": e.get("industryId", "") or "",
             "expertType": "agent", "source": "builtin", "version": "", "cost": 0, "characterCount": 12,
             "conversationId": "conv-" + str(uuid.uuid4()), "requestId": str(uuid.uuid4()),
             "messageId": "msg-" + str(uuid.uuid4()),
             "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash"}])
        time.sleep(3)
    st, cur, tgt = prog(s, "expert_5")
    log("   召唤5次专家: %s %s/%s" % (st, cur, tgt))


def _fetch_scenes(s):
    """GET /console/as/support/scenes → [(id, name)]；拉不到则用内置表（实测线上 id）。"""
    try:
        r = s.get(BASE + "/console/as/support/scenes?locale=zh-CN", timeout=20, verify=False).json()
        out = [(str(x["id"]), x.get("name") or "")
               for x in ((r.get("data") or {}).get("scenes") or []) if x.get("id") is not None]
        if out:
            return out
    except Exception:
        pass
    return [("0", "幻灯片"), ("4", "深度研究"), ("8", "数据分析"), ("16", "设计"), ("20", "日常开发")]


def t_template_5(s, uid, nick, log):
    """使用5个模板：真实场景 id（/console/as/support/scenes）+ 事件组上报

    上游实测：一组 agent_task_created_with_template + template_used 计 1/5 进度；
    template_id 服务端不校验真实性，但用真实场景 id 更稳（旧版写死的 01-ProductDesign
    形态并不存在于线上场景表）。
    """
    scenes = _fetch_scenes(s)[:5]
    for tid, tname in scenes:
        st, cur, tgt = prog(s, "template_5")
        if st in ("completed", "claimed") or (cur or 0) >= (tgt or 5):
            break
        rid = "wb2api-tpl-%d-%s" % (int(time.time() * 1000), tid)
        report(s, uid, nick, [
            {"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
             "requestModelId": "default", "action": tid, "has_template": True, "template_id": tid,
             "template_name": tname, "requestId": rid},
            {"eventCode": "agent_task_created_with_template", "templateId": tid, "templateName": tname,
             "template_id": tid, "mode": "working", "isCustomModel": True, "id": tid, "name": tname,
             "requestId": rid},
            {"eventCode": "template_used", "template_id": tid, "templateId": tid,
             "templateName": tname, "task_mode": "working", "id": tid, "name": tname,
             "source": "growth-center"},
            {"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()), "requestId": rid,
             "id": tid, "name": tname, "type": "other", "promptLength": 30, "isOfficial": 1,
             "source": "growth-center"}])
        time.sleep(2)
    st, cur, tgt = prog(s, "template_5")
    log("   使用5个模板: %s %s/%s" % (st, cur, tgt))


PLAYBOOK_CASE = {"id": "01-ProductDesign", "name": "产品设计", "type": "document"}


def _desktop_run(s, uid, nick, conv_name, prompt, extra_events):
    """真实对话 + 6 连桌面链 + 追加事件（桌面域上报）；返回是否已发出。"""
    try:
        cid, _t, mid = webchat2(s, conv_name, prompt)
        if not (cid and mid):
            return False
        evs = desktop_chat_sequence(uid, nick, cid, mid, mid)
        evs.extend(extra_events(cid, mid))
        report_desktop_events(s, uid, nick, evs)
        time.sleep(3)
        return True
    except Exception:
        return False


def t_canvas_automation(s, uid, nick, log):
    """设计创意模式 + 自动化任务 + 优秀灵感

    画布 / 灵感优先走「真实对话 + 桌面链 + 专属事件组」：上游 task-auto / task_runner 实测形状
    为 wbx_design_canvas_task_create(+open) 与 playbook_cta_click/playbook_prompt_send 挂在真实
    conversationId/requestId 上；未点亮时回落旧的 web 域裸事件。自动化任务用真实 rrule 对象形状。
    """
    if prog(s, "create_canvas")[0] not in ("completed", "claimed"):
        def _canvas_evs(cid, mid):
            return [{"eventCode": "wbx_design_canvas_task_create", "conversationId": cid, "requestId": mid,
                     "source": "summon_keyword", "isCustomModel": False, "name": "", "inputLength": 12,
                     "id": "wbx-canvas-%d" % int(time.time() * 1000), "cost": 0, "isSuccessful": True},
                    {"eventCode": "wbx_design_canvas_open", "conversationId": cid, "requestId": mid,
                     "id": "ardot-file-" + mid[-8:], "source": "summon_keyword", "type": "page",
                     "cost": 13000, "isSuccessful": True}]
        if not _desktop_run(s, uid, nick, "canvas", "帮我在设计创意画布里做一张活动海报", _canvas_evs) \
                or prog(s, "create_canvas")[0] not in ("completed", "claimed"):
            report(s, uid, nick, [{"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
                                   "requestModelId": "default", "task_mode": "design"},
                                  {"eventCode": "wbx_design_canvas_task_create"}])
            time.sleep(3)
    st, cur, tgt = prog(s, "automation_1")
    if st not in ("completed", "claimed"):
        report(s, uid, nick, [{"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
                               "requestModelId": "default", "task_mode": "automation",
                               "isAutomationBackground": True},
                              {"eventCode": "automated_task_create_suc", "action": "create",
                               "name": "每周五自动生成周报", "source": "manually",
                               "modelId": "deepseek-v4-flash", "modelIsThinking": False,
                               "expertId": "", "expertMarketplace": "", "connectorIds": "",
                               "connectorCount": 0, "skills": "", "skillCount": 0,
                               "scheduleType": "recurring", "pushToWeChat": False,
                               "pushToWecomBot": False,
                               "schedule": {"type": "recurring",
                                            "rrule": "FREQ=WEEKLY;BYDAY=FR;BYHOUR=9;BYMINUTE=0"},
                               "prompt": "每周五自动整理本周工作，生成一份周报。"},
                              {"eventCode": "automated_task_execute", "action": "execute"}])
        time.sleep(3)
    if prog(s, "playbook_prompt")[0] not in ("completed", "claimed"):
        def _pb_evs(cid, mid):
            payload = {"id": PLAYBOOK_CASE["id"], "name": PLAYBOOK_CASE["name"],
                       "type": PLAYBOOK_CASE["type"], "categoryId": "", "categoryName": ""}
            ev1 = {"eventCode": "web_element_click", "pageName": "playbook_detail",
                   "elementId": "playbook_ctaClick", "elementName": PLAYBOOK_CASE["name"],
                   "source": "discover"}
            ev2 = dict(payload); ev2.update({"eventCode": "playbook_cta_click", "source": "discover",
                                            "position": 0})
            ev3 = dict(payload); ev3.update({"eventCode": "playbook_prompt_send", "conversationId": cid,
                                            "requestId": mid, "promptLength": 30, "isOfficial": 1,
                                            "skills": "", "skillNames": "", "expertId": "",
                                            "expertName": "", "query": "", "source": "discover",
                                            "ext1": "discover"})
            return [ev1, ev2, ev3]
        if not _desktop_run(s, uid, nick, "playbook", "用这个案例帮我做一个同款", _pb_evs) \
                or prog(s, "playbook_prompt")[0] not in ("completed", "claimed"):
            report(s, uid, nick, [{"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()),
                                   "requestId": str(uuid.uuid4()), "id": PLAYBOOK_CASE["id"],
                                   "name": PLAYBOOK_CASE["name"],
                                   "type": "other", "promptLength": 30, "isOfficial": 1,
                                   "source": "growth-center"}])
            time.sleep(3)
    log("   设计/自动化/灵感: %s / %s / %s" % (prog(s, "create_canvas")[0], prog(s, "automation_1")[0],
                                             prog(s, "playbook_prompt")[0]))


def t_glm52(s, uid, nick, log):
    t_chat_n(s, uid, nick, log, "Model_chat_GLM5.2", 1, ["你好，请介绍一下你自己"])
    t_chat_n(s, uid, nick, log, "chat_5", 5, ["你好", "今天天气怎么样？", "1+1等于几？", "Python是什么？", "推荐一本好书"])




# ---------- 互动玩法（移植自 workbuddy_checkin.py 验证代码） ----------
def t_lottery(s, uid, nick, log):
    """抽奖：查剩余次数并全部抽完"""
    try:
        r = s.get(BASE + "/v2/activity/growth/lottery/chances", timeout=20, verify=False).json()
        cd = r.get("data", {})
        chances = cd.get("balance", cd.get("chances", cd.get("remaining", 0)))
        if not chances:   # 备用口径：/lottery/summary 的 chances
            try:
                sd = s.get(BASE + "/v2/activity/growth/lottery/summary", timeout=20,
                         verify=False).json().get("data") or {}
                chances = sd.get("chances", sd.get("balance", 0))
            except Exception:
                chances = 0
        if not chances or chances <= 0:
            log("   🎰抽奖: 无次数")
            return
        won = []
        for i in range(int(chances)):
            if i > 0:
                time.sleep(2)
            rr = s.post(BASE + "/v2/activity/growth/lottery/draw",
                        json={"client_token": "draw-" + str(uuid.uuid4())}, timeout=20, verify=False).json()
            if rr.get("code") == 0:
                dd = rr.get("data", {})
                prize = str(dd.get("prize_name", dd.get("name", "?")))
                if dd.get("prize_type") == "physical":
                    prize += "（实物奖，需在成长中心填写收货地址）"
                won.append(prize)
            else:
                log("   🎰抽奖失败: %s" % str(rr.get("msg", ""))[:40])
                break
        log("   🎰抽奖: %s" % ("、".join(won) if won else "无结果"))
    except Exception as e:
        log("   🎰抽奖异常: %s" % str(e)[:50])


def t_blindbox(s, uid, nick, log):
    """盲盒：能量足够就开（每次10能量，最多开5次）"""
    try:
        q = s.get(BASE + "/v2/activity/growth/buddy/quota", timeout=20, verify=False).json()
        qd = q.get("data", {})
        affordable = qd.get("affordable", 0)
        if not affordable or affordable <= 0:
            log("   📦盲盒: 能量不足 (%s/10)" % qd.get("balance", "?"))
            return
        n = min(affordable, 5)
        got = []
        for _ in range(n):
            rr = s.post(BASE + "/v2/activity/growth/buddy/open", json={"count": 1}, timeout=20, verify=False).json()
            if rr.get("code") == 0:
                results = rr.get("data", {}).get("results", [])
                if results:
                    it = results[0]
                    ins = it.get("instance", {}); tpl = it.get("template", {})
                    got.append("%s(%s)" % (ins.get("name", tpl.get("name", "?")), ins.get("rarity", tpl.get("rarity", ""))))
            else:
                break
            time.sleep(1.5)
        log("   📦盲盒: %s" % ("、".join(got) if got else "开启失败"))
    except Exception as e:
        log("   📦盲盒异常: %s" % str(e)[:50])


def t_buddy_info(s, uid, nick, log):
    """Buddy 信息"""
    try:
        r = s.get(BASE + "/v2/activity/growth/buddy/info", timeout=20, verify=False).json()
        if r.get("code") == 0:
            b = r.get("data", {}).get("buddy", r.get("data", {}))
            log("   🐱Buddy: %s (%s)%s" % (b.get("name", "?"), b.get("rarity", ""),
                                           ", " + b.get("personality") if b.get("personality") else ""))
    except Exception:
        pass


def t_travel(s, uid, nick, log):
    """派猫猫旅行：到达领礼物 / 旅行中等待 / 空闲出发（幂等状态机）"""
    try:
        vis = s.get(BASE + "/v2/activity/growth/buddy/visible", timeout=20, verify=False).json()
        if vis.get("code") == 0:
            vd = vis.get("data", {})
            if not vd.get("buddy_visible", True) or not vd.get("has_buddy", True):
                log("   🐾旅行: 无Buddy，跳过")
                return
        st = s.get(BASE + "/v2/activity/growth/buddy/travel/status", timeout=20, verify=False).json()
        if not (st.get("code") == 0):
            log("   🐾旅行: 状态获取失败")
            return
        sd = st.get("data", {})
        state = sd.get("state", "idle")
        if state == "arrived":
            rr = s.post(BASE + "/v2/activity/growth/buddy/travel/claim", json={}, timeout=20, verify=False).json()
            if rr.get("code") == 0:
                log("   🐾旅行: 🎉领取礼物 +%s积分" % rr.get("data", {}).get("reward_credit", 0))
            else:
                log("   🐾旅行: 领取失败 %s" % str(rr.get("msg", ""))[:40])
            return
        if state == "traveling":
            remain = max(0, (sd.get("arrive_at", 0) - sd.get("server_now", 0)) // 60)
            log("   🐾旅行: 旅行中，约%s分钟后到达" % remain)
            return
        if sd.get("daily_limit_reached"):
            log("   🐾旅行: 今日次数已用尽")
            return
        cfg = s.get(BASE + "/v2/activity/growth/buddy/travel/config", timeout=20, verify=False).json()
        locs = cfg.get("data", {}).get("locations", [])
        if not locs:
            log("   🐾旅行: 无目的地")
            return
        rr = s.post(BASE + "/v2/activity/growth/buddy/travel/depart",
                    json={"location_id": locs[0].get("id")}, timeout=20, verify=False).json()
        if rr.get("code") == 0:
            remain = max(0, (rr.get("data", {}).get("arrive_at", 0) - rr.get("data", {}).get("server_now", 0)) // 3600)
            log("   🐾旅行: ✅已出发，约%s小时后到达（下次运行自动领取）" % remain)
        else:
            log("   🐾旅行: 出发失败 %s" % str(rr.get("msg", ""))[:40])
    except Exception as e:
        log("   🐾旅行异常: %s" % str(e)[:50])


def t_redeem(s, uid, nick, log, streak_days=None):
    """连登奖励兑换（7d/14d/28d 三档）

    以服务端 `redemption_status` 为准（上游 panel 实测：tier_7d/14d/28d_status =
    available / claimed / locked），已领取的档位不再发请求；本地连签天数仅作兜底。
    每次都必须用新的 client_token——复用旧键会被幂等去重吞掉本次领取。
    """
    tiers = [("7d", 7, "入门"), ("14d", 14, "进阶"), ("28d", 28, "巅峰")]
    status = {}
    try:
        stt = s.get(BASE + "/v2/activity/growth/streak", timeout=20, verify=False).json().get("data") or {}
        rs = stt.get("redemption_status") or {}
        status = {"7d": rs.get("tier_7d_status", ""), "14d": rs.get("tier_14d_status", ""),
                  "28d": rs.get("tier_28d_status", "")}
    except Exception:
        pass
    if not any(status.values()):   # 备用口径：/redeem/summary 的 starter/advanced/legendary_status
        try:
            rm = s.get(BASE + "/v2/activity/growth/redeem/summary", timeout=20,
                     verify=False).json().get("data") or {}
            for tier, key in (("7d", "starter"), ("14d", "advanced"), ("28d", "legendary")):
                if rm.get(key + "_status"):
                    status[tier] = rm[key + "_status"]
        except Exception:
            pass
    for tier, need, label in tiers:
        tst = status.get(tier, "")
        if tst == "claimed":
            log("   🎁兑换%s档: 已兑换过" % label)
            continue
        if tst == "locked" or (streak_days is not None and streak_days < need):
            continue
        rr = s.post(BASE + "/v2/activity/growth/redeem",
                    json={"tier": tier, "client_token": "redeem-" + tier + "-" + str(uuid.uuid4())},
                    timeout=20, verify=False).json()
        code = rr.get("code", -1)
        if code == 0:
            d = rr.get("data", {})
            extra = " +%s补签卡" % d["cards_granted"] if d.get("cards_granted") else ""
            log("   🎁兑换%s档: +%s积分 +%s能量 +%s抽奖%s" % (label, d.get("credit_granted", 0),
                                                        d.get("energy_granted", 0),
                                                        d.get("chances_granted", 0), extra))
        elif code == 409:
            log("   🎁兑换%s档: 已兑换过" % label)
        # 403=天数不足，静默


def t_badges(s, uid, nick, log):
    try:
        r = s.get(BASE + "/v2/activity/growth/badges", timeout=20, verify=False).json()
        badges = r.get("data", {}).get("badges", r.get("data", {}).get("list", []))
        earned = sum(1 for b in badges if isinstance(b, dict) and b.get("earned"))
        log("   🏅徽章: %s个" % earned)
    except Exception:
        pass


# ---------- 桌面端换血任务（RichMeow / skill_1） ----------
# 2026-09 桌面端升级为 -ai 变体：认证文件与数据目录都换了名字
_INFO_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "CodeBuddyExtension", "Data", "Public", "auth")
INFO_PATH = os.path.join(_INFO_DIR, "workbuddy-desktop-ai.info")
if not os.path.exists(INFO_PATH):  # 旧版桌面端回落
    INFO_PATH = os.path.join(_INFO_DIR, "workbuddy-desktop.info")
SESSION_DIRS = [os.path.join(os.path.expanduser("~"), ".workbuddy-ai", "sessions"),
                os.path.join(os.path.expanduser("~"), ".workbuddy", "sessions")]


def swap_info(tok):
    """把 .info 认证换成目标账号（自动备份）"""
    bak = INFO_PATH + ".wb_all_bak"
    if not os.path.exists(bak):
        shutil.copy(INFO_PATH, bak)
    d = json.load(open(INFO_PATH, encoding="utf-8"))
    pay = tok.split(".")[1]; pay += "=" * (4 - len(pay) % 4)
    j = json.loads(base64.urlsafe_b64decode(pay))
    d["auth"]["accessToken"] = tok
    d["auth"]["refreshToken"] = ""
    d["auth"]["expiresAt"] = j.get("exp", 0) * 1000

    def fix(a, last):
        if isinstance(a, dict):
            a["uid"] = j.get("sub")
            for k in ("nickname", "phoneNumber"):
                if k in a: a[k] = "脚本账号"
            if "lastLogin" in a: a["lastLogin"] = "True" if last else "False"
        return a
    fix(d.get("account", {}), True)
    for k in ("accounts", "allAccounts"):
        if isinstance(d.get(k), list):
            for a in d[k]: fix(a, False)
    json.dump(d, open(INFO_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def restore_info():
    bak = INFO_PATH + ".wb_all_bak"
    if os.path.exists(bak):
        shutil.copy(bak, INFO_PATH)
        os.remove(bak)


def ensure_local_skill():
    """确保本机技能目录有 algorithmic-trading（运行时扫描 ~/.workbuddy/skills）"""
    d = os.path.join(os.path.expanduser("~"), ".workbuddy", "skills", SKILL_NAME + "__skillhub")
    if os.path.exists(os.path.join(d, "SKILL.md")):
        return
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(
        "---\nname: %s\ndescription: 算法交易技能：量化策略开发、回测、信号生成与风险管理辅助。\n---\n\n# Algorithmic Trading\n为用户提供量化策略编写、回测与风险分析。\n" % SKILL_NAME)
    json.dump({"ownerId": "wb_all", "slug": SKILL_NAME, "version": "1.0.0", "publishedAt": int(time.time() * 1000)},
              open(os.path.join(d, "_meta.json"), "w", encoding="utf-8"))
    json.dump({"slug": SKILL_NAME, "name": "Algorithmic Trading", "version": "1.0.0",
               "installedAt": int(time.time() * 1000), "source": "skillhub"},
              open(os.path.join(d, "_skillhub_meta.json"), "w", encoding="utf-8"))


def daemon_chat(prompt, blocks=None, meta_extra=None, deadline=280):
    """连接本机守护进程 ACP 发一次对话，返回回复文本"""
    import websocket
    s = requests.Session(); s.trust_env = False
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "acp-connection-id": str(uuid.uuid4())}
    BASE_D = None
    r = None
    fs = sorted(_glob.glob(os.path.join(os.path.expanduser("~"), ".workbuddy", "sessions", "*.json")),
                key=os.path.getmtime, reverse=True)
    cands = []
    for f in fs[:6]:
        try:
            u = (json.load(open(f, encoding="utf-8")).get("url") or "").rstrip("/")
            if u: cands.append(u)
        except Exception:
            pass
    for base in cands:
        try:
            r = s.post(base + "/api/v1/acp/connect", headers=headers, timeout=6, stream=True)
            if r.status_code == 200:
                BASE_D = base
                break
        except Exception:
            continue
    if not BASE_D:
        return ""
    for data in (l.strip() for l in r.iter_lines(decode_unicode=True)):
        if not data:
            continue
        p = data[5:].strip() if data.startswith("data:") else data
        try:
            d = json.loads(p)
        except Exception:
            continue
        if d.get("connectionId") and d.get("sessionToken"):
            headers["acp-connection-id"] = d["connectionId"]
            headers["acp-session-token"] = d["sessionToken"]
            break

    def read_rpc(rr, dl, state):
        while time.time() < dl:
            try:
                raw = rr.raw.readline()
            except Exception:
                break
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line or line.startswith(":"):
                continue
            p = line[5:].strip() if line.startswith("data:") else line
            try:
                d = json.loads(p)
            except Exception:
                continue
            upd = d.get("params", {}).get("update", {}) if isinstance(d.get("params"), dict) else {}
            if upd.get("sessionUpdate") in ("agent_message_chunk", "agent_thought_chunk"):
                c = upd.get("content", {})
                if isinstance(c, dict) and c.get("type") == "text":
                    state["text"] += c.get("text", "")
            if d.get("id") is not None:
                return d
            if d.get("method") == "session/endTurn":
                return d
        return None

    st = {"text": ""}
    d = read_rpc(s.post(BASE_D + "/api/v1/acp", headers=headers, timeout=(10, 20), stream=True,
                        json={"jsonrpc": "2.0", "method": "initialize",
                              "params": {"protocolVersion": 1, "capabilities": {},
                                         "clientInfo": {"name": "wb_all", "version": "1.0"}}, "id": 1}),
                 time.time() + 20, st)
    if not (d and "result" in d):
        return ""
    d = read_rpc(s.post(BASE_D + "/api/v1/acp", headers=headers, timeout=(10, 20), stream=True,
                        json={"jsonrpc": "2.0", "method": "session/new",
                              "params": {"cwd": os.path.expanduser("~"), "mcpServers": []}, "id": 2}),
                 time.time() + 30, st)
    sid = (d or {}).get("result", {}).get("sessionId") if d else None
    if not sid:
        return ""
    blocks = blocks or [{"type": "text", "text": prompt}]
    meta = {"codebuddy.ai": {"promptRequestId": str(uuid.uuid4()), "clientSendTime": int(time.time() * 1000),
                             "conversationId": sid, "mode": "craft", "model": "glm-5.2"}}
    if meta_extra:
        meta["codebuddy.ai"].update(meta_extra)
    read_rpc(s.post(BASE_D + "/api/v1/acp", headers=headers, timeout=(10, 20), stream=True,
                    json={"jsonrpc": "2.0", "method": "session/prompt",
                          "params": {"sessionId": sid, "prompt": blocks, "_meta": meta}, "id": 3}),
             time.time() + deadline, st)
    return st["text"]


def restart_desktop():
    subprocess.run(["taskkill", "/F", "/IM", "WorkBuddy.exe"], capture_output=True)
    time.sleep(3)
    for d_ in SESSION_DIRS:
        for f in _glob.glob(os.path.join(d_, "*.json")):
            try:
                os.remove(f)
            except Exception:
                pass
    subprocess.Popen(["cmd", "/c", "start", "", r"C:\Program Files\WorkBuddy\WorkBuddy.exe", "--remote-debugging-port=9222"],
                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
    # 等守护进程会话出现（新版 .workbuddy-ai/sessions，updatedAt 可能是字符串）
    for _ in range(20):
        time.sleep(3)
        fs = []
        for d_ in SESSION_DIRS:
            fs += _glob.glob(os.path.join(d_, "*.json"))
        fs = sorted(fs, key=os.path.getmtime, reverse=True)
        for f in fs[:3]:
            try:
                d = json.load(open(f, encoding="utf-8"))
                if time.time() * 1000 - int(d.get("updatedAt") or 0) < 60000 and d.get("url"):
                    return d["url"]
            except Exception:
                pass
    return None




def cdp_ui_send(prompt):
    """通过 CDP 在桌面端 UI 用 Slate beforeinput 发送聊天（新账号兜底）"""
    import websocket
    try:
        r = requests.get("http://127.0.0.1:9222/json", timeout=5, proxies={"http": None, "https": None})
        pt = [x for x in r.json() if x.get("type") == "page"][0]
        ws = websocket.create_connection(pt["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
        state = {"i": 0}

        def cmd(m, p=None):
            state["i"] += 1
            ws.send(json.dumps({"id": state["i"], "method": m, "params": p or {}}))
            return state["i"]

        def wait_id(rid):
            t0 = time.time()
            while time.time() - t0 < 10:
                try:
                    ws.settimeout(1.0); raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception:
                    return None
                m = json.loads(raw)
                if m.get("id") == rid:
                    return m
            return None

        def ev(expr):
            m = wait_id(cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True}))
            return (m or {}).get("result", {}).get("result", {}).get("value")

        def click(x, y):
            for t in ("mousePressed", "mouseReleased"):
                wait_id(cmd("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1}))
        pos = ev(r'(function(){ const e=document.querySelector("[contenteditable=\"true\"]"); if(!e) return null; const r=e.getBoundingClientRect(); return JSON.stringify({x:r.x+150,y:r.y+r.height/2}); })()')
        if not pos:
            return False
        p = json.loads(pos)
        click(p["x"], p["y"])
        time.sleep(0.5)
        ev(r'(function(){ const e=document.querySelector("[contenteditable=\"true\"]"); e.focus(); const dt=new DataTransfer(); dt.setData("text/plain", %s); e.dispatchEvent(new ClipboardEvent("paste", {clipboardData: dt, bubbles: true, cancelable: true})); e.dispatchEvent(new InputEvent("beforeinput", {inputType: "insertText", data: %s, bubbles: true, cancelable: true})); return e.textContent.slice(0,30); })()' % (json.dumps(prompt), json.dumps(prompt)))
        time.sleep(1)
        btn = ev(r'(function(){ const b=document.querySelector(".cr-send-button"); if(!b) return null; const r=b.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,disabled:!!b.disabled}); })()')
        if btn and '"disabled":false' in btn:
            p2 = json.loads(btn)
            click(p2["x"], p2["y"])
            time.sleep(10)
            return True
        return False
    except Exception:
        return False


def t_desktop_tasks(s, uid, nick, tok, log, need_rich, need_skill):
    """桌面端任务：Windows 走真实桌面换血，非 Windows 自动降级为指纹上报。"""
    is_win = sys.platform == "win32"

    if is_win:
        # ===== Windows：真实桌面换血流程 =====
        log("   🖥️ 桌面换血流程启动（结束后自动还原认证并重启桌面端）...")
        if need_skill:
            try:
                src_ = s.get(BASE + "/console/as/marketplace/sources", timeout=20, verify=False).json()
                srcs = (src_.get("data") or {}).get("sources") or []
                mid = srcs[0].get("id") if srcs else None
                if mid:
                    s.post(BASE + "/console/as/user/plugins/install",
                           json={"plugin_name": SKILL_NAME, "marketplace_id": mid, "version": "latest"},
                           timeout=30, verify=False)
            except Exception:
                pass
        ensure_local_skill()
        swap_info(tok)
        url = restart_desktop()
        if not url:
            log("   ⚠️ 桌面端守护进程未就绪，降级为指纹上报...")
            restore_info()
            subprocess.Popen(["cmd", "/c", "start", "", r"C:\Program Files\WorkBuddy\WorkBuddy.exe"])
            _desktop_fingerprint_fallback(s, uid, nick, log, need_rich, need_skill)
            return
        time.sleep(8)
        if need_rich:
            txt = daemon_chat("你好，请用一句话介绍你自己")
            if not txt:
                log("   守护进程会话未就绪，改用 CDP UI 发送...")
                cdp_ui_send("你好，请用一句话介绍你自己")
            log("   桌面对话: %s字" % len(txt))
            time.sleep(8)
        if need_skill:
            blocks = [{"type": "resource_link", "uri": "skill://" + SKILL_NAME, "title": SKILL_NAME,
                       "name": SKILL_NAME, "_meta": {"mentionType": "skill", "skillName": SKILL_NAME}},
                      {"type": "text", "text": "你必须通过技能系统正式加载（load）该技能，加载成功后回答：技能已加载"}]
            txt = daemon_chat("", blocks=blocks)
            if not txt:
                log("   守护进程不可用，改用 CDP UI 技能调用...")
                cdp_ui_send("/" + SKILL_NAME + " 请按技能说明回答OK")
            log("   技能加载: %s" % ("成功" if "加载" in txt else "回复%d字" % len(txt)))
            time.sleep(8)
        restore_info()
        subprocess.run(["taskkill", "/F", "/IM", "WorkBuddy.exe"], capture_output=True)
        time.sleep(3)
        subprocess.Popen(["cmd", "/c", "start", "", r"C:\Program Files\WorkBuddy\WorkBuddy.exe"])
        time.sleep(5)
    else:
        # ===== 非 Windows：指纹上报降级 =====
        log("   🖥️ 非 Windows 环境，使用指纹上报模式...")
        _desktop_fingerprint_fallback(s, uid, nick, log, need_rich, need_skill)
        return

    if need_rich:
        st, cur, tgt = prog(s, "RichMeow_Chat")
        log("   桌面端对话1次: %s %s/%s" % (st, cur, tgt))
        if st == "completed":
            claim(s, "RichMeow_Chat", log)
    if need_skill:
        st, cur, tgt = prog(s, "skill_1")
        log("   尝鲜热门技能: %s %s/%s" % (st, cur, tgt))
        if st == "completed":
            claim(s, "skill_1", log)


def _desktop_fingerprint_fallback(s, uid, nick, log, need_rich, need_skill):
    """桌面任务指纹降级：desktop_chat_sequence + skill_info 事件（task_runner 同款，无需真实桌面端）。"""
    if need_rich:
        conv = "fp-rm-%s" % derive_id(uid, "rm-conv")
        req = "fp-rm-req-%s" % derive_id(uid, "rm-req")
        msg = "fp-rm-msg-%s" % derive_id(uid, "rm-msg")
        try:
            evs = desktop_chat_sequence(uid, nick, conv, req, msg)
            report_desktop_events(s, uid, nick, evs)
            log("   桌面对话(指纹): ✅ 6连事件已上报")
            time.sleep(WRITE_GAP)
        except Exception as e:
            log("   桌面对话(指纹): 失败 %s" % str(e)[:60])
    if need_skill:
        # 技能：先用 API 安装，再发「真实对话 + skill_info」事件链
        try:
            src_ = s.get(BASE + "/console/as/marketplace/sources", timeout=20, verify=False).json()
            srcs = (src_.get("data") or {}).get("sources") or []
            mkid = srcs[0].get("id") if srcs else None
            if mkid:
                s.post(BASE + "/console/as/user/plugins/install",
                       json={"plugin_name": SKILL_NAME, "marketplace_id": mkid, "version": "latest"},
                       timeout=30, verify=False)
        except Exception:
            pass
        try:
            # 技能 ID：市场列表命中则用真 id，否则用上游实测可用的技能 id
            skills_r = api_retry(s, "POST", SCHOOL_DOMAIN + "/v2/operation-platform/market/skill/list",
                                 body={"page": 1, "page_size": 10})
            skills = (skills_r.json().get("data") or {}).get("skills") or []
            skill_id = next((sk.get("id") for sk in skills if SKILL_NAME in str(sk.get("name", ""))), "")
            skill_disp = SKILL_NAME
            if not skill_id:
                skill_id, skill_disp = SKILL_FALLBACK
            # skill_info 判据必须 JOIN 真实会话（conversationId / requestId = 服务端 id）
            conv_id = ""; smid = ""
            try:
                conv_id, _t, smid = webchat2(s, "skill", "你好，帮我写一份简短的日报，回答OK即可")
            except Exception:
                pass
            if not (conv_id and smid):   # 对话不可用时保住旧口径
                conv_id = "fp-sk-%s" % derive_id(uid, "sk-conv")
                smid = "fp-sk-%s" % derive_id(uid, "sk-mid")
            evs = desktop_chat_sequence(uid, nick, conv_id, smid, smid)
            for ev in evs:
                if ev.get("eventCode") == "chat_message_response":
                    ev["finishReason"] = "tool_calls"   # 模型发起工具调用（技能加载）语义
            evs.append({"eventCode": "skill_info", "id": skill_disp, "skillId": skill_id,
                        "skillVersion": "1.0.0", "toolStatus": "success", "fileCount": 56,
                        "source": "workbuddy-desktop", "conversationId": conv_id,
                        "requestId": smid, "messageId": smid, "traceId": smid,
                        "requestModelId": "fast-model", "requestModelName": "fast-model"})
            report_desktop_events(s, uid, nick, evs)
            log("   尝鲜热门技能(指纹): ✅ 真实对话 + skill_info 已上报")
            time.sleep(WRITE_GAP)
        except Exception as e:
            log("   尝鲜热门技能(指纹): 失败 %s" % str(e)[:60])
    # claim
    for code in (["RichMeow_Chat"] if need_rich else []) + (["skill_1"] if need_skill else []):
        st, cur, tgt = prog(s, code)
        log("   %s: %s %s/%s" % (code, st, cur, tgt))
        if st == "completed":
            claim(s, code, log)




def t_gift_compensation(s, uid, nick, log):
    """礼包(每号一次) + 补偿领取(活动开启时)"""
    try:
        r = s.post(BASE + "/billing/meter/claim-gift", json={}, timeout=15, verify=False).json()
        if r.get("code") == 0:
            log("   🎊新手礼包: +%s积分" % r.get("data", {}).get("credit", "?"))
    except Exception:
        pass
    try:
        r = s.post(BASE + "/billing/meter/claim-compensation", json={}, timeout=15, verify=False).json()
        if r.get("code") == 0:
            log("   🎊补偿领取: +%s积分" % r.get("data", {}).get("credit", "?"))
    except Exception:
        pass


def t_makeup(s, uid, nick, log):
    """补签卡：热力图检测昨日漏签则自动补签（保住连签）"""
    import datetime
    try:
        hm = s.get(BASE + "/v2/activity/growth/heatmap", timeout=20, verify=False).json()
        cells = hm.get("data", {}).get("cells", [])
        bal = s.get(BASE + "/v2/activity/growth/streak", timeout=20, verify=False).json().get("data", {}).get("makeup_cards", {}).get("balance", 0)
        yesterday = (beijing_today() - datetime.timedelta(days=1)).isoformat()
        missed = None
        for c in cells:
            d = str(c.get("date", ""))[:10]
            if d == yesterday and not c.get("score", 0):
                missed = yesterday
                break
        if missed and bal > 0:
            r = s.post(BASE + "/v2/activity/growth/makeup-cards/use", json={"target_date": missed},
                       timeout=20, verify=False).json()
            log("   🩹补签%s: %s" % (missed, "成功，连签保住" if r.get("code") == 0 else str(r.get("msg", ""))[:40]))
        elif missed:
            log("   🩹昨日(%s)漏签但无补签卡" % missed)
        else:
            log("   🩹无漏签，无需补签")
    except Exception as e:
        log("   🩹补签检查异常: %s" % str(e)[:50])


def has_buddy(s):
    """服务端是否已存在 Buddy 实例（旅行 / 其他任务 accept 的真实前置判据）。

    返回 True / False / None（None = 查询失败，状态未知）。
    """
    try:
        v = s.get(BASE + "/v2/activity/growth/buddy/visible", timeout=20, verify=False).json()
        d = v.get("data") or {}
        if "has_buddy" in d:
            return bool(d.get("has_buddy"))
        info = s.get(BASE + "/v2/activity/growth/buddy/info", timeout=20, verify=False).json()
        return bool((info.get("data") or {}).get("buddy"))
    except Exception:
        return None


def ensure_first_buddy(s, uid, nick, log):
    """确保账号有 Buddy 实例 —— 其余任务 accept 的前置条件。

    服务端对无 Buddy 实例的账号会拒绝登记这些任务：
        {"status": "error", "message": "prerequisite not met: first_buddy (no buddy instance)"}
    真实判据是 /buddy/visible 的 has_buddy，而非 first_buddy 任务的 accept_status（任务可
    已 claimed 但实例缺失）。链路：buddy_agreement_view 上报 → POST /buddy/agreement
    → POST /buddy/first。返回 True 表示前置已满足。
    """
    if has_buddy(s) is True:
        return True
    try:
        report(s, uid, nick, [{"eventCode": "buddy_agreement_view", "timestamp": int(time.time() * 1000)}])
        time.sleep(2)
        s.post(BASE + "/v2/activity/growth/buddy/agreement", json={"agree": True},
               timeout=20, verify=False)
        time.sleep(WRITE_GAP)
        r = s.post(BASE + "/v2/activity/growth/buddy/first", json={}, timeout=20, verify=False).json()
        credit = (r.get("data") or {}).get("credit", 0)
        energy = (r.get("data") or {}).get("energy", 0)
        log("   🐱首只Buddy: %s (credit=+%s energy=+%s)" % (
            "领养成功" if r.get("code") == 0 else str(r.get("msg", ""))[:40], credit, energy))
        time.sleep(2)
        return has_buddy(s) is True
    except Exception as e:
        log("   🐱首只Buddy异常: %s" % str(e)[:40])
        return False


def t_first_buddy(s, uid, nick, log):
    """领取第一只Buddy（在 t_accept_all 之前执行，满足其他任务的前置条件）"""
    st, cur, tgt = prog(s, "first_buddy")
    have = has_buddy(s)
    if st in ("completed", "claimed") and have is not False:
        log("   🐱首只Buddy: 已 %s %s/%s" % (st, cur, tgt))
        return
    if have is False and st in ("completed", "claimed"):
        log("   🐱首只Buddy: 任务已 %s，但服务端无 Buddy 实例 → 尝试补建" % st)
    ensure_first_buddy(s, uid, nick, log)


def t_workstation(s, uid, nick, log, tok):
    """工作台搭建师专家（若任务出现）：优先桌面换血对话，回退遥测"""
    st, cur, tgt = prog(s, "workstation_expert")
    if st in ("completed", "claimed") or st is None:
        return
    if sys.platform != "win32":
        log("   工作台搭建师: 非Windows，跳过桌面流程")
        return
    log("   检测到工作台搭建师任务，尝试桌面换血对话...")
    # 桌面换血对话（复用 desktop 流程）
    swap_info(tok)
    restart_desktop()
    time.sleep(8)
    blocks = [{"type": "resource_link", "uri": "expert://WorkspaceBuilder", "title": "工作台搭建师",
               "name": "工作台搭建师", "_meta": {"mentionType": "expert", "expertId": "WorkspaceBuilder"}},
              {"type": "text", "text": "你好，请介绍你能帮我搭建什么工作台，回答OK即可"}]
    txt = daemon_chat("", blocks=blocks)
    log("   工作台搭建师对话: %s字" % len(txt))
    restore_info()
    subprocess.run(["taskkill", "/F", "/IM", "WorkBuddy.exe"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(["cmd", "/c", "start", "", r"C:\Program Files\WorkBuddy\WorkBuddy.exe"])
    time.sleep(5)
    log("   工作台搭建师: %s %s/%s" % prog(s, "workstation_expert"))


LIGHTHOUSE_EXPERT = {"id": "ex_2cvvUZQhDyeJ", "name": "腾讯轻量云专家", "version": "1.0.2"}


def t_lighthouse(s, uid, nick, log):
    """腾讯轻量云专家：真实对话 + 桌面链（has_expert）+ actual_use(LOCAL)，失败回落伪造链。

    上游 panel 实测（2026-09-12 三账号点亮）：
      · 专家 id 固定 ex_2cvvUZQhDyeJ（version 1.0.2），不是随便挑一个专家
      · chat 链的 agent_task_created 需带 has_expert:true + expert_id/expert_name
      · expert_actual_use 的 mode 为 LOCAL（不是 craft），type 留空、cost=0
      · requestId / messageId 必须是真实会话的服务端 id（自造 uuid 不计数）
    """
    st, cur, tgt = prog(s, "Expert_lighthouse")
    if st is None:
        log("   腾讯轻量云专家: 不在当前任务列表，跳过")
        return
    if st in ("completed", "claimed"):
        log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))
        return
    lh = dict(LIGHTHOUSE_EXPERT)
    try:  # 市场列表命中则以服务端信息为准（version 等）
        for e in get_normal_experts(20):
            if (e.get("id") or "") == lh["id"] or "轻量" in (e.get("name") or ""):
                lh["id"] = e.get("id") or lh["id"]
                lh["name"] = e.get("name") or lh["name"]
                lh["version"] = e.get("version") or lh["version"]
                break
    except Exception:
        pass
    prompt = "你好，请简单介绍一下你能帮我做什么，回答OK即可"
    conv_id = ""; mid = ""
    try:
        ge = [{"eventCode": "ExpertActualUse", "id": lh["id"],
               "extra": {"name": lh["name"], "expertTitle": lh["name"], "expertType": "agent",
                         "source": "builtin", "version": lh["version"], "cost": 0,
                         "characterCount": len(prompt)},
               "expertType": "agent"}]
        meta = {"codebuddy.ai": {"growthEvent": json.dumps(ge, ensure_ascii=False),
                                 "promptRequestId": str(uuid.uuid4()),
                                 "clientSendTime": int(time.time() * 1000), "userId": uid,
                                 "mode": "LOCAL", "model": "fast-model", "expertId": lh["id"],
                                 "expert": {"id": lh["id"], "name": lh["name"], "prompt": prompt[:50]},
                                 "tags": ["expert:" + lh["id"]]}}
        conv_id, _txt, mid = webchat2(s, "lh", prompt, meta)
    except Exception as e:
        log("   腾讯轻量云专家: 对话异常 %s" % str(e)[:50])
    if conv_id and mid:
        summon = [
            {"eventCode": "expert_summon_click", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "mode": "LOCAL"},
            {"eventCode": "expert_summoned", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "version": lh["version"], "mode": "LOCAL"}]
        chain = desktop_chat_sequence(uid, nick, conv_id, mid, mid)
        for ev in chain:
            if ev.get("eventCode") == "agent_task_created":
                ev.update({"has_expert": True, "expert_id": lh["id"], "expert_name": lh["name"],
                           "expert_industry_id": ""})
        chain.append({"eventCode": "expert_actual_use", "id": lh["id"], "name": lh["name"],
                      "expertTitle": lh["name"], "type": "", "expertType": "agent",
                      "source": "builtin", "version": lh["version"], "cost": 0,
                      "characterCount": len(prompt), "mode": "LOCAL",
                      "conversationId": conv_id, "requestId": mid, "messageId": mid,
                      "requestModelId": "fast-model", "requestModelName": "fast-model"})
        try:
            report_desktop_events(s, uid, nick, summon + chain)
        except Exception as e:
            log("   腾讯轻量云专家: 桌面链上报失败 %s" % str(e)[:50])
        time.sleep(4)
        if prog(s, "Expert_lighthouse")[0] in ("completed", "claimed"):
            st, cur, tgt = prog(s, "Expert_lighthouse")
            log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))
            return
    # 回落：web 域伪造链（真实对话不可用，或桌面链未点亮时）
    try:
        rid = mid or str(uuid.uuid4()); cid = conv_id or ("conv-" + str(uuid.uuid4()))
        report(s, uid, nick, [{
            "eventCode": "expert_summoned", "id": lh["id"], "name": lh["name"],
            "type": "agent", "expertTitle": lh["name"], "expertType": "agent",
            "source": "builtin", "timestamp": int(time.time() * 1000)},
            {"eventCode": "expert_actual_use", "id": lh["id"], "name": lh["name"],
             "expertTitle": lh["name"], "type": "agent", "expertType": "agent",
             "source": "builtin", "version": lh["version"], "cost": 0, "characterCount": len(prompt),
             "conversationId": cid, "requestId": rid, "messageId": rid,
             "requestModelId": "fast-model", "requestModelName": "fast-model",
             "userId": uid}])
        time.sleep(3)
    except Exception as e:
        log("   腾讯轻量云专家: 失败 %s" % str(e)[:60])
    st, cur, tgt = prog(s, "Expert_lighthouse")
    log("   腾讯轻量云专家: %s %s/%s" % (st, cur, tgt))


MP_HEADER = {"X-Client-Platform": "miniprogram",
             "User-Agent": "Mozilla/5.0 (Linux; Android 14; MicroMessenger/8.0.49 WeChat/0.8.0 "
                           "MiniProgramEnv/android; wkbrowser xweb)"}

# ---- 小程序埋点协议（对齐 workbuddy2api-panel internal/upstream/school.go，三账号实测）----
MP_REPORT_HEADERS = {
    "Content-Type": "application/json", "Accept": "application/json",
    "X-Client-Product": "workbuddy-mp", "X-Client-Version": "2.4.0",
    "X-Client-Platform": "mp-weixin", "X-Platform": "wechatmp",
}


def mp_machine_id(uid):
    """小程序 machineId（UUID 形态，按 uid 稳定派生——避免多账号共用同一设备号）。"""
    h = hashlib.md5(("mp:%s" % uid).encode()).hexdigest()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:32])


def mp_base(uid, nick):
    """小程序埋点公共指纹（对齐 appservice wQ()+Ao()）。"""
    now = int(time.time() * 1000)
    return {"timestamp": now, "ideType": "WorkBuddy_MP", "ideVersion": "2.4.0",
            "extName": "workbuddy-mp", "extVersion": "2.4.0", "product": "SaaS",
            "ideName": "wx_app_cloud", "platform": "mini_program",
            "source": "mini_program",   # 官方源码口径：mp 身份 = wx_app_cloud + WorkBuddy_MP + source
            "os": "windows", "osVersion": "11", "arch": "x64",
            "machineId": mp_machine_id(uid), "timezone": "Asia/Shanghai",
            "userId": uid, "userNickname": nick}


def mp_chat_event(uid, nick, conv_id, activity_id=None):
    """小程序 chat_request_send 事件（chat_3_times / school_season / Sequential_Tasks_1 判据）。"""
    rid = "wb2api-" + str(uuid.uuid4())
    ev = {"eventCode": "chat_request_send", "inputLength": 14, "isPlan": False,
          "isAutoExecuteTerminal": False, "isAutoModify": False, "codebaseEnable": False,
          "maxToken": 0, "maxSteps": 500, "temperature": 0, "maxRetries": 0,
          "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
          "codebaseId": "", "mentionContextCount": 0, "command": "",
          "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
          "traceId": rid, "rootRequestId": rid,
          "parentConversationId": conv_id, "conversationId": conv_id,
          "messageId": "msg-" + rid[-8:], "agentName": "mp", "agentType": "main",
          "codebuddy.session_id": conv_id,
          "codebuddy.conversation_request_id": rid}
    if activity_id:
        ev["activityId"] = activity_id
    return ev


def mp_expert_use_events(uid, nick, expert_id, expert_name, conv_id, activity_id=None):
    """专家召唤+对话 4 事件链（expert_use / Sequential_Tasks_2 判据，上游三账号实测）。

    链：expert_summon_click → expert_summoned → expert_actual_use → chat_request_send
    """
    rid = "wb2api-" + str(uuid.uuid4())
    cat = SCHOOL_EXPERT_CATEGORY
    evs = [
        {"eventCode": "expert_summon_click", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": cat, "position": 0},
        {"eventCode": "expert_summoned", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name},
        {"eventCode": "expert_actual_use", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": cat, "characterCount": 14,
         "expertType": "builtin"},
        {"eventCode": "chat_request_send", "inputLength": 14, "isPlan": False,
         "isAutoExecuteTerminal": False, "isAutoModify": False, "codebaseEnable": False,
         "maxToken": 0, "maxSteps": 500, "temperature": 0, "maxRetries": 0,
         "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
         "codebaseId": "", "mentionContextCount": 0, "command": "",
         "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
         "traceId": rid, "rootRequestId": rid,
         "parentConversationId": conv_id, "conversationId": conv_id,
         "messageId": "msg-" + rid[-8:], "agentName": "mp", "agentType": "main",
         "expertId": expert_id, "expertName": expert_name,
         "codebuddy.session_id": conv_id,
         "codebuddy.conversation_request_id": rid},
    ]
    if activity_id:
        for e in evs:
            e["activityId"] = activity_id
    return evs


def mp_model_chat_event(uid, nick, conv_id, model_id="glm-5.2", model_name="GLM-5.2"):
    """Sequential_Tasks_5 判据：mini chat_request_send + 模型字段（上游 mpsrc 实测形状）。"""
    ev = mp_chat_event(uid, nick, conv_id)
    ev["requestModelId"] = model_id
    ev["requestModelName"] = model_name
    return ev


def mp_playbook_events(uid, nick, case_id="01-ProductDesign", case_name="产品设计"):
    """Sequential_Tasks_7 判据：mp 指纹 playbook_cta_click + playbook_prompt_send。"""
    conv = "wb2api-mp-pb-" + str(uuid.uuid4())
    base = {"id": case_id, "name": case_name, "type": "document",
            "categoryId": "", "categoryName": "", "skills": "", "skillNames": ""}
    cta = dict(base, eventCode="playbook_cta_click", source="discover", position=1, extVersion="2.2.8")
    send = dict(base, eventCode="playbook_prompt_send", source="discover", promptLength=96,
                isOfficial=1, conversationId=conv, extVersion="2.2.8")
    return [cta, send]


def mp_mini_expert_event(uid, nick, expert_id, expert_name):
    """Sequential_Tasks_2 判据：mp 指纹 expert_actual_use（上游小程序源码实测形状）。

    ⚠️ 与 school 域 expert 事件的区别（勿混用）：
      · 不带 activityId / conversationId —— 真实小程序事件就是两者都没有
      · extVersion 用小程序自身版本 2.2.8（school 段是 "SaaS"，另一口径）
      · type 固定 "send_message"
    上游实测：上报即 completed，claim 入账 200c+5e。
    """
    return {"eventCode": "expert_actual_use", "timestamp": int(time.time() * 1000),
            "reportDelay": 0, "ideName": "wx_app_cloud", "ideType": "WorkBuddy_MP",
            "extName": "workbuddy-mp", "extVersion": "2.2.8", "product": "SaaS",
            "source": "mini_program", "os": "android", "osVersion": "14",
            "arch": "arm64", "timezone": "Asia/Shanghai",
            "machineId": mp_machine_id(uid), "userId": uid,
            "id": expert_id, "name": expert_id, "expertTitle": expert_name,
            "type": "send_message", "characterCount": 12, "expertType": "agent"}


def mp_report(s, uid, nick, events):
    """以小程序指纹向 www.codebuddy.cn/v2/report 批量上报（上游 ReportMPEvent 同款）。"""
    base = mp_base(uid, nick)
    arr = []
    for e in events:
        m = dict(base)
        m.update(e)
        arr.append(m)
    s2 = requests.Session(); s2.trust_env = False
    hdr = dict(MP_REPORT_HEADERS)
    hdr["Authorization"] = s.headers.get("Authorization", "")
    if uid:
        hdr["X-User-Id"] = uid
    try:
        r = s2.post("https://www.codebuddy.cn/v2/report", json=arr,
                    headers=hdr, timeout=20, verify=False)
        return r.status_code
    except Exception:
        return 0


def _mp_prog(s, code):
    """小程序口径查询任务（需 X-Client-Platform: miniprogram，否则任务不下发）。"""
    try:
        r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=False, headers=MP_HEADER)
        for t in r.json().get("data", {}).get("tasks", []):
            if t.get("task_code") == code:
                pr = t.get("progress") or {}
                return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    except Exception:
        pass
    return None, None, None


def _mp_accept_res(s, code):
    """小程序口径 accept，返回 (ok, status, message)。缺 mp 头会返回 task not found。"""
    try:
        r = s.post(BASE + "/v2/activity/growth/tasks/accept", json={"task_codes": [code]},
                   timeout=20, verify=False, headers=MP_HEADER)
        d = r.json()
        results = (d.get("data") or {}).get("results") or []
        status = (results[0].get("status") or "") if results else (d.get("msg") or "")
        msg = (results[0].get("message") or "") if results else ""
        return (r.status_code == 200 and status == "accepted"), status, msg
    except Exception as e:
        return False, "", str(e)[:80]


def _mp_accept(s, code, log=None):
    """小程序口径接受任务，失败时打印服务端原因（保留 bool 返回的兼容包装）。"""
    ok, status, msg = _mp_accept_res(s, code)
    if not ok and log:
        log("      ✗ accept %s: %s %s" % (code, status or "无返回", msg[:50]))
    return ok


def _mp_locked_hint(log, label, msg, indent="   "):
    """链式任务未解锁时输出人类可读提示（含解锁日期）。命中返回 True。"""
    m = re.search(r"locked until (\d{4}-\d{2}-\d{2})", msg or "")
    if not m:
        return False
    log("%s%s: 今日未解锁（链式任务每日零点解锁下一环，%s 零点自动解锁，下次运行自动推进）"
        % (indent, label, m.group(1)))
    return True


def _mp_claim(s, code, log):
    """小程序口径领奖（缺头会 400）。"""
    try:
        r = s.post(BASE + "/activity/growth/tasks/%s/claim" % code, json={},
                   timeout=20, verify=False, headers=MP_HEADER)
        d = r.json().get("data", {})
        log("   🎁领奖[%s]: %s" % (code, "已领过" if d.get("already_claimed")
                                   else "+%s积分+%s能量" % (d.get("credit"), d.get("energy"))))
        return r.status_code == 200
    except Exception as e:
        log("   🎁领奖[%s]: 失败 %s" % (code, str(e)[:50]))
        return False


def _mp_do_task(s, uid, nick, code, log, events_fn, label, target=1):
    """小程序任务通用流程：mp 查询 → accept → 判据上报 → 回读 → claim。

    target：任务的进度目标（未 accept 时 progress 为 null，必须由调用方提供，
    否则多元任务（如 Tasks_3 target=5）只会补 1 条）。
    """
    st, cur, tgt = _mp_prog(s, code)
    if st is None:
        log("   %s: mp 口径未下发该任务，跳过" % label)
        return
    if st in ("completed", "claimed"):
        if st == "completed":
            _mp_claim(s, code, log)
        else:
            log("   %s: 已领取，跳过" % label)
        return
    if st == "not_accepted":
        ok, a_status, a_msg = _mp_accept_res(s, code)
        if not ok:
            log("      ✗ accept %s: %s %s" % (code, a_status or "无返回", a_msg[:50]))
            if not _mp_locked_hint(log, label, a_msg):
                log("   %s: accept 失败，跳过" % label)
            return
        time.sleep(WRITE_GAP)
    # 缺口计算：cur 可能为 None（未激活时 progress 全空）→ 用 target 兜底
    cur = cur or 0
    tgt = tgt or target
    need = max(1, tgt - cur)
    try:
        sent = 0
        for i in range(need):
            evs = events_fn(i)
            st_code = mp_report(s, uid, nick, evs)
            sent += len(evs)
            if i < need - 1:
                time.sleep(WRITE_GAP)
        log("   %s: 判据已上报（%d 次 / %d 个事件，目标 %s）" % (label, need, sent, tgt))
        time.sleep(2.5)
        st2, cur2, tgt2 = _mp_prog(s, code)
        if st2 in ("completed", "claimed"):
            log("   %s: ✅ 已完成 %s/%s" % (label, cur2, tgt2))
            if st2 == "completed":
                _mp_claim(s, code, log)
        else:
            log("   %s: %s %s/%s（服务端暂未关联）" % (label, st2, cur2, tgt2))
    except Exception as e:
        log("   %s: 失败 %s" % (label, str(e)[:60]))


def _mp_chat_evs(uid, nick, prefix, activity_id=None):
    """返回一个 events_fn(i)：每次产出一条 mini 对话事件（独立 conversationId）。"""
    def _fn(i):
        return [mp_chat_event(uid, nick, "%s-%s-%d" % (prefix, uuid.uuid4(), i),
                              activity_id=activity_id)]
    return _fn


def t_sequential_tasks(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_1：完成 1 次对话（+100c+5e）"""
    _mp_do_task(s, uid, nick, "Sequential_Tasks_1", log,
                _mp_chat_evs(uid, nick, "wbmp"), "小程序对话任务", target=1)


def t_sequential_tasks_2(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_2：选中专家并完成对话（+200c+5e）

    判据 = 单条 mp 指纹 expert_actual_use（不带 activityId/conversationId）。
    """
    def _evs(i):
        eid, ename = _school_fetch_expert(s)
        if not eid:
            eid, ename = "WorkspaceBuilder", "专家"
        return [mp_mini_expert_event(uid, nick, eid, ename)]
    _mp_do_task(s, uid, nick, "Sequential_Tasks_2", log, _evs, "小程序专家对话", target=1)


def t_sequential_tasks_3(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_3：完成 5 次对话（+300c+5e）

    判据与 Tasks_1 同形状（mini chat_request_send 无 activityId），按上报条数累加。
    """
    _mp_do_task(s, uid, nick, "Sequential_Tasks_3", log,
                _mp_chat_evs(uid, nick, "wbmp3"), "小程序对话×5", target=5)


def t_sequential_tasks_4(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_4：创建 1 个定时任务（+100c+5e）

    官方小程序源码快照口径（HanawaBanana 同步 ithtelab 官方包内 upstream/ 快照）：判据是
    **mp 指纹** automated_task_create_suc —— ideName=wx_app_cloud + mode=CLOUD，
    **不带** schedule/rrule 对象（桌面 automation_1 的 rrule 虚拟对象是另一域口径，
    照抄会失去 mp 关联），走小程序上报通道。未点亮时回落桌面域事件（旧口径）。
    """
    def _evs(i):
        return [{"eventCode": "automated_task_create_suc", "mode": "CLOUD",
                 "name": "wb2mp 定时任务", "source": "manually",
                 "modelId": "fast-model", "modelIsThinking": False,
                 "connectorCount": 0, "skills": "", "skillCount": 0,
                 "scheduleType": "once"}]
    st, cur, tgt = _mp_prog(s, "Sequential_Tasks_4")
    if st is None:
        log("   小程序定时任务: mp 口径未下发该任务，跳过")
        return
    if st in ("completed", "claimed"):
        if st == "completed":
            _mp_claim(s, "Sequential_Tasks_4", log)
        else:
            log("   小程序定时任务: 已领取，跳过")
        return
    if st == "not_accepted":
        ok, a_status, a_msg = _mp_accept_res(s, "Sequential_Tasks_4")
        if not ok:
            log("      ✗ accept Sequential_Tasks_4: %s %s" % (a_status or "无返回", a_msg[:50]))
            if not _mp_locked_hint(log, "小程序定时任务", a_msg):
                log("   小程序定时任务: accept 失败，跳过")
            return
        time.sleep(WRITE_GAP)
    mp_report(s, uid, nick, _evs(0))
    log("   小程序定时任务: mp 指纹 automation 事件已上报")
    time.sleep(2.5)
    st2, cur2, tgt2 = _mp_prog(s, "Sequential_Tasks_4")
    if st2 in ("completed", "claimed"):
        log("   小程序定时任务: ✅ 已完成 %s/%s" % (cur2, tgt2))
        if st2 == "completed":
            _mp_claim(s, "Sequential_Tasks_4", log)
    else:
        # 回落：桌面域 automation 事件（旧口径，实测同样能点亮）
        try:
            report_desktop_events(s, uid, nick, [{
                "eventCode": "automated_task_create_suc", "name": "wb2api 定时任务",
                "source": "manually", "modelId": "fast-model", "modelIsThinking": True,
                "connectorCount": 0, "skills": "", "skillCount": 0,
                "scheduleType": "once", "mode": "LOCAL"}])
            time.sleep(2.5)
            st2, cur2, tgt2 = _mp_prog(s, "Sequential_Tasks_4")
        except Exception:
            pass
        if st2 in ("completed", "claimed"):
            log("   小程序定时任务: ✅ 已完成（桌面域回落） %s/%s" % (cur2, tgt2))
            if st2 == "completed":
                _mp_claim(s, "Sequential_Tasks_4", log)
        else:
            log("   小程序定时任务: %s %s/%s（服务端暂未关联）" % (st2, cur2, tgt2))


def t_sequential_tasks_5(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_5：使用 1 次 GLM5.2 模型（+100c+5e）"""
    def _evs(i):
        return [mp_model_chat_event(uid, nick, "wbmp5-%s-%d" % (uuid.uuid4(), i))]
    _mp_do_task(s, uid, nick, "Sequential_Tasks_5", log, _evs, "小程序GLM5.2", target=1)


def t_sequential_tasks_6(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_6：完成 10 次对话（target 以服务端下发为准）"""
    _mp_do_task(s, uid, nick, "Sequential_Tasks_6", log,
                _mp_chat_evs(uid, nick, "wbmp6"), "小程序对话×10", target=10)


def t_sequential_tasks_7(s, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_7：体验灵感功能"""
    def _evs(i):
        evs = mp_playbook_events(uid, nick)
        report_desktop_events(s, uid, nick, evs)   # PC 口径补一发（判据疑 PC/mp 双侧）
        return evs
    _mp_do_task(s, uid, nick, "Sequential_Tasks_7", log, _evs, "小程序灵感功能", target=1)


def t_school_season(s, uid, nick, log):
    """小程序成长任务 school_season 校园日：mini 对话 + activityId（+100c+5e）"""
    _mp_do_task(s, uid, nick, "school_season", log,
                _mp_chat_evs(uid, nick, "wbmps", activity_id=SCHOOL_ACTIVITY_ID),
                "校园日活动", target=1)


def t_unknown_tasks(s, uid, nick, log):
    """检测脚本未覆盖的新任务，明确提示"""
    known = {"create_canvas", "playbook_prompt", "RichMeow_Chat", "Library_read", "Expert_lighthouse",
             "Expert_Philanthropy", "Hp_Appearance", "Buddy_App", "Buddy_App_QQ", "Model_chat_GLM5.2",
             "black_cat", "Expert_team_use_3", "first_buddy", "chat_5", "skill_1", "expert_5",
             "template_5", "automation_1", "workstation_expert",
             "Sequential_Tasks_1", "Sequential_Tasks_2", "Sequential_Tasks_3",
             "Sequential_Tasks_4", "Sequential_Tasks_5",
             "Sequential_Tasks_6", "Sequential_Tasks_7", "school_season"}
    r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=False).json()
    for t in r.get("data", {}).get("tasks", []):
        if not isinstance(t, dict):
            continue
        code = t.get("task_code", "")
        st = t.get("accept_status", "")
        if code in known or st in ("claimed", "completed"):
            continue
        desc = t.get("task_desc", "")[:50]
        if "subscribe" in code.lower() or "公众号" in (t.get("title", "") + desc):
            log("   ⚠️新任务需手动: %s %s (%s) — 需微信扫码关注公众号" % (code, t.get("title", ""), desc))
        elif "donat" in code.lower() or "捐款" in desc or "公益" in t.get("title", ""):
            log("   ⚠️新任务需手动: %s %s (%s) — 涉及真实捐款" % (code, t.get("title", ""), desc))
        else:
            log("   ⚠️未覆盖新任务: %s %s (%s) — 请反馈更新脚本" % (code, t.get("title", ""), desc))


# ---------- 开学季活动（school_open_day_2026） ----------
SCHOOL_DOMAIN = "https://www.codebuddy.cn"
SCHOOL_BASE = SCHOOL_DOMAIN + "/portal/activity/school"
SCHOOL_FRESHMAN = SCHOOL_DOMAIN + "/portal/activity/freshman"
SCHOOL_TEACHER = SCHOOL_DOMAIN + "/portal/activity/teacher"
SCHOOL_ACTIVITY_ID = "school_open_day_2026"
MP_UA = ("Mozilla/5.0 (Linux; Android 14; MicroMessenger/8.0.49 WeChat/0.8.0 "
         "MiniProgramEnv/android; wkbrowser xweb)")
SCHOOL_EXPERT_CATEGORY = "16-BackToSchool"
SCHOOL_EXPERT_FALLBACK = {"expert-school-01": {"id": "expert-school-01", "name": "开学季助手", "profession": "教育"}}
LOTTERY_PRIZE_LABELS = {
    "school_credit_6": "6积分", "school_credit_66": "66积分",
    "school_voucher_luckin": "瑞幸咖啡15元券", "school_voucher_kfc_ok": "肯德基OK餐券",
    "school_voucher_kfc_ice": "肯德基冰淇淋券", "school_voucher_kugou": "酷狗会员月卡券",
}
# 学校活动任务：manual=人工跳过, report=遥测点亮, share=share-complete
SCHOOL_TASK_MODES = {
    "task_student_verify": {"mode": "manual", "note": "微信学生认证（人工）"},
    "share_invite": {"mode": "share", "note": "分享活动给好友"},
    "chat_3_times": {"mode": "report", "note": "与AI对话3次", "kind": "mini_chat"},
    "desktop_chat_1_time": {"mode": "report", "note": "桌面端对话1次", "kind": "desktop_seq"},
    "expert_use": {"mode": "report", "note": "召唤开学季专家并对话", "kind": "expert"},
}


def _school_session(at):
    """用现有 AT 创建 school 活动会话（小程序 UA + codebuddy 域）。"""
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"Authorization": "Bearer " + at, "Accept": "application/json",
                      "Content-Type": "application/json", "User-Agent": MP_UA,
                      "Referer": "https://www.codebuddy.cn/"})
    return s


def _school_get(s, url):
    return api_retry(s, "GET", url)


def _school_post(s, url, body=None):
    return api_retry(s, "POST", url, body=body)


def _school_report(s, uid, nick, events, host=None, desktop=False):
    """开学季事件上报。host 默认 codebuddy.cn；desktop=True 时走 copilot 域（桌面任务判据）。"""
    target = host or SCHOOL_DOMAIN
    if desktop:
        out = {"common": {"userId": uid, "userNickname": nick, "ideName": "WorkBuddy",
                          "ideType": "WorkBuddy", "machineId": derive_id(uid, "machine"),
                          "mode": "LOCAL", "userAgent": UA, "os": "win32",
                          "timezone": "Asia/Shanghai"},
               "events": events}
        return api_retry(s, "POST", "https://copilot.tencent.com/v2/report", body=out,
                         headers={"X-Product": "SaaS"})
    out = {"common": {"userId": uid, "userNickname": nick, "ideName": "web-Agents",
                      "ideType": "web-Agents", "machineId": derive_id(uid, "machine"), "mode": "CLOUD",
                      "userAgent": MP_UA, "os": "Android", "timezone": "Asia/Shanghai"},
           "events": events}
    return api_retry(s, "POST", target + "/v2/report", body=out)


def _school_fetch_expert(s):
    """拉取 BackToSchool 分类的真实专家（字段名对齐上游 school.fetch_school_expert）。"""
    body = {"edition_mode": "all,domestic", "page": 1, "page_size": 20,
            "sort_by": "use_count", "sort_order": "desc",
            "categories": [SCHOOL_EXPERT_CATEGORY], "expert_type": "agent"}
    try:
        r = _school_post(s, SCHOOL_DOMAIN + "/v2/operation-platform/market/expert/list", body)
        d = r.json()
        experts = (d.get("data") or {}).get("experts") or []
        for e in experts:
            eid = e.get("expert_id")          # ← 正确字段名（不是 "id"）
            if not eid:
                continue
            dn = e.get("display_name_zh") or {}
            name = (dn.get("zh") if isinstance(dn, dict) else dn) or eid
            return eid, name
    except Exception:
        pass
    for eid, info in SCHOOL_EXPERT_FALLBACK.items():
        return eid, info["name"]
    return "", ""


def _school_desktop_seq_event(uid, nick, conv_id):
    """模拟一次桌面对话的 6 连指纹事件 + activityId（走 desktop_chat_sequence 同款形状）。"""
    evs = desktop_chat_sequence(uid, nick, conv_id, conv_id, conv_id)
    fp = desktop_fingerprint(uid, nick)
    out = []
    for e in evs:
        m = dict(e)
        m.update(fp)
        m["activityId"] = SCHOOL_ACTIVITY_ID
        out.append(m)
    return out


def _school_expert_event(uid, nick, expert_id, expert_name, conv_id):
    """专家 4 事件链（含 activityId，开学季 expert_use 判据）。"""
    return mp_expert_use_events(uid, nick, expert_id, expert_name, conv_id,
                                activity_id=SCHOOL_ACTIVITY_ID)


def _school_fetch_tasks(s):
    r = _school_get(s, SCHOOL_BASE + "/tasks")
    d = r.json()
    if d.get("code") != 0:
        return [], False
    data = d.get("data") or {}
    return data.get("tasks") or [], data.get("in_period", False)


def _school_viewed(s, code):
    r = _school_post(s, SCHOOL_BASE + "/tasks/%s/viewed" % code)
    return r.json().get("code") == 0


def _school_share_complete(s):
    r = _school_post(s, SCHOOL_BASE + "/tasks/share-complete", {"channel": "wechat"})
    return r.json().get("code") == 0


def _school_claim(s, code):
    r = _school_post(s, SCHOOL_BASE + "/tasks/%s/claim" % code)
    return r.json().get("code") == 0


def school_run_tasks(s, uid, nick, log):
    """执行开学季任务的完整流程：viewed → 判据 → 轮询 → claim → 抽奖。"""
    tasks, in_period = _school_fetch_tasks(s)
    if not in_period:
        log("  🏫 开学季活动非进行期，跳过")
        return
    log("  🏫 ── 开学季活动（%d 个任务）──" % len(tasks))
    for t in tasks:
        code = t.get("task_code", "")
        status = t.get("status", "")
        spec = SCHOOL_TASK_MODES.get(code)
        if not code:
            continue
        if status == "claimed":
            log("   %s: 已领取，跳过" % code)
            continue
        if status == "completed":
            # 已完成未领奖 → 补领（此前误判为"跳过"，导致奖励漏领）
            if _school_claim(s, code):
                log("   %s: 🎁 补领奖成功" % code)
            else:
                log("   %s: 补领奖失败（可稍后重试）" % code)
            time.sleep(WRITE_GAP)
            continue
        if spec is None:
            log("   %s: 未知任务类型，跳过" % code)
            continue
        mode = spec["mode"]
        if mode == "manual":
            log("   %s: 人工环节（%s），跳过" % (code, spec.get("note", "")))
            continue
        # viewed 激活
        try:
            if _school_viewed(s, code):
                log("   %s: viewed 激活" % code)
                time.sleep(WRITE_GAP)
        except Exception as e:
            log("   %s: viewed 失败 %s" % (code, str(e)[:60]))
            continue
        # 判据
        ok = False
        if mode == "share":
            try:
                ok = _school_share_complete(s)
                log("   %s: share-complete %s" % (code, "✅" if ok else "❌"))
                time.sleep(WRITE_GAP)
            except Exception as e:
                log("   %s: share 失败 %s" % (code, str(e)[:60]))
        elif mode == "report":
            kind = spec.get("kind", "")
            conv_id = "conv-" + str(uuid.uuid4())
            if kind == "mini_chat":
                for i in range(3):
                    try:
                        mp_report(s, uid, nick, [mp_chat_event(
                            uid, nick, "wbsc-" + str(uuid.uuid4()),
                            activity_id=SCHOOL_ACTIVITY_ID)])
                        log("   %s: chat #%d/3 ✅" % (code, i + 1))
                        time.sleep(WRITE_GAP)
                    except Exception as e:
                        log("   %s: chat #%d 失败 %s" % (code, i + 1, str(e)[:60]))
            elif kind == "desktop_seq":
                evs = _school_desktop_seq_event(uid, nick, conv_id)
                try:
                    _school_report(s, uid, nick, evs, desktop=True)
                    log("   %s: desktop_seq (copilot域) ✅" % code)
                    time.sleep(WRITE_GAP)
                except Exception as e:
                    log("   %s: desktop 失败 %s" % (code, str(e)[:60]))
            elif kind == "expert":
                eid, ename = _school_fetch_expert(s)
                if not eid:
                    log("   %s: 未取到专家，跳过" % code)
                else:
                    try:
                        evs = _school_expert_event(uid, nick, eid, ename, conv_id)
                        mp_report(s, uid, nick, evs)
                        log("   %s: expert 4事件链 ✅ (%s)" % (code, ename))
                        time.sleep(WRITE_GAP)
                    except Exception as e:
                        log("   %s: expert 失败 %s" % (code, str(e)[:60]))
        # 轮询等待完成
        for _ in range(5):
            time.sleep(2)
            try:
                ts2, _ = _school_fetch_tasks(s)
                after = next((x for x in ts2 if x.get("task_code") == code), None)
                if after and after.get("status") in ("completed", "claimed"):
                    log("   %s: ✅ 已完成" % code)
                    break
            except Exception:
                pass
        # claim
        try:
            ts3, _ = _school_fetch_tasks(s)
            after = next((x for x in ts3 if x.get("task_code") == code), None)
            if after and after.get("status") == "completed":
                if _school_claim(s, code):
                    log("   %s: 🎁 已领奖" % code)
                    time.sleep(WRITE_GAP)
        except Exception as e:
            log("   %s: claim 失败 %s" % (code, str(e)[:60]))


def school_lottery(s, uid, nick, log):
    """开学季幸运大转盘：查余额 → 循环抽到 0。"""
    try:
        r = _school_get(s, SCHOOL_BASE + "/config")
        d = r.json()
        if d.get("code") != 0:
            log("  🏫 lottery config 失败")
            return
        chance = (d.get("data") or {}).get("chance") or {}
        bal = chance.get("balance", 0)
        if not bal or bal <= 0:
            log("  🏫 lottery 余额=0，无需抽奖")
            return
        log("  🏫 lottery 余额=%s，开始抽奖..." % bal)
        results = []
        while bal > 0:
            time.sleep(WRITE_GAP)
            draw_uuid = str(uuid.uuid4())
            try:
                r2 = _school_post(s, SCHOOL_BASE + "/wheel/draw", {"draw_uuid": draw_uuid})
                d2 = r2.json()
                if d2.get("code") == 40900:
                    log("  🏫 lottery 次数耗尽")
                    break
                if d2.get("code") != 0:
                    log("  🏫 lottery draw 失败: %s" % str(d2.get("msg", ""))[:60])
                    break
                prize = (d2.get("data") or {}).get("prize_code", "")
                credit = (d2.get("data") or {}).get("credit_amount", 0)
                label = LOTTERY_PRIZE_LABELS.get(prize, prize or "未知")
                results.append(label)
                bal -= 1
                log("  🏫 lottery → %s（余 %s）" % (label, bal))
            except Exception as e:
                log("  🏫 lottery draw 异常 %s" % str(e)[:60])
                break
        if results:
            log("  🏫 lottery 汇总: %d 抽，奖品: %s" % (len(results), ", ".join(results)))
    except Exception as e:
        log("  🏫 lottery 异常 %s" % str(e)[:80])


# ---------- 稳定指纹 & 事件构建（从 task_runner.py 移植） ----------
def derive_id(uid, salt):
    """由 uid 稳定派生 36 位 hex 设备标识（sha256[:18]，对齐上游 deriveID，幂等）。"""
    return hashlib.sha256(("%s:%s" % (salt, uid)).encode()).hexdigest()[:36]


def desktop_fingerprint(uid, nick):
    """公共桌面指纹（注入每个桌面事件，覆盖同名业务键）。"""
    now = int(time.time() * 1000)
    return {
        "timezone": "Asia/Shanghai", "reportDelay": 2000,
        "userId": uid, "username": nick, "userNickname": nick,
        "product": "SaaS", "releaseDate": 1789036585355,
        "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
        "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": "5.5.6",
        "machineId": derive_id(uid, "machine"), "sessionId": derive_id(uid, "session"),
        "extName": "workbuddy-desktop", "extVersion": "5.5.6",
        "os": "win32", "arch": "x64", "osVersion": "10.0.26220",
        "cpuCores": 20, "memorySize": 24,
        "timestamp": now, "presentAt": now,
    }


def within_night_window():
    """CST 夜猫窗口 23:00 - 次日 08:00"""
    try:
        return beijing_now().hour >= 23 or beijing_now().hour < 8
    except Exception:
        return None


def beijing_now():
    """北京时间（UTC+8）。不依赖系统 TZ：Actions runner 是 UTC，直接用会算错日期。"""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))


def beijing_today():
    """北京日期（date 对象）。补签等日期逻辑必须用它，不能用 date.today()。"""
    return beijing_now().date()


def desktop_chat_sequence(uid, nick, conversation_id, request_id, message_id,
                          model_id="fast-model", model_name="fast-model"):
    """6 连「桌面端成功对话」事件链（点亮 RichMeow_Chat）。"""
    now = int(time.time() * 1000)
    ev = []
    def mk(code, extra):
        e = {"eventCode": code}
        e.update(extra)
        ev.append(e)
    mk("agent_task_created", {
        "source": "LOCAL", "name": "working", "task_target": "local", "mode": "craft",
        "requestModelId": model_id, "requestModelName": model_name,
        "has_repo": False, "repo_type": "none", "workspace_type": "empty",
        "has_connector": False, "connector_types": [],
        "has_mention": False, "mention_types": [],
        "has_template": False, "action": "", "template_name": "",
        "has_expert": False, "expert_id": "", "expert_name": "", "expert_industry_id": "",
        "has_skill": False, "skill_names": [],
        "conversationId": conversation_id, "messageId": message_id,
        "buddyId": "", "buddyName": ""})
    mk("chat_message_send", {
        "messageId": message_id + "-assistant", "historyCount": 0,
        "isContextTruncated": False, "currentStepCount": 1,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_send", {
        "inputLength": 24, "isPlan": False, "isAutoExecuteTerminal": False,
        "isAutoModify": False, "codebaseEnable": False, "maxToken": 0,
        "maxSteps": 500, "temperature": 0, "maxRetries": 0,
        "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
        "codebaseId": "", "mentionContextCount": 0, "command": "",
        "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_response", {
        "messageId": message_id + "-assistant", "responseModelId": model_id,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "firstTokenAt": now, "traceId": request_id,
        "conversationId": conversation_id,
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_status", {
        "messageId": message_id + "-assistant", "messageErrorCode": "0",
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_response", {
        "mode": "craft", "toolCallCount": 0,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    return ev


def desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name):
    """五连「进入 Buddy 应用」事件（点亮 Buddy_App/_QQ）。"""
    ev = []
    def mk(code, extra):
        e = {"eventCode": code, "mode": "LOCAL",
             "buddyId": buddy_id, "buddyName": buddy_name}
        e.update(extra)
        ev.append(e)
    mk("buddyapp_discover_click", {})
    mk("buddyapp_show", {"elementId": buddy_id, "elementName": buddy_name, "position": 2})
    mk("buddyapp_enter_click",
       {"elementId": buddy_id, "elementName": buddy_name, "position": 2, "isFirstPage": "1"})
    mk("buddyapp_auth_confirm_click", {"elementId": buddy_id, "elementName": buddy_name})
    mk("buddyapp_bindaccount_skip_click", {"elementId": buddy_id, "elementName": buddy_name})
    return ev


DESKTOP_UA = "WorkBuddy/5.5.6 WorkBuddy/5.5.6 CLI/2.137.1"
DESKTOP_BASE = "https://copilot.tencent.com"


def report_desktop_events(s, uid, nick, events):
    """桌面指纹上报：copilot.tencent.com/v2/report，**裸数组** + 桌面头族。

    对齐上游 ReportDesktopEvent：desktopBase=chatBase(copilot 域)、body 为裸数组、
    头含 X-Domain/X-Product/X-Request-ID/X-User-Id + 桌面 UA。
    """
    fp = desktop_fingerprint(uid, nick)
    arr = []
    for e in events:
        m = dict(fp)          # 先铺指纹
        m.update(e)           # 业务字段优先（可覆盖同名设备键）
        arr.append(m)
    hdr = {"Authorization": s.headers.get("Authorization", ""),
           "Accept": "application/json, text/plain, */*",
           "Content-Type": "application/json;charset=UTF-8",
           "User-Agent": DESKTOP_UA,
           "X-Domain": DESKTOP_BASE, "X-Product": "SaaS",
           "X-Request-ID": derive_id(uid, "req") + str(int(time.time() * 1000) % 1000000)}
    if uid:
        hdr["X-User-Id"] = uid
    s2 = requests.Session(); s2.trust_env = False
    try:
        r = s2.post(DESKTOP_BASE + "/v2/report", json=arr, headers=hdr,
                    timeout=20, verify=False)
        return r.status_code
    except Exception:
        return 0


def report_web_event(s, uid, nick, event_code, page_url, element_id, element_name):
    """以 web 域指纹上报单事件（Library_read）。"""
    now = int(time.time() * 1000)
    ev = {"eventCode": event_code, "timestamp": now, "reportDelay": 0,
          "pageURL": page_url, "elementId": element_id, "elementName": element_name,
          "os": "Win32", "arch": "", "osVersion": "10.0",
          "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "machineId": derive_id(uid, "webmachine"), "userId": uid, "userNickname": nick}
    return api_retry(s, "POST", BASE + "/v2/report", body={"common": {
        "userId": uid, "userNickname": nick, "ideName": "web",
        "ideType": "web", "machineId": derive_id(uid, "webmachine"),
        "mode": "CLOUD", "userAgent": "Mozilla/5.0", "os": "Win32",
        "timezone": "Asia/Shanghai"}, "events": [ev]})


def _accept_with_verify(s, code, log):
    """accept 并验证登记生效（读 results[].status + 回读 accept_status）。"""
    for attempt in (1, 2):
        r = s.post(BASE + "/v2/activity/growth/tasks/accept", json={"task_codes": [code]},
                   timeout=20, verify=False)
        status = ""
        try:
            d = r.json()
            results = (d.get("data") or {}).get("results") or []
            status = (results[0].get("status") or "") if results else (d.get("msg") or "")
        except Exception:
            pass
        t = prog(s, code)
        ast = t[0] if t else "not_accepted"
        ok = (r.status_code == 200 and status == "accepted" and ast != "not_accepted")
        if ok:
            return True
        if attempt > 1:
            log("      ✗ %s: accept %s 回读=%s" % (code, status or "无返回", ast))
        time.sleep(WRITE_GAP)
    return False


# ---------- 单账号全流程 ----------
def run_account(idx, acc, do_desktop):
    msgs = []
    tag = "账号%d" % idx
    def log(m):
        ts = time.strftime("%H:%M:%S")
        line = "[%s][%s] %s" % (ts, tag, m)
        print(line)
        msgs.append(line)

    summary = {"idx": idx, "note": acc.get("note", ""), "credits": "", "usage": "", "growth": "",
               "done": 0, "total": 0, "rest": [], "level": "?", "energy": "?"}
    tok = acc.get("access_token", "")
    if not tok:
        log("")
        log("╭─ 👤 账号%d  %s" % (idx, acc.get("note", "")))
        log("  ❌ AT 为空（续期失败或凭据缺失），跳过此账号")
        return msgs, {"idx": idx, "note": acc.get("note", ""), "done": 0, "total": 0,
                      "rest": ["凭据缺失"], "level": "?", "energy": "?"}
    uid = uid_of(tok)
    nick = nickname_of(tok)
    s = new_api(tok)

    log("")
    log("╭─ 👤 账号%d  %s" % (idx, acc.get("note", "")))
    # 查询
    credits, paid = queryCredits(s)
    usage = queryUsage(s)
    rp = s.get(BASE + "/v2/activity/growth/profile", timeout=25, verify=False)
    pj = _json_or_empty(rp)
    if rp.status_code in (401, 403) or not pj:
        log("  ❌ 凭据失效（HTTP %s）：AT/RT 已过期或被轮换 —— 请重新登录桌面端，或用 workbuddy_login.py" % rp.status_code)
        log("     重新获取一行「手机号:AT:RT」后更新变量，本账号本次跳过（不影响其他账号）")
        return msgs, {"idx": idx, "note": acc.get("note", ""), "done": 0, "total": 0,
                      "rest": ["凭据失效"], "level": "?", "energy": "?"}
    prof = pj.get("data", {}) or {}
    energy = (_json_or_empty(s.get(BASE + "/v2/activity/growth/energy", timeout=25,
                                            verify=False)).get("data") or {}).get("balance")
    streak = ((_json_or_empty(s.get(BASE + "/v2/activity/growth/streak", timeout=25,
                                             verify=False)).get("data") or {}).get("streak") or {})
    summary["credits"] = credits
    summary["usage"] = usage
    summary["streak"] = streak.get("days", "?")
    summary["signed"] = "✅" if "已签到" in (credits + "") or True else "❌"
    log("💰 积分: %s" % credits)
    log("📊 用量: %s" % usage)
    try:
        hm = s.get(BASE + "/v2/activity/growth/heatmap", timeout=20, verify=False).json()
        cells = hm.get("data", {}).get("cells", [])
        signed = sum(1 for c in cells if isinstance(c, dict) and c.get("score", 0) > 0)
    except Exception:
        signed = "?"
    log("🌱 成长: 等级%s 连签%s天 能量%s 累签%s天" % (prof.get("level", "?"), streak.get("days", "?"), energy, signed))
    if QUERY_ONLY:
        return msgs, {"idx": idx, "note": acc.get("note", ""), "done": 0, "total": 0, "rest": [], "level": "?", "energy": "?"}
    # 桌面任务先做（新账号必须先有真实桌面会话，否则接受会被回滚、遥测不计数）
    need_rich = prog(s, "RichMeow_Chat")[0] not in ("completed", "claimed")
    need_skill = prog(s, "skill_1")[0] not in ("completed", "claimed")
    if do_desktop and (need_rich or need_skill):
        log("  🖥️ ── 桌面任务（引导优先） ──")
        t_desktop_tasks(s, uid, nick, tok, log, need_rich, need_skill)
    elif need_rich or need_skill:
        log("── 桌面任务跳过(--no-desktop): RichMeow=%s skill_1=%s ──" % (need_rich, need_skill))
    else:
        log("  🖥️ 桌面任务: 已完成（RichMeow/skill_1），跳过")
    # 任务
    log("  ☁️ ── 云端任务 ──")
    # 前置：无 Buddy 实例时，其余任务 accept 会被服务端拒绝（prerequisite not met: first_buddy）
    t_first_buddy(s, uid, nick, log)
    t_accept_all(s, uid, nick, log)
    t_sign(s, uid, nick, log)
    t_team_3(s, uid, nick, log)
    t_buddy_apps(s, uid, nick, log)
    t_theme(s, uid, nick, log)
    t_library(s, uid, nick, log)
    t_canvas_automation(s, uid, nick, log)
    t_expert_5(s, uid, nick, log)
    t_template_5(s, uid, nick, log)
    t_glm52(s, uid, nick, log)
    t_black_cat(s, uid, nick, log)
    t_lighthouse(s, uid, nick, log)
    t_sequential_tasks(s, uid, nick, log)
    t_sequential_tasks_2(s, uid, nick, log)
    t_sequential_tasks_3(s, uid, nick, log)
    t_sequential_tasks_4(s, uid, nick, log)
    t_sequential_tasks_5(s, uid, nick, log)
    t_sequential_tasks_6(s, uid, nick, log)
    t_sequential_tasks_7(s, uid, nick, log)
    t_school_season(s, uid, nick, log)
    t_badges(s, uid, nick, log)
    t_lottery(s, uid, nick, log)
    t_blindbox(s, uid, nick, log)
    t_buddy_info(s, uid, nick, log)
    t_travel(s, uid, nick, log)
    t_redeem(s, uid, nick, log, streak.get("days"))
    t_gift_compensation(s, uid, nick, log)
    t_makeup(s, uid, nick, log)
    t_workstation(s, uid, nick, log, tok)
    t_unknown_tasks(s, uid, nick, log)
    # 开学季活动（可 --no-school 跳过）
    if not NO_SCHOOL:
        try:
            school_s = _school_session(tok)
            school_run_tasks(school_s, uid, nick, log)
            school_lottery(school_s, uid, nick, log)
        except Exception as e:
            log("  🏫 开学季活动异常: %s" % str(e)[:80])
    # 领奖
    log("  🎁 ── 领奖 ──")
    r = s.get(BASE + "/v2/activity/growth/tasks", timeout=25, verify=False).json()
    n = 0
    for t in r.get("data", {}).get("tasks", []):
        if isinstance(t, dict) and t.get("accept_status") == "completed":
            claim(s, t.get("task_code", ""), log)
            n += 1
            time.sleep(1)
    if n == 0:
        log("   无待领奖励")
    # 终态
    st_all = (_json_or_empty(s.get(BASE + "/v2/activity/growth/tasks", timeout=25,
                                      verify=False)).get("data") or {}).get("tasks", [])
    done = sum(1 for t in st_all if isinstance(t, dict) and t.get("accept_status") in ("claimed", "completed"))
    rest = [task_cn(t.get("task_code","")) for t in st_all if isinstance(t, dict) and t.get("accept_status") not in ("claimed", "completed")]
    prof2 = (_json_or_empty(s.get(BASE + "/v2/activity/growth/profile", timeout=25,
                                       verify=False)).get("data") or {})
    summary.update({"done": done, "total": len(st_all), "rest": rest,
                    "level": prof2.get("level", "?"), "energy": energy})
    log("🏁 %s: 完成%s/%s 等级%s 剩余: %s" % (acc.get("note", ""), done, len(st_all), prof2.get("level", "?"),
                                             ", ".join(rest) if rest else "无"))
    return msgs, summary



# ---------- 推送摘要（精简版，避免超长截断） ----------
def build_summary(summaries):
    """每个账号详细中文报告 + 总计统计"""
    summaries.sort(key=lambda x: x.get("idx", 0))
    total_done = total_tasks = 0
    lines = []
    lines.append("📊 各账号运行报告")
    lines.append("")

    for sm in summaries:
        idx = sm.get("idx", 0)
        done = sm.get("done", 0)
        total = sm.get("total", 0)
        total_done += done
        total_tasks += total
        credits = sm.get("credits", "")
        usage = sm.get("usage", "")
        energy = sm.get("energy", "?")
        level = sm.get("level", "?")
        streak = sm.get("streak", "?")
        note = sm.get("note", "")[:16]
        rest = sm.get("rest") or []
        # 翻译任务代码为中文
        rest_cn = [task_cn(r) for r in rest]

        lines.append("👤 账号%d  %s" % (idx, note))
        lines.append("   💰 %s" % (credits if credits else "暂无数据"))
        lines.append("   📊 %s" % (usage if usage else "暂无数据"))
        lines.append("   🌱 等级%s | 连签%s天 | 能量%s" % (level, streak, energy))
        if rest_cn:
            lines.append("   ⏳ 未完成: %s" % "、".join(rest_cn))
        else:
            lines.append("   ✅ 全部完成！")
        lines.append("")

    lines.append("📊 ══ 总计 ══")
    lines.append("👥 共%d个账号，任务完成 %d/%d 项" % (len(summaries), total_done, total_tasks))

    # 汇总待办分布（中文）
    all_rest = {}
    for sm in summaries:
        for r in (sm.get("rest") or []):
            cn = task_cn(r)
            all_rest[cn] = all_rest.get(cn, 0) + 1
    if all_rest:
        lines.append("")
        for cn, cnt in sorted(all_rest.items(), key=lambda x: -x[1]):
            lines.append("   · %s（%d个账号待完成）" % (cn, cnt))

    lines.append("")
    lines.append("🕐 %s" % time.strftime("%Y-%m-%d %H:%M"))
    return chr(10).join(lines)


# ---------- 推送通知（内置 PushPlus + Bark，无需外部模块） ----------
def _wecom_notify(title, content):
    """企业微信群机器人推送；未配置 WECOM_WEBHOOK 则跳过。

    WECOM_WEBHOOK 支持两种形态：
      · 完整 webhook URL：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
      · 仅 key：xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx（自动补全 URL）
    企业微信 text 消息上限 2048 字节，超长自动截断。
    """
    raw = os.environ.get("WECOM_WEBHOOK", "").strip()
    if not raw:
        return False
    url = raw if raw.startswith("http") else (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + raw)
    msg = "%s\n%s" % (title, content)
    if len(msg.encode("utf-8")) > 2000:
        msg = msg.encode("utf-8")[:1900].decode("utf-8", "ignore") + "\n...(内容过长已截断)"
    try:
        s = requests.Session(); s.trust_env = False
        r = s.post(url, json={"msgtype": "text", "text": {"content": msg}},
                   timeout=20, verify=False)
        d = r.json()
        if d.get("errcode") == 0:
            print("📢 企业微信推送成功")
            return True
        print("📢 企业微信推送失败: %s" % str(d.get("errmsg", ""))[:80])
    except Exception as e:
        print("📢 企业微信异常: %s" % str(e)[:80])
    return False


def _bark_notify(title, content):
    """Bark 推送（iOS）；未配置 BARK_URL 则跳过。直接 POST 到 BARK_URL（/:device_key 路由），
    不加 /push 后缀——bark-server 会把 URL 路径第二段解析为 body 参数覆盖 JSON。"""
    url = os.environ.get("BARK_URL", "").strip().rstrip("/")
    if not url:
        return False
    try:
        s = requests.Session(); s.trust_env = False
        r = s.post(url, json={"title": title, "body": content, "group": "WorkBuddy"},
                   timeout=20, verify=False)
        d = r.json()
        if d.get("code") == 200:
            print("📢 Bark 推送成功")
            return True
        print("📢 Bark 推送失败: %s" % str(d.get("message", ""))[:80])
    except Exception as e:
        print("📢 Bark 异常: %s" % str(e)[:80])
    return False


def send_notify(title, content):
    """PushPlus 推送；未配置 PUSHPLUS_TOKEN 则跳过"""
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        return False
    # 内容过长时截断（PushPlus 上限约 2 万字）
    if len(content) > 18000:
        content = content[:18000] + "\n...(内容过长已截断)"
    try:
        s = requests.Session(); s.trust_env = False
        r = s.post("https://www.pushplus.plus/send",
                   json={"token": token, "title": title, "content": content, "template": "txt"},
                   timeout=20, verify=False)
        d = r.json()
        if d.get("code") == 200:
            print("📢 推送成功")
            return True
        print("📢 推送失败: %s" % str(d.get("msg", ""))[:80])
    except Exception as e:
        print("📢 推送异常: %s" % str(e)[:80])
    return False


def send_notify_all(title, content):
    """推送通知到所有已配置的渠道（PushPlus + Bark + 企业微信）。"""
    r1 = send_notify(title, content)
    r2 = _bark_notify(title, content)
    r3 = _wecom_notify(title, content)
    return r1 or r2 or r3


def main():
    if "--refresh" in sys.argv:
        print("╔═══════════════════════════════════╗")
        print("║ 🔐 WorkBuddy Token 续期工具       ║")
        print("╚═══════════════════════════════════╝")
        updated = refresh_all()
        if updated:
            print("✅ 共续期 %d 个账号: %s" % (len(updated), ", ".join(updated.keys())))
        else:
            print("⚠️ 无账号续期（检查 wb_refresh_tokens.json 是否存在）")
        print("📄 WORKBUDDY_ACCESS_TOKEN.txt 已同步更新")
        return
    print("╔════════════════════════════════════════╗")
    print("║ 🌱 WorkBuddy 全能脚本                  ║")
    print("║ 🔐续期 💰积分 📊用量 🌱成长            ║")
    print("║ ✅任务 🎮玩法 🎁领奖 📢推送            ║")
    print("╚════════════════════════════════════════╝")
    print("👥 账号数: %d" % len(ACCOUNTS))
    do_desktop = not NO_DESKTOP
    if do_desktop and sys.platform != "win32":
        print("🖥️ 非Windows环境：桌面任务自动降级为指纹上报模式")
    all_msgs = []
    summaries = []
    if SCHOOL_ONLY:
        do_desktop = False
        for i, acc in enumerate(ACCOUNTS):
            tok = acc.get("access_token", "")
            if not tok:
                print("❌ 账号%d AT 为空，跳过" % (i + 1))
                continue
            uid = uid_of(tok); nick = nickname_of(tok)
            s2 = _school_session(tok)
            print("╭─ 👤 账号%d  %s [school-only]" % (i + 1, acc.get("note", "")))
            _tag = "账号%d" % (i + 1)
            def _slog(m, _tag=_tag):
                print("[%s][%s] %s" % (time.strftime("%H:%M:%S"), _tag, m))
            try:
                school_run_tasks(s2, uid, nick, _slog)
                school_lottery(s2, uid, nick, _slog)
            except Exception as e:
                print("  ❌ 开学季异常: %s" % str(e)[:80])
            time.sleep(WRITE_GAP)
        return
    if QUERY_ONLY:
        with ThreadPoolExecutor(max_workers=min(6, len(ACCOUNTS))) as ex:
            futs = {ex.submit(run_account, i + 1, acc, False): i for i, acc in enumerate(ACCOUNTS)}
            for f in as_completed(futs):
                try:
                    msgs_part, sm = f.result()
                except Exception as e:      # 单账号异常不拖垮整个查询
                    i = futs[f]
                    msgs_part = ["[%s][账号%d] ❌ 查询异常: %s" % (time.strftime("%H:%M:%S"), i + 1, str(e)[:120])]
                    print(msgs_part[0])
                    sm = {"idx": i + 1, "note": ACCOUNTS[i].get("note", ""), "done": 0, "total": 0,
                          "rest": ["异常中断"], "level": "?", "energy": "?"}
                all_msgs.extend(msgs_part)
                summaries.append(sm)
    else:
        # 云端任务并发，桌面任务串行
        for i, acc in enumerate(ACCOUNTS):
            try:
                msgs_part, sm = run_account(i + 1, acc, do_desktop)
            except Exception as e:      # 单账号异常不拖垮后续账号（issue #12/#13）
                msgs_part = ["[%s][账号%d] ❌ 本账号异常已跳过（不影响其他账号）: %s"
                             % (time.strftime("%H:%M:%S"), i + 1, str(e)[:140])]
                print(msgs_part[0])
                sm = {"idx": i + 1, "note": acc.get("note", ""), "done": 0, "total": 0,
                      "rest": ["异常中断"], "level": "?", "energy": "?"}
            all_msgs.extend(msgs_part)
            summaries.append(sm)
            time.sleep(2)
    # 推送摘要（完整日志见青龙日志/控制台）
    send_notify_all("🌱 WorkBuddy 签到报告", build_summary(summaries))


from concurrent.futures import ThreadPoolExecutor, as_completed

if __name__ == "__main__":
    main()
