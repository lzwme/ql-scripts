/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-04-02 14:12:13
 * @Description: 迪卡侬签到。奖励：积攒奖励金可换手机话费重置抵用券

 cron: 50 8 * * *
 环境变量： dkl_token 抓包 api-cn.decathlon.com.cn 请求 header 里面的 Authorization
  示例：export dkl_token="23fexxxxxxxxxxxxxxxxxxxxxxxxxxxx"
 */
import { Env } from './utils';

const $ = new Env('迪卡侬签到');

export async function signCheckIn(token: string) {
  const signUrl = 'https://api-cn.decathlon.com.cn/membership/membership-portal/mp/api/v1/business-center/reward/CHECK_IN_DAILY';
  $.req.setHeaders({
    Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}`,
    referer: 'https://servicewechat.com/wxdbc3f1ac061903dd/337/page-frame.html',
    'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x6309092b) XWEB/9079',
  });
  const { data: signRes } = await $.req.post(signUrl, {});

  if (+signRes.code == 0) {
    $.log(`签到成功，获取积分： ${signRes.data?.point_change}。当前可用积分：${signRes.data?.point_balance}`);
  } else if (String(signRes.code).includes('1006')) {
    $.log(`今日已签到 ${signRes.msg || JSON.stringify(signRes)}`);
  } else {
    console.error(signRes);
    $.log(`签到失败：${JSON.stringify(signRes.msg)}`, 'error');
  }
}

// process.env.dkl_token = '';
if (require.main === module) $.init(signCheckIn, 'dkl_token').then(() => $.done());
