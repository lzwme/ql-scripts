/*
 * @Author: renxia
 * @Date: 2024-03-22 10:00:00
 * @LastEditors: renxia
 * @LastEditTime: 2025-03-31 09:45:54
 *
 cron: 25 8 * * *
 new Env('绝味鸭脖小程序30天连续签到挑战')
 环境变量: jwyb_urls: 抓取该地址的完整请求URL：https://p3720226302625sh3s-saas.xiaoman-activity.meta-xuantan.com/activityMultiport.html
          多账户用 @ 或换行分割
   有效期较短，重新认证需获取应用微信 code，故废弃
 */

import { dateFormat, generateUuid, md5, Request, wait } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('绝味鸭脖小程序30天连续签到挑战', { sep: ['@', '\n'] });
const req = new Request({ baseURL: 'https://p3720226302625sh3s-saas.xiaoman-activity.meta-xuantan.com' });

class UserInfo {
  private li = '';
  private xmToken = '';
  baseKey = atob('dWgzJEhnJl5ISzg3NiVnYnhWRzdmJCVwPTBNfj5zMXg=');
  constructor(url: string, private index: number) {
    req.setHeaders({
      'user-agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 18_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.56(0x1800383b) NetType/WIFI Language/zh_CN miniProgram/wxf6ec04edb4802bec',
      Referer: url,
      'content-type': 'application/json',
      ri: '',
      bdrk: '',
    });
    this.li = new URL(url).searchParams.get('li')!;
  }
  async start() {
    await this.sign();
    // await this.getTaskList();
  }
  objKeySort(t: any) {
    const n: any = {};
    Object.keys(t)
      .sort()
      .forEach((key) => {
        if (key != null && key != 'null') n[key] = t[key];
      });
    return n;
  }
  genTokenSign(li = this.li) {
    const e = {
      nonceStr: generateUuid().replace(/-/g, '').toLocaleLowerCase(),
      timestamp: new Date().getTime(),
      tokenSign: li,
    };
    e.tokenSign += e.nonceStr;
    e.tokenSign += e.timestamp;
    e.tokenSign += atob('SjdoOCZeQmdzNSNibio3aG4lIT1raDMwOCpidjIhc14=');
    e.tokenSign = md5(e.tokenSign);
    return e;
  }
  genXmSign(params: any) {
    let q = '';
    const m = {
      nonceStr: generateUuid().replace(/-/g, '').toLocaleLowerCase(),
      xmTimestamp: new Date().getTime(),
      xmToken: this.xmToken,
    };

    params = this.objKeySort(Object.assign({}, params, m));

    Object.values(params).forEach((v) => {
      q += typeof v === 'object' ? JSON.stringify(v) : v;
    });
    // console.log('q:', q, params);

    const xmSign = md5(q + this.baseKey);
    return { xmSign, ...m };
  }
  async getUserToken() {
    if (this.xmToken) return this.xmToken;
    // const url = `https://p3720226302625sh3s-saas.xiaoman-activity.meta-xuantan.com/xm/token/getUserToken`;
    const query = this.genTokenSign();
    // const res = await y.httpGet(url, query);
    const headers = { ...this.genXmSign(query) };
    const { data: res } = await req.get('/xm/token/getUserToken', query, headers);
    console.log('getUserToken:', res);

    if (res.code != 0) {
      $.log(`账号[${this.index}] 获取用户token失败: ${res.desc}`, 'error');
      console.log(res);
      return '';
    }
    // xmToken
    req.setHeaders({ xmToken: res.data });
    this.xmToken = res.data;
    return res.data;
  }
  async getTaskList() {
    const headers = { ...this.genXmSign({}), functionId: '100540002' };
    const { data: res } = await req.get('/activity/function/task/get', {}, headers);

    if (res.data?.taskList?.length) {
      console.log(`账号[${this.index}] 任务列表:`, res.data.taskList);
      // todo: 完成任务
      // https://p3720226302625sh3s-saas.xiaoman-activity.meta-xuantan.com/activity/function/task/finish
      for (const task of res.data.taskList) {
        if (task.status !== 0 || task.taskNum <= task.finishNum) continue;

        console.log('task:', task.taskTile, `${task.finishNum}/${task.taskNum}`);
        const body = {
          actOpId: '84991480',
          actionId: 0,
          actionParams: {},
          taskId: task.taskId,
          timestamp: new Date().getTime(),
          functionId: '',
        };

        const { data: res } = await req.post('/activity/function/task/finish', body, {
          functionId: task.functionId || '100540002',
          ...this.genXmSign({ ...body, xmToken: this.xmToken }),
        });
        if (res.code == 0) {
          $.log(`账号[${this.index}] 任务[${task.taskTitle}]完成成功: ${res.desc}`);
        } else {
          $.log(`账号[${this.index}] 任务[${task.taskTitle}]完成失败: ${res.desc}`, 'error');
          console.log('finishTask:', res);
        }
      }
    } else {
      $.log(`账号[${this.index}] 获取任务列表失败: ${res.desc}`, 'error');
      console.log('getTaskList:', res);
    }

    return res;
  }
  async sign() {
    await this.getUserToken();
    if (!this.xmToken) return;

    await wait(1000 * 30, 1000 * 60);

    const body = { patchDate: dateFormat('yyyy-MM-dd', new Date()) };
    // const res = await y.httpPost2(url, body, 0);
    const { data: res } = await req.post('/sign/action', body, {
      functionid: '0',
      ...this.genXmSign({ ...body, xmToken: this.xmToken }),
    });
    if (res.code == 0) {
      $.log(`账号[${this.index}] 签到成功: ${res.desc}`);
    } else {
      $.log(`账号[${this.index}] 签到失败: ${res.desc}`, 'error');
      console.log('sign:', res);
    }
    return res;
  }
}
// process.env.jwyb_urls = '';
$.init(UserInfo, 'jwyb_urls').then(() => $.done());
