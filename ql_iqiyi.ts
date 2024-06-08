/*
 * @Author: renxia
 * @Date: 2024-03-12 23:52:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-05-30 09:21:02
 * @See {https://mirror.ghproxy.com/https://raw.githubusercontent.com/NobyDa/Script/master/iQIYI-DailyBonus/iQIYI.js | 参考}
 cron: 25 8 * * *
 new Env('爱奇艺签到')
 环境变量: IQIYI_COOKIE 抓取请求中的 cookie 。多账户用 & 或换行分割
 */

import { AnyObject, md5, sleep, toQueryString, cookieParse } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('爱奇艺签到');
$.init(start, 'IQIYI_COOKIE').then(() => $.done());

let P00001 = '';
let P00003 = '';
let dfp = '';

async function start(cookie: string) {
  const ckObj = cookieParse(cookie);
  P00001 = ckObj.P00001;
  P00003 = ckObj.P00003 || ckObj.P00010;
  dfp = ckObj.dfp || '';

  if (P00001 && P00003) {
    await login();
    await Checkin();
    sleep(1000);
    await webCheckin();
    sleep(1000);
    await webtask();

    for (let i = 0; i < 3; i++) {
      const run = await Lottery();
      if (run) await sleep(1000);
      else break;
    }

    const tasks = await getTaskList();
    for (const task of tasks) {
      if (task.status === 4) {
        $.log(`💓任务[${task.name}]进行中，需手动完成`);
        console.log(`--------------------`);
      } else if (task.status !== 1) {
        //0：待领取 1：已完成 2：未开始 4：进行中
        await joinTask(task);
        await notifyTask(task);
        await sleep(1000);
        await getTaskRewards(task);
        console.log(`--------------------`);
      }
    }
  } else {
    console.log(`Cookie缺少关键值，需重新获取`);
  }
}

async function login() {
  const url =
    `https://cards.iqiyi.com/views_category/3.0/vip_home?secure_p=iPhone&scrn_scale=0&dev_os=0&ouid=0&layout_v=6&psp_cki=${P00001}` +
    '&page_st=suggest&app_k=8e48946f144759d86a50075555fd5862&dev_ua=iPhone8%2C2&net_sts=1&cupid_uid=0&xas=1&init_type=6&app_v=11.4.5&idfa=0&app_t=0&platform_id=0&layout_name=0&req_sn=0&api_v=0&psp_status=0&psp_uid=451953037415627&qyid=0&secure_v=0&req_times=0';
  const headers = { sign: '7fd8aadd90f4cfc99a858a4b087bcc3a', t: '479112291' };
  const { data } = await $.req.get(url, void 0, headers);
  if (data.code == 0) $.log(`爱奇艺查询成功！VIP会员${data.base?.exp_time || '-'}天后到期`);
  else $.log(`爱奇艺查询失败！$${data.message || JSON.stringify(data)}`, 'error');
}

async function Checkin() {
  const sign_date = {
    task_code: 'natural_month_sign',
    timestamp: Date.now(),
    appKey: 'lequ_rn',
    userId: P00003,
    authCookie: P00001,
    agenttype: 20,
    agentversion: '15.4.6',
    srcplatform: 20,
    appver: '15.4.6',
    qyid: md5(stringRandom(16)),
    // agentType: '1',
    // typeCode: 'point',
  };
  const post_date = {
    natural_month_sign: {
      verticalCode: 'iQIYI',
      agentVersion: '15.4.6',
      authCookie: P00001,
      taskCode: 'iQIYI_mofhr',
      dfp: dfp,
      qyid: md5(stringRandom(16)),
      agentType: 20,
      signFrom: 1,
    },
  };
  const sign = k('cRcFakm9KSPSjFEufg3W', sign_date, { split: '|', sort: true, splitSecretKey: true });
  const url = `https://community.iqiyi.com/openApi/task/execute?${toQueryString(sign_date)}&sign=${sign}`;
  const { data: obj } = await $.req.post(url, post_date);

  if (obj.code === 'A00000') {
    if (obj.data.code === 'A0000') {
      $.log(`签到成功！累计签到 ${obj.data?.data?.signDays} 天`);
      for (let i = 0; i < obj.data.data.rewards.length; i++) {
        if (obj.data.data.rewards[i].rewardType == 1) {
          $.log(` 成长值+${obj.data.data.rewards[i].rewardCount}`);
        } else if (obj.data.data.rewards[i].rewardType == 2) {
          $.log(` VIP天+${obj.data.data.rewards[i].rewardCount}`);
        } else if (obj.data.data.rewards[i].rewardType == 3) {
          $.log(` 积分+${obj.data.data.rewards[i].rewardCount}`);
        }
      }
    } else {
      $.log(`应用签到: ${obj.data.msg} ⚠️`);
    }
  } else {
    $.log(`应用签到: [${obj.msg || obj.message || 'Cookie无效'}]⚠️`, 'error');
  }
}

/** 网页版签到 */
async function webCheckin() {
  if (!dfp) return; // $.log('网页版签到：未发现 dfp 参数，任务忽略');

  const sign_date = {
    agenttype: '1',
    agentversion: '0',
    appKey: 'basic_pca',
    appver: '0',
    authCookie: P00001,
    channelCode: 'sign_pcw',
    dfp: dfp,
    scoreType: '1',
    srcplatform: '1',
    typeCode: 'point',
    userId: P00003,
    user_agent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    verticalCode: 'iQIYI',
  };
  const sign = k('UKobMjDMsDoScuWOfp6F', sign_date, { split: '|', sort: true, splitSecretKey: true });
  const url = `https://community.iqiyi.com/openApi/score/add?${toQueryString(sign_date)}&sign=${sign}`;
  const { data: obj } = await $.req.get(url);

  if (obj.code === 'A00000') {
    if (obj.data?.[0]?.code === 'A0000') {
      $.log(`网页端签到成功: 获得积分${obj.data[0].score}, 累计签到 ${obj.data[0].continuousValue} 天`);
    } else {
      $.log(`网页端签到: ${obj.data?.[0].msg} ⚠️`);
    }
  } else {
    $.log(`网页端签到失败: [${obj.msg || obj.message || 'Cookie无效'}]⚠️`, 'error');
  }
}
/** 网页端访问热点首页任务 */
async function webtask() {
  if (!dfp) return; // $.log('网页版热点任务：未发现 dfp 参数，任务忽略');

  const sign_date = {
    agenttype: '1',
    agentversion: '0',
    appKey: 'basic_pca',
    appver: '0',
    authCookie: P00001,
    channelCode: 'paopao_pcw',
    dfp,
    scoreType: '1',
    srcplatform: '1',
    typeCode: 'point',
    userId: P00003,
    user_agent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    verticalCode: 'iQIYI',
  };
  const sign = k('UKobMjDMsDoScuWOfp6F', sign_date, { split: '|', sort: true, splitSecretKey: true });
  const paramStr = toQueryString(sign_date);
  const url = `https://community.iqiyi.com/openApi/task/complete?${paramStr}&sign=${sign}`;

  try {
    const { data: res } = await $.req.get(url);

    if (res.code === 'A00000') {
      $.log(`网页端访问任务成功：${res.message}`);

      // 领取奖励
      const rewardUrl = `https://community.iqiyi.com/openApi/score/getReward?${paramStr}&sign=${sign}`;
      const { data: rewardRes } = await $.req.get(rewardUrl);
      // console.log('rewardRes', rewardRes);
      if (rewardRes.code === 'A00000') {
        $.log(`网页端访问任务成功：获得${rewardRes.data.score}积分`);
      } else {
        $.log(`网页端访问任务失败：${rewardRes.message}`);
      }
    } else {
      $.log(`网页端访问任务失败：${res.message}`);
    }
  } catch (error) {
    console.error('请求失败:', error);
  }
}
// 抽奖
async function Lottery() {
  const url =
    'https://iface2.iqiyi.com/aggregate/3.0/lottery_activity?app_k=0&app_v=0&platform_id=0&dev_os=0&dev_ua=0&net_sts=0&qyid=0&psp_uid=0&psp_cki=' +
    P00001 +
    '&psp_status=0&secure_p=0&secure_v=0&req_sn=0';
  const { data: obj } = await $.req.get(url);

  if (obj.code != 0) {
    $.log(`[${obj.title || '应用抽奖'}]${obj.errorReason}`);
    return false;
  } else if (obj.title) {
    $.log(`应用抽奖: ${(obj.title != '影片推荐' && obj.awardName) || '未中奖'} 🎉`);
    if (obj.kv.code == 'Q00702') {
      $.log(`应用抽奖: 您的抽奖次数已经用完 ⚠️`);
      return false;
    }
  } else if (obj.kv.code == 'Q00304') {
    $.log(`应用抽奖: Cookie无效 ⚠️`, 'error');
    return false;
  } else {
    $.log(`应用抽奖: 未知错误 ⚠️`, 'error');
    return false;
  }

  return true;
}

async function getTaskList() {
  const { data: obj } = await $.req.get(`https://tc.vip.iqiyi.com/taskCenter/task/queryUserTask?P00001=${P00001}`);
  if (obj.code == 'A00000' && obj.data && obj.data.tasks) {
    const taskList: TaskItem[] = [];
    Object.values(obj.data.tasks).forEach((d: any) => {
      if (!Array.isArray(d)) return;
      d.forEach(item =>
        taskList.push({
          name: item.taskTitle || item.name,
          taskCode: item.taskCode || item.code,
          status: item.status,
        })
      );
    });

    $.log(`获取任务列表成功！共有任务 ${obj.data.count} 个，已完成 ${obj.data.finishedCount} 个`);
    return taskList;
  } else {
    $.log(`获取任务列表失败!`);
  }
  return [];
}

async function joinTask(task: TaskItem) {
  const { data } = await $.req.get(
    `https://tc.vip.iqiyi.com/taskCenter/task/joinTask?taskCode=${task.taskCode}&lang=zh_CN&platform=0000000000000000&P00001=${P00001}`
  );
  $.log(`领取任务：${task.name} => ${data.msg || data.code || JSON.stringify(data)}`);
}

async function notifyTask(task: TaskItem) {
  const { data } = await $.req.get(
    `https://tc.vip.iqiyi.com/taskCenter/task/notify?taskCode=${task.taskCode}&lang=zh_CN&platform=0000000000000000&P00001=${P00001}`
  );

  $.log(`爱奇艺-开始任务: ${task.name} => ${data.msg || data.code || JSON.stringify(data)}`);
}

async function getTaskRewards(task: TaskItem) {
  const { data } = await $.req.get(
    `https://tc.vip.iqiyi.com/taskCenter/task/getTaskRewards?taskCode=${task.taskCode}` +
      `&lang=zh_CN&platform=0000000000000000&P00001=${P00001}`
  );

  if (data.msg === '成功' && data.code === 'A00000' && data.dataNew[0] !== undefined) {
    $.log(`任务奖励: ${task.name} => ${data.dataNew[0].name + data.dataNew[0].value} 🎉`);
  } else {
    $.log(`任务奖励: ${task.name} => ${(data.msg !== `成功` && data.msg) || `未完成`} ⚠️`);
  }
}

function k(e: string, t: AnyObject, a: { split: string; sort: boolean; splitSecretKey: boolean }) {
  let c = void 0 == a.split ? '|' : a.split,
    s = void 0 === a.sort || a.sort,
    o = a.splitSecretKey,
    i = void 0 !== o && o,
    l = s ? Object.keys(t).sort() : Object.keys(t),
    u = l.map(k => `${k}=${t[k]}`).join(c) + (i ? c : '') + e;
  return md5(u);
}
function stringRandom(length: number) {
  let rdm62 = 0;
  let ret = '';
  while (length--) {
    rdm62 = 0 | (Math.random() * 62);
    ret += String.fromCharCode(rdm62 + (rdm62 < 10 ? 48 : rdm62 < 36 ? 55 : 61));
  }
  return ret;
}

type TaskItem = {
  name: string;
  taskCode: string;
  /** 任务状态。 0：待领取 1：已完成 2：未开始 4：进行中 */
  status: 1 | 2 | 3 | 4;
};
