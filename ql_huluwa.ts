/**
 葫芦娃预约 v1.06

 cron: 50 9 * * *
 const $ = new Env("葫芦娃预约");

 抓包把 X-access-token 的值(在请求头里)填到环境变量中, 多账号用 & 隔开（可自定义）

 环境变量 XLHG_TOKEN 新联惠购
 环境变量 GLYP_TOKEN 贵旅优品
 环境变量 KGLG_TOKEN 空港乐购
 环境变量 HLQG_TOKEN 航旅黔购
 环境变量 ZHCS_TOKEN 遵行出山
 环境变量 GYQP_TOKEN 贵盐黔品
 环境变量 LLSC_TOKEN 乐旅商城
 环境变量 YLQX_TOKEN 驿路黔寻

 https://blog.168api.cn/jsjiami-com-v7-%e5%9c%a8%e7%ba%bf%e8%a7%a3%e5%af%86
 */

import { createHmac } from 'crypto';
import moment from 'moment';
import type { IncomingHttpHeaders } from 'http';
import { assign, Request, sleep } from '@lzwme/fe-utils';
import { getLiteStorage, sendNotify } from './utils';

const SPLIT = '&'; // 分割符（可自定义）
const config = {
  token: {
    XLHG: (process.env.XLHG_COOKIE || process.env.XLTH_COOKIE || '').split(SPLIT).filter(Boolean),
    GLYP: [] as string[],
    KGLG: [] as string[],
    HLQG: [] as string[],
    ZXCS: [] as string[],
    GYQP: [] as string[],
    LLSC: [] as string[],
    YLQX: [] as string[],
  },
};
const stor = getLiteStorage<typeof config>('葫芦娃预约');
const req = new Request('', { 'content-type': 'application/json' });
const constants = {
  app: {
    XLHG: { name: '新联惠购', channelId: '8', appId: 'wxded2e7e6d60ac09d' },
    GLYP: { name: '贵旅优品', channelId: '7', appId: 'wx61549642d715f361' },
    KGLG: { name: '空港乐购', channelId: '2', appId: 'wx613ba8ea6a002aa8' },
    HLQG: { name: '航旅黔购', channelId: '6', appId: 'wx936aa5357931e226' },
    ZXCS: { name: '遵行出山', channelId: '5', appId: 'wx624149b74233c99a' },
    GYQP: { name: '贵盐黔品', channelId: '3', appId: 'wx5508e31ffe9366b8' },
    LLSC: { name: '乐旅商城', channelId: '1', appId: 'wx821fb4d8604ed4d6' },
    YLQX: { name: '驿路黔寻', channelId: '9', appId: 'wxee0ce83ab4b26f9c' },
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
  message: [] as string[],
};

function logPrint(msg: string, toSendCache = true) {
  console.log(msg);
  if (toSendCache) cache.message.push(msg);
}
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
  else logPrint(`获取 ak/sk 异常：${data.message}`);
}
async function reservation(appId: string, channelId: string) {
  try {
    const userInfo = await post<{ phone: string; idcard: string; realName: string }>(constants.api.queryById, { appId });
    if (userInfo.code != '10000') return logPrint(userInfo.message);
    logPrint(`当前用户[${userInfo.data.phone}]`);

    const activityRes = await post(constants.api.channelActivity, { id: channelId });
    const aData = activityRes.data;
    if (activityRes.code != '10000') return logPrint(activityRes.message);

    if (aData.appointCounts > 1 && aData.drawTime < Date.now()) {
      logPrint(
        `[${aData.name}]结果已公布，中签人数[${aData.appointCounts}]，${aData.isAppoint ? '您已中签，尽快进小程序确认！' : '您未中签'}`
      );
      return;
    }

    logPrint(`活动名称[${aData.name}]`);
    const checkRes = await post(constants.api.checkCustomerInQianggou, { activityId: aData.id, channelId });
    if (checkRes.code != '10000') return logPrint(checkRes.message);

    if (checkRes.data == false) {
      const r = await post(constants.api.appoint, { activityId: aData.id, channelId: channelId });
      logPrint(`预约结果[appoint][${r.message}]`);
    } else logPrint(`预约结果[已经预约成功，无需重复预约]`);
  } catch (error) {
    logPrint(`运行异常[${(error as Error).message}]`);
  }
}
async function start() {
  assign(config, stor.get());

  for (const [key, tokens] of Object.entries(config.token)) {
    if (!tokens.length) {
      tokens.push(...(process.env[`${key}_COOKIE`] || process.env[`${key}_TOKEN`] || '').split(SPLIT).filter(Boolean));
      if (!tokens.length) continue;
    }

    const constant = constants.app[key as keyof typeof constants.app];
    logPrint(`${constant.name}预约开始`);

    await getAkSk(constant.appId);
    for (const [idx, token] of tokens.entries()) {
      logPrint('----第' + (idx + 1) + '个号----');
      req.setHeaders({
        'X-access-token': token,
        'user-agent': `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x6309080f)XWEB/8461`,
      });
      await reservation(constant.appId, constant.channelId);
      await sleep(1000);
    }
    logPrint(`${constant.name}预约结束\n`);
  }

  await sendNotify('葫芦娃预约', cache.message.join('\n'), {}, '\n\n本通知 By：lzwme/ql-scripts');
}

start();
