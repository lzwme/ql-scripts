/*
 * @Author: renxia
 * @Date: 2024-02-23 13:52:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-03-18 18:18:48
 * @see https://raw.githubusercontent.com/ClydeTime/Quantumult/main/Script/Task/videoqq.js
 cron: 36 7 * * *
 new Env('腾讯视频VIP会员签到')
 注意，非会员无法签到。环境变量:
 export videoqq_cookie='' : 抓取 APP 请求中的 Cookie
 下面两个不抓取也没关系，但可能时效性会比较短，容易频繁过期
 export videoqq_cookie_pc='' : 抓取 PC 网页请求中的 Cookie
 export videoqq_ref_url='' : 抓取 PC 网页请求的 ref_url： 获取教程: https://cdn.jsdelivr.net/gh/BlueskyClouds/Script/img/2020/11/1/img/v_1.jpg
 */

import { Env } from './utils';

const $ = new Env('腾讯视频VIP会员签到', { sep: ['\n', '@'] });
// process.env.videoqq_cookie = '';
// process.env.videoqq_cookie_pc = '';
// process.env.process.env.videoqq_ref_url = '';
$.init(start, 'videoqq_cookie').then(() => $.done());

let videoqq_cookie_pc = '';
// ref_url获取教程: 「https://cdn.jsdelivr.net/gh/BlueskyClouds/Script/img/2020/11/1/img/v_1.jpg」
let videoqq_ref_url = process.env.videoqq_ref_url || '';
let auth: Record<string, string> = {};

let headers = {
  Referer: `https://film.video.qq.com/`,
  'User-Agent':
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_1 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/11A465 QQLiveBrowser/8.7.45 AppType/UN WebKitCore/WKWebView iOS GDTTangramMobSDK/4.370.6 GDTMobSDK/4.370.6 cellPhone/iPhone 12 pro max',
};

async function start(cookie: string) {
  $.req.setHeaders({ ...headers, cookie });
  auth = getAuth(cookie);
  if (videoqq_ref_url) await refCookie(videoqq_ref_url);

  let sign_flag = await txVideoSignIn();
  await txVideoDownTasks();

  if (sign_flag) {
    let message = `🟢【恭喜】签到状态:签到成功 \n`;
    $.log(message);
  } else {
    let message = `🔴【抱歉】签到状态:签到失败 \n` + '请重新获取cookie';
    $.log(message);
  }
}

const parseSet = (cookie: string) => {
  const obj: Record<string, string> = {};
  cookie = cookie.replace(/\GMT, /g, 'GMT;');
  const arr = cookie.split(';');
  arr.forEach(function (val) {
    const brr = val.split('=');
    obj[brr[0]] = brr[1];
  });
  return obj;
};

function getAuth(cookie: string) {
  let needParams = [''];
  const obj: Record<string, string> = {};

  //适配微信登录
  if (cookie) {
    if (cookie.includes('main_login=wx')) {
      needParams = [
        'vdevice_qimei36',
        'video_platform',
        'pgv_pvid',
        'pgv_info',
        'video_omgid',
        'main_login',
        'access_token',
        'appid',
        'openid',
        'vuserid',
        'vusession',
      ];
    } else if (cookie.includes('main_login=qq')) {
      needParams = [
        'vdevice_qimei36',
        'video_platform',
        'pgv_pvid',
        'video_omgid',
        'main_login',
        'vqq_access_token',
        'vqq_appid',
        'vqq_openid',
        'vqq_vuserid',
        'vqq_vusession',
      ];
    } else {
      $.log('getAuth - 无法提取有效cookie参数', 'error');
    }

    cookie.split('; ').forEach(t => {
      const [key, val] = t.split(/\=(.*)$/, 2);
      if (needParams.includes(key)) obj[key] = val;
    });
  }

  return obj;
}

async function refCookie(url: string) {
  const { headers, data } = await $.req.get<string>(url, {}, { 'content-type': 'text/html', cookie: videoqq_cookie_pc });
  const { vusession, vqq_vusession, access_token } = parseSet(headers['set-cookie']?.join(';') as string);
  //微信多一个 access_token
  if (typeof vusession != 'undefined') {
    auth['vusession'] = vusession;
    auth['access_token'] = access_token;
  } else {
    auth['vqq_vusession'] = vqq_vusession;
  }

  const cookie = Object.keys(auth)
    .map(i => i + '=' + auth[i])
    .join('; ');
  $.req.setHeaders({
    ...headers,
    cookie,
  });

  if (data.match(/nick/)) {
    //通过验证获取QQ昵称参数来判断是否正确
    $.log('验证成功，执行主程序');
  } else {
    $.log('验证ref_url失败,无法获取个人资料 ref_url 或 Cookie 失效 ‼️‼️');
    console.error(data);
  }
}

/** 手机端签到 */
async function txVideoSignIn() {
  const { data } = await $.req.get(`https://vip.video.qq.com/rpc/trpc.new_task_system.task_system.TaskSystem/CheckIn?rpc_data=%7B%7D`);
  if (data != null) {
    const { ret: code, check_in_score } = data;
    if (code === 0 && check_in_score != undefined) {
      $.log('腾讯视频会员手机端签到成功：签到分数：' + check_in_score + '分 🎉');
    } else if (code === -2002) {
      $.log('腾讯视频会员手机端签到失败：重复签到 ‼️‼️');
    } else if (code === -2007) {
      $.log('腾讯视频会员签到：非会员无法签到');
    } else {
      $.log('腾讯视频会员手机端签到失败：未知错误请查看控制台输出 ‼️‼️\n' + data);
    }
  } else {
    $.log('腾讯视频会员签到：签到失败, Cookie失效 ‼️‼️');
  }

  return data?.ret == 0;
}

/** 观看60分钟任务签到请求 */
async function txVideoDownTasks() {
  const { data } = await $.req.get(
    `https://vip.video.qq.com/rpc/trpc.new_task_system.task_system.TaskSystem/ProvideAward?rpc_data=%7B%22task_id%22:1%7D`
  );
  const { ret: code, check_in_score } = data;

  if (code === 0 && check_in_score != undefined) {
    $.log('腾讯视频会员观看任务签到成功：签到分数：' + check_in_score + '分 🎉');
  } else if (code === -2002) {
    $.log('腾讯视频会员观看任务签到成功：重复签到 ‼️‼️');
  } else if (code === -2003) {
    $.log('腾讯视频会员观看任务签到失败：任务未完成 ‼️‼️');
  } else if (code === -2007) {
    $.log('腾讯视频会员签到：非会员无法签到');
  } else {
    $.log('腾讯视频会员观看任务签到成功：未知错误请查看控制台输出 ‼️‼️\n');
    console.error(data);
  }
}
