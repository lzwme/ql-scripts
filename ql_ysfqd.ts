/*
 * @Author: renxia
 * @Date: 2024-02-23 13:52:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-02-23 15:37:32
 *
 cron: 15 7 * * *
 new Env('云闪付签到')
 环境变量: ysfqd_data， 多账户用 @ 或换行分割。抓取 https://youhui.95516.com/newsign/api 请求 headers 中 Authorization
 */

import { Env } from './utils';

const $ = new Env('云闪付签到', { sep: ['@', '\n'] });
$.init(signIn, 'ysfqd_data').then(() => $.done());

async function signIn(auth: string) {
  const { data: result } = await $.req.post(
    'https://youhui.95516.com/newsign/api/daily_sign_in',
    {},
    {
      Authorization: `Bearer ${auth.replace('Bearer ', '')}`,
      'User-Agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 /sa-sdk-ios/sensors-verify/analytics.95516.com?production   (com.unionpay.chsp) (cordova 4.5.4) (updebug 0) (version 929) (UnionPay/1.0 CloudPay) (clientVersion 189) (language zh_CN) (upHtml) (walletMode 00) ',
    }
  );

  if ('signedIn' in result) {
    $.log(`今天是第${result['signInDays']['current']['days']}天签到 今日已签到成功,目前已连续签到${result['signInDays']['days']}天🎉`);
  } else {
    $.log(`用户查询:失败 ❌ 了呢,原因未知！`);
    console.log(result);
  }
}
