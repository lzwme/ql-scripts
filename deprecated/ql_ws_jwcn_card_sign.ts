/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-09-05 13:40:37
 * @Description: 佳为软件，微信会员签到

 cron: 50 8 1 1 1
 环境变量： WS_JWCN_SIGN 抓包 https://ws.jwcn.net/weixinpl/card/card_sign.php?card_member_id= ，URL 中的 card_member_id、card_id 以及请求 cookie 里的 PHPSESSID，用；连接
  示例：export WS_JWCN_SIGN="card_member_id=xxx; card_id=1111; PHPSESSID=xxxx"
  多个账号用换行分隔
 */
import { cookieParse } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('奇奥超市签到');

export async function signCheckIn(WS_JWCN_SIGN: string) {
  const { card_member_id, card_id, PHPSESSID = '' } = cookieParse(WS_JWCN_SIGN);
  let url = `https://ws.jwcn.net/weixinpl/card/sign_score.php?callback=jsonpCallback_signscore&card_member_id=${card_member_id}&card_id=${card_id}`;
  let txt = await fetch(url).then(d => d.text());

  txt = txt.replaceAll('jsonpCallback_signscore', '').replace(/^\(/, '').replace(');', '');
  console.log(txt, card_member_id, card_id, PHPSESSID, url);

  if (/card_member_id:(\d+)/.exec(txt)) {
    $.log('签到成功！');
  } else {
    $.log(`签到失败!${txt}`, 'error');
  }

  url = `https://ws.jwcn.net/weixinpl/card/card_sign.php?card_member_id=${card_member_id}&card_id=${card_id}`;
  txt = await fetch(url, {
    headers: {
      cookie: `PHPSESSID=${PHPSESSID || ''}`,
      referer: `https://ws.jwcn.net/weixinpl/card/card_sign.php?card_id=`,
      'user-agent': `Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x18003231) NetType/WIFI Language/zh_CN`,
    },
  }).then(d => d.text());

  const m = /<p>(今日已签到.+)</.exec(txt);
  if (m) {
    $.log(m[1]);
  } else {
    console.log(txt);
    $.log(`获取积分信息失败`);
  }
}

// process.env.WS_JWCN_SIGN = '';
if (require.main === module) $.init(signCheckIn, 'WS_JWCN_SIGN').then(() => $.done());
