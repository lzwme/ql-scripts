/*
 * @Author: renxia
 * @Date: 2024-02-23 13:52:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-09-10 21:57:48
 *
 cron: 25 7 * * *
 new Env('阿里云盘签到')
 环境变量: alyp 抓取请求中的 refresh_token。多账户用 @ 或换行分割
 */

import { Env } from './utils';
const $ = new Env('阿里云盘签到', { sep: ['@', '\n'] });

class UserInfo {
  private access_token = '';
  private nick_name = '';
  private signInDay = 1;
  constructor(private refresh_token: string, private index: number) {}
  async start() {
    let { data: res } = await $.req.post(`https://auth.aliyundrive.com/v2/account/token`, {
      grant_type: 'refresh_token',
      refresh_token: this.refresh_token,
    });
    if (res.status == 'enabled') {
      this.access_token = res.access_token;
      this.nick_name = res.nick_name;
      await this.sign();
    } else $.log(`❌账号[${this.nick_name}] 更新token失败`), console.log(res);
  }
  async sign() {
    // todo: 获取限时任务
    // 'https://member.alipan.com/v2/activity/sign_in_info' data.result.rewards[]

    const { data: res } = await $.req.post(
      `https://member.aliyundrive.com/v1/activity/sign_in_list`,
      { isReward: false },
      { authorization: `Bearer ${this.access_token}` }
    );

    if (res.success == true) {
      this.signInDay = res.result.signInCount;
      const o = this.signInDay - 1;
      $.log(`账号 [${this.nick_name} ] 签到成功 ${res.result.signInLogs[o].calendarChinese} \n ${res.result.signInLogs[o].reward.notice}`);
      await this.reward();
    } else {
      $.log(`❌账号[${this.index}]  签到失败`);
      console.log(res);
    }

    await this.Sendtg_bot();
  }
  async reward() {
    return $.log('请手动领取签到奖励');
    const { data: res } = await $.req.post(
      `https://member.aliyundrive.com/v1/activity/sign_in_reward`,
      { signInDay: this.signInDay, month: (new Date().getMonth() + 1) },
      { authorization: `Bearer ${this.access_token}` }
    );

    if (res.success == true) {
      $.log(` ${res.result.description || res.result.notice}  `);
    } else {
      $.log(`❌账号[${this.index}]  领取奖励失败`, 'error');
      console.log(res);
    }
  }
  async Sendtg_bot() {
    const tg_token = process.env.tg_token;
    const tg_chatId = process.env.tg_chatId;
    if (!tg_token || !tg_chatId) return;

    const TelegramBot = require('node-telegram-bot-api');
    const bot = new TelegramBot(tg_token);
    return bot.sendMessage(tg_chatId, $.getMsgs());
  }
}
// process.env.alyp = '';
$.init(UserInfo, 'alyp').then(() => $.done());
