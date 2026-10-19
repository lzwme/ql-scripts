/*
 * @Author: renxia
 * @Date: 2026-10-19 10:00:00
 * @Description: Sophnet 每日签到。注册： https://www.sophnet.com?code=MUEVYN
 *
 * 参考：https://github.com/xxy9468615/cat_checkin/blob/main/scripts/sophnet.py
 *
 * cron: 20 9 * * *
 * 环境变量： SOPHNET_TOKEN 必填。格式： token#refreshToken。多账号以 & 或 \n 换行分割
 *   - token：可选。抓包请求 header 中的 authorization（可带或不带 Bearer 前缀）
 *   - refreshToken：登录接口响应中的 refreshToken。仅填 refreshToken 时写成 `#refreshToken`
 *   - 示例：process.env.SOPHNET_TOKEN = 'accessToken1#refreshToken1&#refreshToken2'
 * 说明：
 *   - token 失效时会自动使用 refreshToken 续期，并将新的 token 缓存到 cache 目录，下次运行优先使用
 *   - 签到失败会以错误退出（退出码非 0），避免青龙面板显示假成功
 */
import { createHash } from 'node:crypto';
import { Env } from './utils';

const $ = new Env('Sophnet 签到');

const HOST = 'https://sophnet.com';
/** token 失效的业务状态码 */
const INVALID_TOKEN_STATUS = [10023, 10025];

interface ApiResult<T = any> {
  status?: number;
  message?: string;
  result?: T;
  data?: T;
}

interface Credential {
  token: string;
  refreshToken: string;
}

interface CheckInResult {
  ok: boolean;
  already: boolean;
  invalidToken: boolean;
  message: string;
}

interface WelfareResult {
  checkIn?: {
    tokenBalance?: number;
    currentContinuousDays?: number;
    totalCheckInDays?: number;
  };
  tokenSummary?: { balance?: number };
}

function mask(str: string) {
  if (!str) return '<空>';
  return str.length <= 12 ? '******' : `${str.slice(0, 6)}******${str.slice(-4)}`;
}

function cleanToken(token = '') {
  return String(token).trim().replace(/^Bearer\s+/i, '');
}

function isInvalidTokenStatus(status: unknown) {
  return INVALID_TOKEN_STATUS.includes(Number(status));
}

function authHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (token) headers.authorization = `Bearer ${cleanToken(token)}`;
  return headers;
}

/** 解析账号配置。格式：token#refreshToken */
function parseAccount(cfg: string) {
  const [token = '', refreshToken = ''] = String(cfg).split('#').map(d => cleanToken(d));
  const key = `account_${createHash('md5').update(`${token}#${refreshToken}`).digest('hex').slice(0, 10)}`;

  return { key, token, refreshToken };
}

/** 使用 refreshToken 续期，成功则写入缓存 */
async function doRefresh(key: string, refreshToken: string): Promise<Credential> {
  const { data, response } = await $.req.post<ApiResult>(
    `${HOST}/api/sys/login/refresh`,
    { refreshToken },
    authHeaders(),
    { timeout: 20000 }
  );

  const status = Number(data?.status);
  if ([1, ...INVALID_TOKEN_STATUS].includes(status) || ![200, 201].includes(response.statusCode!)) {
    throw new Error(data?.message || `HTTP ${response.statusCode}`);
  }

  const res = (data.result || data.data || data || {}) as any;
  const token = cleanToken(res.token || res.accessToken);
  const newRefreshToken = String(res.refreshToken || refreshToken).trim();

  if (!token) throw new Error('续期响应中未找到 token');

  $.storage.setItem(key, { token, refreshToken: newRefreshToken, t: Date.now() });
  $.log(`🔑 token 续期成功：${mask(token)}`);

  return { token, refreshToken: newRefreshToken };
}

/** 依次尝试多个 refreshToken 续期（缓存中的可能已失效，需回退到环境变量） */
async function refreshCredential(key: string, ...refreshTokens: string[]): Promise<Credential> {
  const list = [...new Set(refreshTokens.filter(Boolean))];
  if (!list.length) throw new Error('token 已失效且未配置 refreshToken，无法自动续期。请重新抓包更新 SOPHNET_TOKEN');

  let lastError: Error = new Error('续期失败');
  for (const refreshToken of list) {
    try {
      return await doRefresh(key, refreshToken);
    } catch (error) {
      lastError = error as Error;
      $.log(`refreshToken[${mask(refreshToken)}] 续期失败：${lastError.message}`, 'warn');
    }
  }

  throw lastError;
}

/** 执行签到 */
async function checkIn(token: string): Promise<CheckInResult> {
  const { data, response } = await $.req.post<ApiResult>(
    `${HOST}/api/sys/checkin/do`,
    {},
    authHeaders(token),
    { timeout: 20000 }
  );

  const status = Number(data?.status);
  const message = String(data?.message || `HTTP ${response.statusCode}`);
  const invalidToken = isInvalidTokenStatus(status) || [401, 403].includes(response.statusCode!);

  $.debug('签到响应', response.statusCode, JSON.stringify(data));

  return {
    ok: status === 0,
    already: /已(经)?签到/.test(message),
    invalidToken,
    message,
  };
}

/** 查询余额与签到天数（仅展示，失败不影响签到结果） */
async function queryWelfare(token: string) {
  try {
    const { data } = await $.req.get<ApiResult<WelfareResult>>(`${HOST}/api/sys/checkin/welfare`, undefined, authHeaders(token), {
      timeout: 20000,
    });

    const res = (data?.result || data?.data || {}) as WelfareResult;
    const info = res.checkIn || {};
    const balance = res.tokenSummary?.balance ?? info.tokenBalance ?? '-';

    $.log(`💰当前 Token 余额：${balance}`);
    $.log(`📅连续签到：${info.currentContinuousDays ?? 0} 天，累计签到：${info.totalCheckInDays ?? 0} 天`);
    $.debug('welfare 响应', data);
  } catch (error) {
    $.log(`查询余额失败：${(error as Error).message}`, 'warn');
  }
}

export async function signCheckIn(cfg: string) {
  $.req.setConfig({
    baseURL: HOST,
    headers: { 'user-agent': `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/13${Math.ceil(Math.random() * 10)}.0.0.0 Safari/537.36`, },
  });
  const { key, token: envToken, refreshToken: envRefreshToken } = parseAccount(cfg);
  const cache = $.storage.getItem(key) as Credential | undefined;
  const cred: Credential = {
    token: cleanToken(cache?.token) || envToken,
    refreshToken: String(cache?.refreshToken || envRefreshToken).trim(),
  };

  if (!cred.token && !cred.refreshToken) return $.log('未配置 token 或 refreshToken', 'error');
  if (cache?.token) $.debug(`使用缓存的 token：${mask(cache.token)}`);

  if (!cred.token) {
    $.log('未提供 token，尝试使用 refreshToken 登录...', 'warn');
    Object.assign(cred, await refreshCredential(key, cred.refreshToken, envRefreshToken));
  }

  let result = await checkIn(cred.token);

  if (result.invalidToken) {
    $.log('token 已失效，尝试自动续期...', 'warn');
    Object.assign(cred, await refreshCredential(key, cred.refreshToken, envRefreshToken));
    result = await checkIn(cred.token);
  }

  if (!result.ok && !result.already) return $.log(`签到失败：${result.message}`, 'error');

  if (result.already) $.log(`今日已签到：${result.message}`);
  else $.log(`✅签到成功${result.message ? `：${result.message}` : ''}`);

  await queryWelfare(cred.token);
}

// process.env.SOPHNET_TOKEN = '';
if (require.main === module) $.init(signCheckIn, 'SOPHNET_TOKEN|SOPHNET_TOKENS|SOPHNET_token').then(() => $.done());
