/*
 * @Author: renxia
 * @Date: 2024-07-10 21:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-09-09 16:01:17
 * @Description: 古井贡酒会员中心小程序

 cron: 55 8 * * *
 环境变量： gujing 抓包 https://scrm.gujing.com/gujing_scrm/ 请求里面的 access-token
  示例：export gujing="eyJxxxxxxxxxxxxxxxxxxxxxxxxxxxx##memberId"
 */
import { Env } from './utils';

const $ = new Env('古井贡酒会员中心小程序');

export async function signCheckIn(token: string) {
  $.req.setHeaders({
    'access-token': token,
    Accept: 'application/json, text/plain, */*',
    'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Android WebView";v="122"',
    'Content-Type': 'application/json;charset=UTF-8',
    Origin: 'https://scrm.gujing.com',
    'X-Requested-With': 'com.tencent.mm',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'user-agent':
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x1800323c) NetType/WIFI Language/zh_CN miniProgram/wxba9855bdb1a45c8e',
  });

  const params = {
    activityId: '110001000',
    preview: false,
  };

  const r = await $.req.post<any>('https://scrm.gujing.com/gujing_scrm/wxclient/mkt/activities/sign:search', params);
  //   console.log(result);

  if (r.data?.code == 200) {
    if (r.data.content.signed !== 1) {
      $.log(`未签到 ===> 签到ing`);
      const { data } = await $.req.post<any>('https://scrm.gujing.com/gujing_scrm/wxclient/mkt/activities/sign:join', params);
      if (data.code == 200 && data.content?.point) {
        $.log(`签到成功！获取积分 ${r.data.content.point}`);
      } else {
        console.log(data);
        $.log(`签到失败！${data.chnDesc}`, 'error');
      }
    } else {
      $.log(`已签到 ===> 什么都不做`);
    }
  } else {
    $.log(`签到失败 [${JSON.stringify(r.data)}]`, 'error');
  }
}

// process.env.gujing = '';
if (require.main === module) $.init(signCheckIn, 'gujing').then(() => $.done());
