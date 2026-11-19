/**
 * MiniMax Agent网页每日签到 - 青龙面板脚本
 * @see https://gh-proxy.org/github.com/lxpkwwz/ql_scripts/raw/refs/heads/main/minimax_checkin.js
 *
 * cron: 38 7 * * *
 * new Env('MiniMax Agent网页版每日签到')
 *
 * 必填环境变量：
 *   MINIMAX_SIGNIN_URL   完整签到领取 URL。访问 https://agent.minimax.cn 并登录，打开浏览器 F12，然后点击左下角的 签到 按钮，从 network 请求中过滤 /minimax-cloud/v1/signin/clami 的请求 URL
 *
 * 累计签到积分余额变量：
 *   MINIMAX_BALANCE_URL  完整成员资格请求 URL，路径必须为 /matrix/api/v1/commerce/get_membership_info。
 *
 * 可选环境变量：
 *   MINIMAX_WEB_COOKIE    同一网页登录会话的完整 Cookie；接口要求时填写。
 *   MINIMAX_BALANCE_QUERY  默认 1；设为 0 时不查询累计签到积分余额。
 *   MINIMAX_NOTIFY        默认启用青龙 sendNotify；设置为 0 可关闭通知。
 *   MINIMAX_DEBUG         设置为 1 才输出脱敏后的请求与签名调试信息。
 *   MINIMAX_DRY_RUN       设置为 1 时仅校验配置与动态签名，不发送请求也不通知。
 */

'use strict';

const crypto = require('node:crypto');
const https = require('node:https');
const path = require('node:path');

const API_ORIGIN = 'https://agent.minimaxi.cn';
const ALLOWED_ORIGINS = new Set([
  'https://agent.minimaxi.com',
  'https://agent.minimax.cn',
]);
const CLAIM_PATH = '/minimax-cloud/api/v1/signin/claim';
const CLAIM_ENDPOINT = `${API_ORIGIN}${CLAIM_PATH}`;
const MEMBERSHIP_PATH = '/matrix/api/v1/commerce/get_membership_info';
const MEMBERSHIP_ENDPOINT = `${API_ORIGIN}${MEMBERSHIP_PATH}`;
const SIGNATURE_SALT = 'I*7Cf%WZ#S&%1RlZJ&C2';
const YY_SUFFIX = 'ooui';
const REQUEST_BODY = '{}';
const TIMEOUT_MS = 15000;
const NOTIFY_TITLE = 'MiniMax 网页签到';

function md5(value) {
  return crypto.createHash('md5').update(String(value), 'utf8').digest('hex');
}

function mask(value) {
  if (!value) return '<未设置>';
  const text = String(value);
  return text.length <= 8 ? '<已设置>' : `${text.slice(0, 5)}***${text.slice(-4)}`;
}

function decodeJwtPayload(token) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) throw new Error('token 不是三段式 JWT。请从网页请求中重新复制完整链接。');
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(Buffer.from(base64, 'base64').toString('utf8'));
  } catch {
    throw new Error('无法读取 token 的 JWT payload。请从最新网页请求中重新复制完整链接。');
  }
}

function assertLiveToken(token) {
  const payload = decodeJwtPayload(token);
  if (Number.isFinite(payload.exp) && payload.exp <= Math.floor(Date.now() / 1000)) {
    throw new Error('token 已过期。请在 MiniMax 网页端重新登录，再复制新的完整请求链接。');
  }
  return payload;
}

function cleanPastedUrl(rawUrl) {
  let value = String(rawUrl || '').replace(/^\uFEFF/, '').trim();
  // 兼容从青龙变量或聊天窗口复制时附带的外层引号、反引号和换行。
  if ((value.startsWith('\"') && value.endsWith('\"')) ||
      (value.startsWith("'") && value.endsWith("'")) ||
      (value.startsWith('`') && value.endsWith('`'))) {
    value = value.slice(1, -1).trim();
  }
  return value.replace(/[\r\n\t]/g, '');
}

function parseRequestUrl(rawUrl, expectedPath, label, acceptedPaths = []) {
  let url;
  try {
    url = new URL(cleanPastedUrl(rawUrl));
  } catch {
    throw new Error(`${label} 不是有效的完整 URL。${rawUrl}`);
  }
  if (url.protocol !== 'https:' || !ALLOWED_ORIGINS.has(url.origin) ||
      (url.pathname !== expectedPath && !acceptedPaths.includes(url.pathname))) {
    throw new Error(`${label} 必须是 agent.minimax.cn 或 agent.minimaxi.com 域名下的完整请求链接，路径应为 ${expectedPath}。`);
  }
  return url;
}

function parseSigninUrl(rawUrl) {
  const url = parseRequestUrl(rawUrl, CLAIM_PATH, 'MINIMAX_SIGNIN_URL', [
    '/minimax-cloud/api/v1/signin/config',
    '/minimax-cloud/api/v1/signin/status',
  ]);
  // config/status 只作为参数来源，真正执行动作必须调用 claim。
  if (url.pathname !== CLAIM_PATH) url.pathname = CLAIM_PATH;
  const token = String(url.searchParams.get('token') || '').trim();
  const uuid = String(url.searchParams.get('uuid') || '').trim();
  const deviceId = String(url.searchParams.get('device_id') || '').trim();
  const userId = String(url.searchParams.get('user_id') || '').trim();
  if (!token || !uuid || !deviceId || !userId) {
    throw new Error('MINIMAX_SIGNIN_URL 缺少 token、uuid、device_id 或 user_id；请重新复制点击签到按钮产生的完整请求链接。');
  }
  const payload = assertLiveToken(token);
  return {
    url: url.toString(),
    token,
    uuid,
    deviceId,
    userId,
    expiresAt: Number.isFinite(payload.exp)
      ? new Date(payload.exp * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
      : '未知',
  };
}

function parseMembershipUrl(rawUrl, fallbackToken) {
  const url = parseRequestUrl(rawUrl, MEMBERSHIP_PATH, 'MINIMAX_BALANCE_URL');
  const token = String(url.searchParams.get('token') || fallbackToken || '').trim();
  if (!token) throw new Error('MINIMAX_BALANCE_URL 缺少 token，且无法从 MINIMAX_SIGNIN_URL 复用 token。');
  assertLiveToken(token);
  return { url: url.toString(), token };
}

function resolveConfig(env = process.env) {
  const signin = parseSigninUrl(env.MINIMAX_SIGNIN_URL);
  const rawBalanceUrl = String(env.MINIMAX_BALANCE_URL || '').trim();
  const balanceQueryRequested = String(env.MINIMAX_BALANCE_QUERY || '1') !== '0';
  // 默认从签到 URL 派生余额接口：保留域名、token、设备和用户参数，只替换接口路径。
  // MINIMAX_BALANCE_URL 仍兼容作为高级用户的可选覆盖项。
  const derivedBalanceUrl = new URL(signin.url);
  derivedBalanceUrl.pathname = MEMBERSHIP_PATH;
  const membership = balanceQueryRequested
    ? parseMembershipUrl(rawBalanceUrl || derivedBalanceUrl.toString(), signin.token)
    : null;
  return {
    ...signin,
    membership,
    cookie: String(env.MINIMAX_WEB_COOKIE || '').trim(),
    balanceQuery: balanceQueryRequested && Boolean(membership),
    balanceSkipReason: !balanceQueryRequested ? '已关闭余额查询' : '',
    notify: String(env.MINIMAX_NOTIFY || '1') !== '0',
    debug: String(env.MINIMAX_DEBUG || '') === '1',
    dryRun: String(env.MINIMAX_DRY_RUN || '') === '1',
    userAgent: String(env.MINIMAX_USER_AGENT || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0').trim(),
  };
}

function baseHeaders(config, token, origin = API_ORIGIN) {
  const headers = {
    Accept: 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cache-Control': 'no-cache',
    DNT: '1',
    Origin: origin,
    Pragma: 'no-cache',
    Referer: `${API_ORIGIN}/`,
    'Sec-CH-UA': '"Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"',
    'Sec-CH-UA-Mobile': '?0',
    'Sec-CH-UA-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
    token,
    'User-Agent': config.userAgent,
  };
  if (config.cookie) headers.Cookie = config.cookie;
  return headers;
}

function signRequestHeaders(config, url, method, body, nowMs, token) {
  const nowSeconds = Math.floor(nowMs / 1000);
  const hasSearchParamsPath = `${url.pathname}${url.search || ''}`;
  const yyBody = method === 'POST' ? (body || '{}') : '{}';
  const signatureBody = method === 'POST' ? (body || '{}') : '';
  return {
    ...baseHeaders(config, token, url.origin),
    'x-timestamp': String(nowSeconds),
    'x-signature': md5(`${nowSeconds}${SIGNATURE_SALT}${signatureBody}`),
    yy: md5(`${encodeURIComponent(hasSearchParamsPath)}_${yyBody}${md5(String(nowMs))}${YY_SUFFIX}`),
  };
}

function buildSigninRequest(config, nowMs = Date.now()) {
  const url = new URL(config.url);
  url.searchParams.set('unix', String(nowMs));
  const headers = {
    ...signRequestHeaders(config, url, 'POST', REQUEST_BODY, nowMs, config.token),
    'Content-Type': 'application/json',
    'Content-Length': String(Buffer.byteLength(REQUEST_BODY)),
  };
  return { method: 'POST', url, headers, body: REQUEST_BODY, nowSeconds: Math.floor(nowMs / 1000) };
}

function buildMembershipRequest(config, nowMs = Date.now()) {
  if (!config.membership) return null;
  // 独立链接中的设备、屏幕和认证查询参数必须原样保留，只刷新时间戳。
  const url = new URL(config.membership.url);
  url.searchParams.set('unix', String(nowMs));
  const headers = {
    ...signRequestHeaders(config, url, 'POST', REQUEST_BODY, nowMs, config.membership.token),
    'Content-Type': 'application/json',
    'Content-Length': String(Buffer.byteLength(REQUEST_BODY)),
  };
  return { method: 'POST', url, headers, body: REQUEST_BODY, nowSeconds: Math.floor(nowMs / 1000) };
}

function request({ method, url, headers, body }) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, { method, headers, timeout: TIMEOUT_MS }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve({ statusCode: res.statusCode || 0, body: Buffer.concat(chunks).toString('utf8') }));
    });
    req.on('timeout', () => req.destroy(new Error(`请求超时（${TIMEOUT_MS}ms）`)));
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

function parseJson(text) {
  try { return JSON.parse(text); } catch { return null; }
}

function formatDate(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return new Date(ms).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
}

function compact(value, limit = 1200) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit)}…（已截断）` : (text || '<空响应>');
}

function judgeSignin(response) {
  const parsed = parseJson(response.body);
  const data = parsed?.data;
  const statusCode = parsed?.base_resp?.status_code;
  const statusMessage = parsed?.base_resp?.status_msg;
  if (response.statusCode < 200 || response.statusCode >= 300) {
    return { ok: false, state: '失败', detail: `HTTP ${response.statusCode}：${compact(response.body)}`, summary: {} };
  }
  if (typeof statusCode === 'number' && statusCode !== 0) {
    return { ok: false, state: '失败', detail: statusMessage || `业务状态码 ${statusCode}`, summary: {} };
  }
  const panelDays = Array.isArray(data?.panel?.days) ? data.panel.days : [];
  const summary = {
    points: Number.isFinite(data?.points) ? data.points : null,
    dayNo: Number.isInteger(data?.day_no) ? data.day_no : null,
    cycleLength: panelDays.length || 7,
    expireAt: Number.isFinite(data?.expire_at_ms) ? formatDate(data.expire_at_ms) : null,
    claimResult: Number.isInteger(data?.claim_result) ? data.claim_result : null,
    balance: null,
  };
  if (summary.claimResult === 2) return { ok: true, state: '已签到', detail: '今天已领取签到积分。', summary };
  if (summary.claimResult === 1) return { ok: true, state: '签到成功', detail: '本次签到积分领取成功。', summary };
  if (/已签到|已经签到|重复签到|already\s*(signed|checked|check-?in)/i.test(response.body || '')) {
    return { ok: true, state: '已签到', detail: '今天已领取签到积分。', summary };
  }
  if (statusCode === 0) return { ok: false, state: '待确认', detail: '业务请求成功，但 claim_result 未识别。', summary };
  return { ok: false, state: '待确认', detail: `HTTP ${response.statusCode}，无法确认签到结果：${compact(response.body)}`, summary };
}

function parseMembershipBalance(response) {
  if (response.statusCode < 200 || response.statusCode >= 300) return { available: false, reason: `积分余额接口 HTTP ${response.statusCode}` };
  const parsed = parseJson(response.body);
  if (!parsed) return { available: false, reason: '积分余额接口返回非 JSON 数据' };
  if (typeof parsed?.base_resp?.status_code === 'number' && parsed.base_resp.status_code !== 0) {
    return { available: false, reason: parsed.base_resp.status_msg || `积分余额业务状态码 ${parsed.base_resp.status_code}` };
  }
  const rawBalance = parsed?.op_credit_summary?.total_remaining_amount;
  if (rawBalance === undefined || rawBalance === null || rawBalance === '') {
    return { available: false, reason: '积分余额接口未提供 op_credit_summary.total_remaining_amount' };
  }
  return { available: true, balance: String(rawBalance) };
}

async function appendSigninBalance(result, config) {
  if (!config.balanceQuery) {
    result.summary.balance = { available: false, reason: config.balanceSkipReason || '未配置余额查询' };
    return;
  }
  try {
    result.summary.balance = parseMembershipBalance(await request(buildMembershipRequest(config)));
  } catch (error) {
    result.summary.balance = { available: false, reason: `积分余额查询失败：${error.message}` };
  }
}

function formatResult(result) {
  const summary = result.summary || {};
  const lines = [`状态：${result.state}`];
  if (summary.dayNo) lines.push(`本轮签到：第 ${summary.dayNo}/${summary.cycleLength || 7} 次`);
  if (summary.points !== null && summary.points !== undefined) lines.push(`本轮奖励：${summary.points} 积分`);
  if (summary.expireAt) lines.push(`本次签到积分到期：${summary.expireAt}`);
  if (summary.balance?.available) lines.push(`签到积分累计余额：${summary.balance.balance}`);
  else if (summary.balance?.reason) {
    lines.push('签到积分累计余额：未查询');
    lines.push(`提示：${summary.balance.reason}`);
  }
  if (!result.ok || result.state === '待确认') lines.push(`说明：${result.detail}`);
  return lines.join('\n');
}

function loadSendNotify() {
  const candidates = [path.resolve(__dirname, 'sendNotify'), path.resolve(__dirname, '../sendNotify'), '/ql/data/scripts/sendNotify', '/ql/scripts/sendNotify'];
  for (const candidate of candidates) {
    try {
      const module = require(candidate);
      const send = typeof module === 'function' ? module : module?.sendNotify;
      if (typeof send === 'function') return send;
    } catch (error) {
      if (error?.code !== 'MODULE_NOT_FOUND') continue;
    }
  }
  return null;
}

async function sendQlNotification(result, config) {
  if (!config.notify || config.dryRun) return false;
  const sendNotify = loadSendNotify();
  if (!sendNotify) {
    if (config.debug) console.log('[调试] 未加载到青龙 sendNotify，已跳过通知。');
    return false;
  }
  try { await sendNotify(NOTIFY_TITLE, formatResult(result)); return true; }
  catch (error) { if (config.debug) console.log(`[调试] 青龙通知发送失败：${error.message}`); return false; }
}

function logDebug(config, signinRequest, membershipRequest) {
  if (!config.debug) return;
  console.log(`签到端点：${signinRequest.url.origin}${signinRequest.url.pathname}`);
  console.log(`积分余额端点：${membershipRequest ? `${membershipRequest.url.origin}${membershipRequest.url.pathname}` : '<未设置>'}`);
  console.log(`用户 ID：${mask(config.userId)}；UUID：${mask(config.uuid)}；设备 ID：${mask(config.deviceId)}`);
  console.log(`Token：${mask(config.token)}；Cookie：${config.cookie ? '<已设置>' : '<未设置>'}；Token 到期：${config.expiresAt}`);
  console.log(`签到签名：x-timestamp=${signinRequest.nowSeconds}；x-signature=${mask(signinRequest.headers['x-signature'])}；yy=${mask(signinRequest.headers.yy)}`);
}

async function main() {
  const config = resolveConfig();
  const signinRequest = buildSigninRequest(config);
  const membershipRequest = buildMembershipRequest(config);
  logDebug(config, signinRequest, membershipRequest);
  if (config.dryRun) {
    console.log('[MiniMax] DRY RUN：环境变量与动态签名校验通过，未执行请求。');
    return;
  }
  const result = judgeSignin(await request(signinRequest));
  await appendSigninBalance(result, config);
  console.log(`[MiniMax] 签到摘要\n${formatResult(result)}`);
  await sendQlNotification(result, config);
  if (!result.ok) process.exitCode = 1;
}

if (require.main === module) {
  main().catch(async (error) => {
    const message = error?.message || String(error);
    console.error(`[MiniMax] 失败：${message}`);
    // resolveConfig、JWT 校验等配置阶段错误也必须通知，不能只写日志。
    const fallbackConfig = {
      notify: String(process.env.MINIMAX_NOTIFY || '1') !== '0',
      dryRun: String(process.env.MINIMAX_DRY_RUN || '') === '1',
      debug: String(process.env.MINIMAX_DEBUG || '') === '1',
    };
    await sendQlNotification({ ok: false, state: '失败', detail: message, summary: {} }, fallbackConfig);
    process.exitCode = 1;
  });
}

module.exports = {
  md5, decodeJwtPayload, cleanPastedUrl, parseRequestUrl, parseSigninUrl, parseMembershipUrl, resolveConfig,
  buildSigninRequest, buildMembershipRequest, judgeSignin, parseMembershipBalance, formatResult,
};