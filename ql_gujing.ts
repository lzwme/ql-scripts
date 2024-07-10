/*
 * @Author: renxia
 * @Date: 2024-07-10 21:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-07-10 21:05:00
 * @Description: 古井贡酒会员中心小程序

 cron: 55 8 * * *
 环境变量： gujing 抓包 https://scrm.gujing.com/gujing_scrm/ 请求里面的 access-token
  示例：export gujing="eyJxxxxxxxxxxxxxxxxxxxxxxxxxxxx##memberId"
 */
import { Env } from './utils';

const $ = new Env('古井贡酒会员中心小程序');

export async function signCheckIn(token: string, type: string) {
  const result = await fetch('https://scrm.gujing.com/gujing_scrm/wxclient/mkt/activities/sign:search', {
    method: 'POST',
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Linux; Android 10; MI 8 Lite Build/QKQ1.190910.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.6261.120 Mobile Safari/537.36 XWEB/1220089 MMWEBSDK/20240404 MMWEBID/8150 MicroMessenger/8.0.49.2600(0x28003156) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 miniProgram/wxba9855bdb1a45c8e',
      Accept: 'application/json, text/plain, */*',
      'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Android WebView";v="122"',
      'Content-Type': 'application/json;charset=UTF-8',
      'sec-ch-ua-mobile': '?1',
      'Access-Token': token,
      'sec-ch-ua-platform': '"Android"',
      Origin: 'https://scrm.gujing.com',
      'X-Requested-With': 'com.tencent.mm',
      'Sec-Fetch-Site': 'same-origin',
      'Sec-Fetch-Mode': 'cors',
      'Sec-Fetch-Dest': 'empty',
      'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    },
    body: JSON.stringify({
      activityId: '110001000',
      preview: false,
    }),
  }).then((d) => d.json());
//   console.log(result);

  if (result?.code == 200) {
    if (result.content.signed !== 1) {
      $.log(`未签到 ===> 签到ing`);
      if (type !== 'sign') await signCheckIn(token, 'sign');
    } else {
      $.log(`已签到 ===> 什么都不做`);
    }
  } else {
    $.log(`签到失败 [${JSON.stringify(result)}]`, 'error');
  }
}

// process.env.gujing = '';
if (require.main === module) $.init(signCheckIn, 'gujing').then(() => $.done());
