/**
 葫芦娃预约 v1.06

 cron: 10 10 * * *
 const $ = new Env("葫芦娃预约");

 抓包把 X-access-token 的值(在请求头里)填到环境变量中, 多账号用 & 隔开（可自定义）

 环境变量 XLHG_TOKEN 偲源惠购
 环境变量 GLYP_TOKEN 贵旅优品
 环境变量 KGLG_TOKEN 空港乐购
 环境变量 HLQG_TOKEN 航旅黔购
 环境变量 ZHCS_TOKEN 遵航出山
 环境变量 GYQP_TOKEN 贵盐黔品
 环境变量 LLSC_TOKEN 乐旅商城
 环境变量 YLQX_TOKEN 驿路黔寻

 https://blog.168api.cn/jsjiami-com-v7-%e5%9c%a8%e7%ba%bf%e8%a7%a3%e5%af%86
 */

import { createHmac } from 'node:crypto';
import type { IncomingHttpHeaders } from 'node:http';
import moment from 'moment';
import { assign, dateFormat, Request, sleep } from '@lzwme/fe-utils';
import { getConfigStorage } from './utils';
import { Env } from './utils';

const $ = new Env('葫芦娃预约');
const SPLIT = '&'; // 分割符（可自定义）
const config = {
  token: {
    偲源惠购: (process.env.XLHG_COOKIE || process.env.XLTH_COOKIE || '').split(SPLIT).filter(Boolean),
    贵旅优品: [] as string[],
    空港乐购: [] as string[],
    航旅黔购: [] as string[],
    遵航出山: [] as string[],
    贵盐黔品: [] as string[],
    乐旅商城: [] as string[],
    驿路黔寻: [] as string[],
  },
};
const stor = getConfigStorage<typeof config>('葫芦娃预约');
const req = new Request('', { 'content-type': 'application/json' });
const constants = {
  app: {
    偲源惠购: { key: 'XLHG', channelId: '8', appId: 'wxded2e7e6d60ac09d' },
    贵旅优品: { key: 'GLYP', channelId: '7', appId: 'wx61549642d715f361' },
    空港乐购: { key: 'KGLG', channelId: '2', appId: 'wx613ba8ea6a002aa8' },
    航旅黔购: { key: 'HLQG', channelId: '6', appId: 'wx936aa5357931e226' },
    遵航出山: { key: 'ZXCS', channelId: '5', appId: 'wx624149b74233c99a' },
    贵盐黔品: { key: 'GYQP', channelId: '3', appId: 'wx5508e31ffe9366b8' },
    乐旅商城: { key: 'LLSC', channelId: '1', appId: 'wx821fb4d8604ed4d6' },
    驿路黔寻: { key: 'YLQX', channelId: '9', appId: 'wxee0ce83ab4b26f9c' },
  },
  apiUrl: 'https://gw.huiqunchina.com',
  akskUrl: 'https://callback.huiqunchina.com',
  api: {
    queryById: '/front-manager/api/customer/queryById/token',
    channelActivity: '/front-manager/api/customer/promotion/channelActivity',
    appoint: '/front-manager/api/customer/promotion/appoint',
    checkCustomerInQianggou: '/front-manager/api/customer/promotion/checkCustomerInQianggou',
  },
};
const cache = {
  ak: '00670fb03584fbf44dd6b136e534f495',
  sk: '0d65f24dbe2bc1ede3c3ceeb96ef71bb',
};

function hmacSignature(method: string, pathname: string, ak: string, sk: string, date: string) {
  const text = method.toUpperCase() + '\n' + pathname + '\n\n' + ak + '\n' + date + '\n';
  return createHmac('sha256', sk).update(text).digest('base64');
}
function formatHeaders(method: 'get' | 'post', pathname: string, paramsStr: string) {
  const date = moment().utc().format('ddd, DD MMM YYYY HH:mm:ss [GMT]');
  return {
    'X-HMAC-SIGNATURE': hmacSignature(method, pathname, cache.ak, cache.sk, date),
    'X-HMAC-ACCESS-KEY': cache.ak,
    'X-HMAC-ALGORITHM': 'hmac-sha256',
    'X-HMAC-DIGEST': createHmac('sha256', cache.sk).update(paramsStr).digest('base64'),
    'X-HMAC-Date': date,
  } as IncomingHttpHeaders;
}
function post<T = any>(pathname: string, data: Record<string, unknown>) {
  const headers = formatHeaders('post', pathname, JSON.stringify(data));
  return req.post<{ code: string; message: string; data: T }>(constants.apiUrl + pathname, data, headers).then(d => d.data);
}
async function getAkSk(appId: string) {
  const { data } = await req.post(`${constants.akskUrl}/api/getInfo`, { appId });
  if (data.code == '10000') assign(cache, data.data); // data.data.ak、sk
  else $.log(`获取 ak/sk 异常：${data?.message || data}`, 'error');
}
async function getWinningCustomers({ activityId = '', activityName = '' }) {
  const url = '/front-manager/api/customer/promotion/getWinningCustomers';
  const data = await post(url, { activityId });
  if (data.code != '10000') return $.log(`查询中签结果失败：` + data.message, 'error');
  else $.log(`[${activityName}]中签结果：${data.message}`, data.data ? 'error' : 'info');
}
async function reservation(appId: string, channelId: string) {
  try {
    const userInfo = await post<{ phone: string; idcard: string; realName: string }>(constants.api.queryById, { appId });
    if (userInfo.code != '10000') return $.log(userInfo.message, 'error');

    const activityRes = await post(constants.api.channelActivity, { id: channelId });
    const aData = activityRes.data;
    if (activityRes.code != '10000') return $.log(activityRes.message, 'error');
    // console.log(aData)
    if (aData.endTime && Date.now() - aData.endTime > 1000 * 60 * 1000) {
      $.log(`----暂无新活动。最近活动为「${dateFormat('MM-dd hh:mm:00', aData.endTime)}」【${aData.name}】----`);
      return '活动已结束';
    }

    $.log(`当前用户[${userInfo.data.phone}]`);
    if (aData.appointCounts > 1 && aData.drawTime < Date.now()) {
      $.log(
        `[${aData.name}]结果已公布，中签人数[${aData.appointCounts}]，${aData.isAppoint ? '您可能已中签，尽快进小程序确认！' : '您未中签'}`,
        aData.isAppoint ? 'error' : 'info'
      );
      await getWinningCustomers({ activityId: aData.id, activityName: aData.name });
      return;
    }

    $.log(`活动名称[${aData.name}]`);
    const checkRes = await post(constants.api.checkCustomerInQianggou, { activityId: aData.id, channelId });
    if (checkRes.code != '10000') return $.log(checkRes.message, 'error');

    if (checkRes.data == false) {
      const r = await post(constants.api.appoint, { activityId: aData.id, channelId: channelId });
      $.log(`预约结果[appoint][${r.message}]`, String(r.message).includes('验证码') ? 'error' : 'info');
    } else $.log(`预约结果[已经预约成功，无需重复预约]`);
  } catch (error) {
    $.log(`运行异常[${(error as Error).message}]`, 'error');
  }
}
async function start() {
  await stor.ready();
  assign(config, stor.get());

  for (let [appName, tokens] of Object.entries(config.token)) {
    try {
      if (/^[a-zA-Z]$/.test(appName)) {
        const item = Object.entries(constants.app).find(d => d[1].key === appName);
        if (!item) continue;
        appName = item[0];
      }

      const key = Object.entries(constants.app).find(d => d[0] === appName)?.[1].key;
      if (key) {
        const _tokens = (process.env[`${key}_COOKIE`] || process.env[`${key}_TOKEN`] || '').split(SPLIT).filter(Boolean);
        if (_tokens.length > 0) tokens = _tokens;
      }
      if (!tokens.length) {
        $.log(`${appName}: 请配置环境变量 ${key}_TOKEN`);
        continue;
      }

      const constant = constants.app[appName as keyof typeof constants.app];
      if (!constant) {
        $.log(`未知的配置：${appName}`);
        continue;
      }
      $.log(`${appName}预约开始`);

      await getAkSk(constant.appId);
      for (const [idx, token] of tokens.entries()) {
        $.log('----第' + (idx + 1) + '个号----');
        req.setHeaders({
          'X-access-token': token.split(token.includes('|') ? '|' : '##')[0].trim(),
          'user-agent': `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x6309080f)XWEB/8461`,
        });
        const msg = await reservation(constant.appId, constant.channelId);
        if (msg === '活动已结束') break;

        await sleep(1000);
      }
      $.log(`${appName}预约结束\n`);
    } catch (e) {
      $.log(`[${appName}]运行异常[${(e as Error).message}]`, 'error');
    }
  }

  await $.done();
}

start();
