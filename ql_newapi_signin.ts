/*
 * @Description: NewAPI 通用签到程序 - 支持多个基于 NewAPI 的平台签到（支持WAF验证）
 *
 * 参考：https://github.com/millylee/anyrouter-check-in
 *
 * cron: 30 8 * * *
 *
 * 用法：
 * - 环境变量： NEW_API_[domainkey]_[userid]
 *   - 格式说明：
 *     - domainkey: 平台标识（如 ANYROUTER、AGENTROUTER 或域名 api.example.com）
 *     - userid: 用户ID（用于标识账号）
 *   - 值：抓包获取的 cookie，格式为 key=value;key2=value2 或 JSON 字符串
 *   - 示例：
 *     - NEW_API_ANYROUTER_1234=session=xxxxx
 *     - NEW_API_ANYROUTER_5678=session=yyyyy
 *     - NEW_API_API2D_8888=session=zzzzz
 *     - NEW_API_api.example.com_9999=session=aaaaa  （自定义域名）
 * - 支持的环境变量（可选）：
 *   - BALANCE_HASH_FILE: 余额hash文件路径，默认为 balance_hash.txt
 *   - WAF_ENABLED: 是否启用WAF验证，默认为 false
 * - 平台配置：
 *   - 内置平台：ANYROUTER、AgentRouter （已验证配置）
 *   - 自定义平台：使用域名作为 domainkey，自动使用默认配置填充
 *     - 默认配置：signinPath=/api/user/sign_in、captchaPath=/api/captcha/image/base64、userInfoPath=/api/user/self
 *     - 协议默认为 https，支持在 domainkey 中指定完整地址（如 https://api.example.com）
 */
import { mkdirp, safeJsonParse } from '@lzwme/fe-utils';
import { Env } from './utils';
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { bootstrap } from 'global-agent';

const $ = new Env('[AnyRouter]NewAPI通用签到');

/** 平台配置接口 */
interface PlatformConfig {
  name: string;
  domain: string;
  signinPath: string;
  /** 验证码 api path。暂未支持 */
  captchaPath?: string;
  userInfoPath: string;
  referer?: string;
  needsWAF: boolean;
  wafCookieNames?: string[];
}

/** 账号配置接口 */
interface AccountConfig {
  domainkey: string;
  userid: string;
  cookies: string | Record<string, string>;
}

/** 用户信息 */
interface UserInfo {
  success: boolean;
  quota?: number;
  used_quota?: number;
  display?: string;
  error?: string;
}

/** 余额hash记录（多平台多账号） */
interface BalanceHashRecord {
  [accountKey: string]: string;
}

/** 默认平台配置 */
const DEFAULT_PLATFORMS: Record<string, PlatformConfig> = {
  ANYROUTER: {
    name: 'AnyRouter',
    domain: 'https://anyrouter.top',
    signinPath: '/api/user/sign_in',
    // captchaPath: '/api/captcha/image/base64',
    userInfoPath: '/api/user/self',
    referer: 'https://anyrouter.top/console/personal',
    needsWAF: false,
  },
  AGENTROUTER: {
    name: 'AgentRouter',
    domain: 'https://agentrouter.org',
    signinPath: '/api/user/sign_in',
    userInfoPath: '/api/user/self',
    referer: 'https://agentrouter.org/console/personal',
    needsWAF: false,
  },
};

const BALANCE_HASH_FILE = process.env.BALANCE_HASH_FILE || path.join(__dirname, 'cache/balance_hash.json');

// ============ 平台管理 ============

/** 获取平台配置 */
function getPlatform(domainkey: string): PlatformConfig | null {
  const upperKey = domainkey.toUpperCase();

  // 如果平台在内置列表中，直接返回
  const info = DEFAULT_PLATFORMS[upperKey] || {} as PlatformConfig;

  // 否则使用默认配置构建新平台
  // 假设 domainkey 就是域名（如 api.example.com）
  let domain = info.domain || (domainkey.includes('://') ? domainkey : `https://${domainkey}`);
  domain = domain.toLowerCase();

  if (!domain.includes('.')) return null;

  return Object.assign({
    name: domainkey,
    domain,
    signinPath: '/api/user/sign_in',
    captchaPath: '/api/captcha/image/base64',
    userInfoPath: '/api/user/self',
    referer: `${domain}/console/personal`,
    needsWAF: false,
  }, info);
}

// ============ 余额hash管理 ============

/** 加载余额hash记录（多平台多账号） */
function loadBalanceHashRecord(): BalanceHashRecord {
   if (fs.existsSync(BALANCE_HASH_FILE)) {
    return safeJsonParse<BalanceHashRecord>(fs.readFileSync(BALANCE_HASH_FILE, 'utf-8'), false, true);
  } else {
    return {} as BalanceHashRecord;
  }
}

/** 保存余额hash记录（多平台多账号） */
function saveBalanceHashRecord(record: BalanceHashRecord): void {
  try {
    mkdirp(path.dirname(BALANCE_HASH_FILE));
    fs.writeFileSync(BALANCE_HASH_FILE, JSON.stringify(record), 'utf-8');
  } catch (error) {
    $.debug(`保存余额hash记录失败：${(error as Error).message}`);
  }
}

/** 生成单个账号余额的hash */
function generateBalanceHash(quota: number, used: number): string {
  const balanceJson = JSON.stringify({ quota, used });
  return crypto.createHash('sha256').update(balanceJson).digest('hex').substring(0, 16);
}

/** 生成账号唯一标识 */
function getAccountKey(account: AccountConfig, _index: number): string {
  return `${account.domainkey}_${account.userid}`;
}

// ============ 工具函数 ============

/** 解析cookies数据 */
function parseCookies(cookiesData: string | Record<string, string>): Record<string, string> {
  if (typeof cookiesData === 'object') return cookiesData;
  const cookiesDict: Record<string, string> = {};
  for (const cookie of cookiesData.split(';')) {
    if (cookie.includes('=')) {
      const [key, ...valueParts] = cookie.split('=');
      cookiesDict[key.trim()] = valueParts.join('=').trim();
    }
  }
  return cookiesDict;
}

// ============ 核心功能 ============

/** 获取用户信息 */
async function getUserInfo(platform: PlatformConfig, headers: Record<string, string>): Promise<UserInfo> {
  try {
    type TUserInfo = { success: boolean; data?: { quota: number; used_quota: number; email?: string; username?: string } };
    const { data } = await $.req.get<TUserInfo>(`${platform.domain}${platform.userInfoPath}`, {}, headers);
    $.debug('获取用户信息结果', data);

    if (data.success && data.data) {
      const quota = Math.round(data.data.quota / 500000 * 100) / 100;
      const used_quota = Math.round(data.data.used_quota / 500000 * 100) / 100;
      return {
        success: true,
        quota,
        used_quota,
        display: `💰当前余额：$${quota}，已用：$${used_quota}`,
      };
    }
    return { success: false, error: '获取用户信息失败' };
  } catch (error) {
    return { success: false, error: `获取用户信息异常：${(error as Error).message}` };
  }
}

/** 获取WAF cookies（如果需要） */
async function getWAFCookies(accountName: string, loginUrl: string, requiredCookies: string[]): Promise<Record<string, string> | null> {
  if (process.env.WAF_ENABLED !== 'true') {
    $.debug(`[${accountName}] WAF验证已禁用，跳过`);
    return {};
  }

  $.log(`[${accountName}] 获取WAF cookies...`, 'warn');

  try {
    // 使用 Playwright 获取 cookies
    const { chromium } = require('playwright');
    const browser = await chromium.launch({
      headless: true,
      args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
    });

    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    });

    const page = await context.newPage();
    await page.goto(loginUrl, { waitUntil: 'networkidle', timeout: 30000 });

    // 获取cookies
    const cookies = await context.cookies();
    await browser.close();

    const wafCookies: Record<string, string> = {};
    for (const cookie of cookies) {
      if (requiredCookies.includes(cookie.name) && cookie.value) {
        wafCookies[cookie.name] = cookie.value;
      }
    }

    const missingCookies = requiredCookies.filter(c => !wafCookies[c]);
    if (missingCookies.length > 0) {
      $.log(`[${accountName}] 缺少WAF cookies：${missingCookies.join(', ')}`, 'error');
      return null;
    }

    $.log(`[${accountName}] 成功获取 ${Object.keys(wafCookies).length} 个WAF cookies`);
    return wafCookies;
  } catch (error) {
    $.log(`[${accountName}] 获取WAF cookies失败：${(error as Error).message}`, 'error');
    return null;
  }
}

/** 准备cookies（合并WAF cookies和用户cookies） */
async function prepareCookies(accountName: string, platform: PlatformConfig, userCookies: Record<string, string>): Promise<Record<string, string> | null> {
  if (platform.needsWAF && platform.wafCookieNames) {
    const loginUrl = `${platform.referer}`;
    const wafCookies = await getWAFCookies(accountName, loginUrl, platform.wafCookieNames);
    if (!wafCookies) {
      return null;
    }
    return { ...wafCookies, ...userCookies };
  }

  return userCookies;
}

// ============ 签到功能 ============

/** 执行签到请求 */
async function executeCheckIn(platform: PlatformConfig, accountName: string, headers: Record<string, string>): Promise<boolean> {
  $.log(`[${accountName}] 执行签到请求...`);

  const signinHeaders = { ...headers, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
  const signinUrl = `${platform.domain}${platform.signinPath}`;

  try {
    type TSigninRes = {
      success?: boolean;
      ret?: number;
      code?: number;
      message?: string;
      msg?: string;
      data?: { consecutive_days?: number; quota_reward?: number; quota_reward_text?: string };
    };

    const { data } = await $.req.post<TSigninRes>(signinUrl, {}, signinHeaders);
    $.debug(`[${accountName}] 签到响应：`, data);

    const message = data.message || data.msg;
    const isSuccess = data.ret === 1 || data.code === 0 || data.success === true;

    if (isSuccess) {
      $.log(`[${accountName}] ✅签到成功！${message || ''}`);
      return true;
    } else {
      $.log(`[${accountName}] ❌签到失败 - ${message || '未知错误'}`, 'error');
      return false;
    }
  } catch (error) {
    $.log(`[${accountName}] ❌签到异常 - ${(error as Error).message}`, 'error');
    return false;
  }
}

/** 为单个账号执行签到操作 */
async function checkInAccount(account: AccountConfig, accountIndex: number): Promise<{ success: boolean; userInfo?: UserInfo }> {
  const platform = getPlatform(account.domainkey);
  if (!platform) {
    $.log(`[账号${accountIndex}] ❌无效的平台配置：${account.domainkey}`, 'error');
    return { success: false };
  }

  const accountName = `${platform.name}(${account.userid})`;
  $.log(`\n[账号${accountIndex}] 开始处理 ${accountName} - ${platform.domain}`);

  const userCookies = parseCookies(account.cookies);
  if (Object.keys(userCookies).length === 0) {
    $.log(`[账号${accountIndex}] ❌无效的cookie配置`, 'error');
    return { success: false };
  }

  // 准备cookies
  const allCookies = await prepareCookies(accountName, platform, userCookies);
  if (!allCookies) {
    return { success: false };
  }

  // 构建headers
  const cookieStr = Object.entries(allCookies).map(([k, v]) => `${k}=${v}`).join('; ');
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': platform.referer || platform.domain,
    'Origin': platform.domain,
    'Cookie': cookieStr,
    'Connection': 'keep-alive',
    'new-api-user': account.userid,
  };

  // 获取用户信息
  const userInfo = await getUserInfo(platform, headers);
  if (userInfo.success) {
    $.log(`[账号${accountIndex}] ${userInfo.display}`);
  } else {
    $.log(`[账号${accountIndex}] ⚠️${userInfo.error}`, 'warn');
  }

  // 执行签到
  const success = await executeCheckIn(platform, accountName, headers);
  return { success, userInfo };
}

// ============ 主程序 ============

/** 解析环境变量，提取所有 NEW_API_ 开头的配置 */
function parseNewApiEnvVars(): AccountConfig[] {
  const accounts: AccountConfig[] = [];

  for (const [key, value] of Object.entries(process.env)) {
    if (key.startsWith('NEW_API_') && value) {
      // 格式：NEW_API_[domainkey]_[userid]
      const parts = key.split('_');
      if (parts.length >= 4) {
        // NEW_API_DOMAINKEY_USERID => parts: ['NEW', 'API', 'DOMAINKEY', 'USERID']
        const domainkey = parts.slice(2, parts.length - 1).join('_');
        const userid = parts[parts.length - 1];
        accounts.push({ domainkey, userid, cookies: value });
      }
    }
  }

  if (accounts.length === 0) {
    $.log('❌未找到 NEW_API_ 开头的环境变量配置', 'error');
    $.log('请按以下格式配置环境变量：', 'info');
    $.log('  - NEW_API_ANYROUTER_1234=session=xxxxx', 'info');
    $.log('  - NEW_API_API2D_5678=session=yyyyy', 'info');
  } else {
    $.log(`📋共找到 ${accounts.length} 个账号配置`);
  }

  return accounts;
}

/** 主函数 */
async function main() {
  $.log('[SYSTEM] NewAPI 多账号自动签到程序启动');
  $.log(`[TIME] 执行时间：${new Date().toLocaleString('zh-CN')}`);

  const accounts = parseNewApiEnvVars();
  if (accounts.length === 0) {
    await $.done();
    return;
  }

  // 加载上次的余额hash记录（多平台多账号）
  const lastBalanceHashRecord = loadBalanceHashRecord();
  const currentBalanceHashRecord: BalanceHashRecord = {};

  let successCount = 0;
  const notificationContent: string[] = [];
  let needNotify = false;

  // 遍历所有账号执行签到
  for (let i = 0; i < accounts.length; i++) {
    const account = accounts[i];
    const accountKey = getAccountKey(account, i);

    try {
      const { success, userInfo } = await checkInAccount(account, i + 1);

      if (success) {
        successCount++;
      } else {
        needNotify = true;
      }

      // 检查余额变化
      if (userInfo && userInfo.success && userInfo.quota !== undefined && userInfo.used_quota !== undefined) {
        const currentHash = generateBalanceHash(userInfo.quota, userInfo.used_quota);
        const lastHash = lastBalanceHashRecord[accountKey];

        // 首次运行或余额有变化，添加到通知
        if (!lastHash) {
          $.log(`[NOTIFY] ${accountKey} 首次运行，记录余额`);
          notificationContent.push(`[首次] ${getPlatform(account.domainkey)?.name || account.domainkey}(${account.userid}) - ${userInfo.display}`);
        } else if (currentHash !== lastHash) {
          $.log(`[NOTIFY] ${accountKey} 余额有变化`);
          notificationContent.push(`[变化] ${getPlatform(account.domainkey)?.name || account.domainkey}(${account.userid}) - ${userInfo.display}`);
        }

        // 保存当前hash
        currentBalanceHashRecord[accountKey] = currentHash;
      }

      // 如果签到失败，添加到通知内容
      if (!success) {
        const platform = getPlatform(account.domainkey);
        const accountName = `${platform?.name || account.domainkey}(${account.userid})`;
        notificationContent.push(`[失败] ${accountName}`);
      }
    } catch (error) {
      $.log(`[账号${i + 1}] 处理异常：${(error as Error).message}`, 'error');
      needNotify = true;
      notificationContent.push(`[异常] ${account.domainkey}(${account.userid}) - ${(error as Error).message}`);
    }
  }

  // 保存当前余额hash记录
  if (Object.keys(currentBalanceHashRecord).length > 0) {
    saveBalanceHashRecord(currentBalanceHashRecord);
  }

  // 发送通知
  if (needNotify || notificationContent.length > 0) {
    const summary = [
      '[统计] 签到结果：',
      `[成功] ${successCount}/${accounts.length}`,
      `[失败] ${accounts.length - successCount}/${accounts.length}`,
    ];

    if (successCount === accounts.length) {
      summary.push('[成功] 所有账号签到成功！');
    } else if (successCount > 0) {
      summary.push('[警告] 部分账号签到成功');
    } else {
      summary.push('[错误] 所有账号签到失败');
    }

    const notifyContent = [
      `[时间] ${new Date().toLocaleString('zh-CN')}`,
      ...notificationContent,
      ...summary,
    ].join('\n');

    $.log(notifyContent);
    // 通知由Env.done()自动发送
  } else {
    $.log('[INFO] 所有账号成功且余额无变化，跳过通知');
  }
}

// 主程序入口
if (require.main === module) {;
  main().then(() => $.done());
}
