/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-02-23 11:05:36
 * @Description: v2free机场签到。注册地址： https://w1.v2free.top/auth/register?code=cJLs

 cron: 21 10 * * *
 环境变量 V2freeCookie: 抓包获取 header 中的 cookie，多个账户以 & 或 \n 换行分割
 环境变量 YESCAPTCHA_KEY: https://yescaptcha.com/i/9fyOAJ 平台的 ClientKey，新用户联系客服可得 1500 测试积分
 */
import { sleep } from '@lzwme/fe-utils';
import { Env, logger } from '../utils';

const $ = new Env('v2free机场签到');
$.init(signCheckIn, 'v2freeCookie').then(() => $.done());

async function reCaptchaV3({ type = 'RecaptchaV3TaskProxyless', websiteURL = '', websiteKey = '', pageAction = '', clientKey = '' }) {
  const result = { token: '', msg: '' };

  if (!clientKey) {
    result.msg = 'clientKey 必填';
    return result;
  }

  const r = await fetch('https://cn.yescaptcha.com/createTask', {
    method: 'POST',
    body: JSON.stringify({ clientKey, task: { type, websiteURL, websiteKey, pageAction } }),
  }).then(d => d.json());
  logger.debug('[createTask]', r);

  if (!r.taskId) {
    logger.debug('[createTask]创建获取验证码任务失败', r);
    result.msg = r.errorDescription || JSON.stringify(r);
    return result;
  }

  const getTaskResult: () => Promise<typeof result> = async () => {
    const r1 = await fetch('https://api.yescaptcha.com/getTaskResult', {
      method: 'POST',
      body: JSON.stringify({ taskId: r.taskId, clientKey }),
    }).then(d => d.json());

    logger.debug('getTaskResult', r1);

    if (r1.errorId !== 0) {
      logger.debug('获取验证码结果失败', r1);
      result.msg = r1.errorDescription || JSON.stringify(r1);
      return result;
    }

    if (r1.status === 'processing') {
      await sleep(1000);
      return getTaskResult();
    }

    result.token = r1.solution?.gRecaptchaResponse as string;
    if (!result.token) result.msg = r1.errorDescription || JSON.stringify(r1);
    return result;
  };

  await sleep(10_000);
  return getTaskResult();
}

async function signCheckIn(Cookie: string) {
  const r = await reCaptchaV3({
    type: 'RecaptchaV3TaskProxyless',
    websiteURL: 'https://w1.v2free.top/user',
    websiteKey: '6LdKhuYnAAAAAEshg5Sa2jKL_HqNOpqfrmp',
    pageAction: '',
    clientKey: process.env.YESCAPTCHA_KEY,
  });
  if (!r.token) return $.log(`人机验证码识别失败: ${r.msg}`, 'error');

  const data = await fetch('https://w1.v2free.top/user/checkin', {
    method: 'POST',
    headers: {
      Cookie,
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      Host: 'w1.v2free.top',
      Origin: 'https://w1.v2free.top',
      Referer: 'https://w1.v2free.top/user',
      'User-Agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    },
    body: `recaptcha=${r.token}`,
  }).then(d => d.text());

  const res = JSON.parse(data as never as string);
  if (res.trafficInfo) $.log(`签到成功！${res.msg}。未使用流量：${res.trafficInfo.unUsedTraffic}`);
  else $.log(`❌签到失败：${res.msg}`, 'error');
}
