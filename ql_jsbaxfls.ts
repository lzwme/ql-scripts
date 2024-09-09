/**
 cron: 40 8 * * *
 new Env('杰士邦安心福利社-小程序')
 环境变量: jsbaxfls 抓取 https://xh-vip-api.a-touchin.com/mp/sign/applyV2 请求头 Headers 中 access-token 的值 多账户 & 或换行分割，或新建同名变量
 */

import { Env } from './utils';
const $ = new Env('杰士邦安心福利社-小程序');

class UserInfo {
  private nick_name = '';
  constructor(token: string, private index: number) {
    console.log(token);
    $.req.setHeaders({
      'access-token': token,
      referer: 'https://servicewechat.com/wx9a2dc52c95994011/98/page-frame.html',
      'user-agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090b19)XWEB/11253',
      platform: 'MP-WEIXIN',
      connection: 'keep-alive',
      charset: 'utf-8',
      'content-type': 'application/json;charset=utf-8',
      'accept-encoding': 'gzip,compress,br,deflate',
      sid: '10009',
    });
  }
  async start() {
    if (!(await this.userInfo())) return false;
    await this.signInInfo();
    await this.taskShare();

    return true;
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
  async userInfo() {
    try {
      const { data: result } = await $.req.get<Res<{ userInfo: any }>>(`https://xh-vip-api.a-touchin.com/mp/user/info`);
      if (result.status == 200) {
          this.nick_name = result.data.userInfo.nick_name;
        $.log(`✅账号[${this.index}][${this.nick_name}]  当前积分[${result.data.userInfo.points}]🎉`);
        return true;
      } else {
        $.log(`❌账号[${this.index}]  获取用户信息失败[${result.message}]`);
        console.log(result);
        return false;
      }
    } catch (e) {
      console.log(e);
      $.log(`❌${(e as Error).message}`);
      return false;
    }
  }
  async signInInfo() {
    try {
      const { data: result } = await $.req.get<Res>(`https://xh-vip-api.a-touchin.com/mp/sign/infoV2`);
      if (result.status == 200) {
        $.log(`✅账号[${this.nick_name}]  当天签到状态[${result.data.today_is_signed}]🎉`);
        if (!result.data.today_is_signed) {
          await this.taskSignIn();
        }
      } else {
        $.log(`❌账号[${this.nick_name}]  当天签到状态[${result.message}]`);
        console.log(result);
      }
    } catch (e) {
      console.log(e);
    }
  }
  async taskSignIn() {
    try {
      const { data: result } = await $.req.get<Res>(`https://xh-vip-api.a-touchin.com/mp/sign/applyV2`);
      if (result.status == 200 || String(result.message).includes('ok')) {
        $.log(`✅账号[${this.nick_name}]  签到执行状态[${result.message}]🎉`);
      } else {
        $.log(`❌账号[${this.nick_name}]  签到执行状态[${result.message}]`);
        console.log(result);
      }
    } catch (e) {
      console.log(e);
    }
  }
  async taskShare() {
    try {
      const { data: result } = await $.req.get<Res>(
        `https://xh-vip-api.a-touchin.com/mp/guess.home/share?project_id=pages%2Fguess%2Findex%3Fproject_id%3D333480658633344`
      );
      if (result.status == 200) {
        $.log(`✅账号[${this.nick_name}]  分享执行状态[${result.message || result.msg}]🎉`);
      } else {
        $.log(`❌账号[${this.nick_name}]  分享执行状态[${result.message || result.msg}]`);
        console.log(result);
      }
    } catch (e) {
      console.log(e);
    }
  }
}
// process.env.jsbaxfls = '';
$.init(UserInfo, 'jsbaxfls').then(() => $.done());

interface Res<T = any> {
  status: number;
  message: string;
  msg?: string;
  data: T;
}
