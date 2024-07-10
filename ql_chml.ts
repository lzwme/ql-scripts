/*
 * @Author: renxia
 * @Date: 2024-07-10 21:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-07-10 21:05:00
 * @Description: 长虹美菱小程序签到

 cron: 50 8 * * *
 环境变量： chmlck 抓包 api.hellobike.com/api?urser 请求里面的 token。 ## 备注
  示例：export chmlck="eyJxxxxxxxxxxxxxxxxxxxxxxxxxxxx##13800000000"
 */
import { Env } from './utils';

const $ = new Env('长虹美菱小程序签到');

export async function signCheckIn(token: string) {
  const signUrl = 'https://hongke.changhong.com/gw/applet/aggr/signin?aggrId=608';
  const signRes = await fetch(signUrl, {
    method: 'post',
    headers: {
      'User-Agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x1800322d) NetType/WIFI Language/zh_CN',
      'Accept-Encoding': 'gzip, deflate',
      'content-type': 'application/json',
      Token: token.trim(),
    },
  }).then((d) => d.json());

  if (signRes.status_code == 200 || String(signRes.message).includes('已签到')) {
    $.log(`签到：${signRes.message}`);
  } else {
    console.error(signRes);
    $.log(`签到失败：${signRes.message || JSON.stringify(signRes)}`, 'error');
  }
}

// process.env.chmlck = '';
if (require.main === module) $.init(signCheckIn, 'chmlck').then(() => $.done());
