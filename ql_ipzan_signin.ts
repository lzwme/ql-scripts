/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-09-10 11:58:47
 * @Description: 品赞 HTTP 代理签到。品赞是一个HTTP优质代理IP服务供应商。

 const $ = new Env("品赞代理签到");
 cron: 10 0 * * 0

 环境变量： export IPZAN_ACCOUNT="phone=手机号;pwd=密码;token=xxx"

    phone: 登录账号  pwd: 登录密码
    token: （可选）抓取请求 header 中的 Authorization 设置为 token 值。但容易超时失效

    多账号使用换行或 & 分割。
    token 与 账号密码取其一即可。若担心设置账号与密码会泄露，可只设置为 token 值。但容易超时失效

 奖励：每周签到得 3 金币（1 金币约等于 1 块钱），可获取有效期 3分钟的 IP 约 500 次。代理 IP 可用于多账号任务并发执行，避免被检测到而封号
 注册地址： https://www.ipzan.com?pid=e9rdab1c  注册赠送 10 金币，可免费获取时效 3 分钟的 IP 代理 1666 次
 */

import { cookieParse } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('品赞代理签到');

export async function signCheckIn(cookie: string) {
  const info = cookieParse(cookie);

  if (info.phone && info.pwd) {
    if (false === (await login(info.phone, info.pwd))) return;
  } else if (info.token) $.req.setHeaders({ authorization: info.token });
  else return $.log('品赞代理签到: 未设置账号与密码或 token');

  const { data: pRes } = await $.req.get('https://service.ipzan.com/home/userWallet-receive');

  if (pRes.code === 0 || String(pRes.message).includes('已领取')) $.log(`签到成功：${pRes.message}`);
  else {
    $.log(`签到失败: ${pRes.message}`);
    console.error(pRes);
  }
}

export async function login(phone: string, password: string) {
  const cacheKey = `ipzan_token_${phone}`;
  const d = $.storage.getItem(cacheKey);

  if (d && Date.now() - d.t < 24 * 60 * 60 * 1000) {
    $.req.setHeaders({ authorization: d.token });
    return true;
  }

  let e = c.encode(''.concat(phone, 'QWERIPZAN1290QWER').concat(password));
  let t = '';
  for (let o = 0; o < 80; o++) t += Math.random().toString(16).slice(2);
  e = ''
    .concat(t.slice(0, 100))
    .concat(e.slice(0, 8))
    .concat(t.slice(100, 200))
    .concat(e.slice(8, 20))
    .concat(t.slice(200, 300))
    .concat(e.slice(20))
    .concat(t.slice(300, 400));

  const params = {
    account: e,
    source: 'ipzan-home-one',
  };
  const { data } = await $.req.post<{ code: number; message: string; data: string }>('https://service.ipzan.com/users-login', params);

  if (data.code !== 0) $.log(`登录失败: ${data.message}`, 'error');
  else {
    $.req.setHeaders({ authorization: data.data });
    $.storage.setItem(cacheKey, { token: data.data, t: Date.now() });
  }

  return data.code === 0;
}

const c = {
  // prettier-ignore
  table: ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "/"],
  UTF16ToUTF8: function (e: string) {
    for (var t = [], n = e.length, i = 0; i < n; i++) {
      var r,
        o,
        s = e.charCodeAt(i);
      0 < s && s <= 127
        ? t.push(e.charAt(i))
        : 128 <= s && s <= 2047
        ? ((r = 192 | ((s >> 6) & 31)), (o = 128 | (63 & s)), t.push(String.fromCharCode(r), String.fromCharCode(o)))
        : 2048 <= s &&
          s <= 65535 &&
          ((r = 224 | ((s >> 12) & 15)),
          (o = 128 | ((s >> 6) & 63)),
          (s = 128 | (63 & s)),
          t.push(String.fromCharCode(r), String.fromCharCode(o), String.fromCharCode(s)));
    }
    return t.join('');
  },
  UTF8ToUTF16: function (e: string) {
    for (var t = [], n = e.length, i = 0, i = 0; i < n; i++) {
      var r,
        o,
        s = e.charCodeAt(i);
      0 == ((s >> 7) & 255)
        ? t.push(e.charAt(i))
        : 6 == ((s >> 5) & 255)
        ? ((o = ((31 & s) << 6) | (63 & (r = e.charCodeAt(++i)))), t.push(String.fromCharCode(o)))
        : 14 == ((s >> 4) & 255) &&
          ((o = ((255 & ((s << 4) | (((r = e.charCodeAt(++i)) >> 2) & 15))) << 8) | (((3 & r) << 6) | (63 & e.charCodeAt(++i)))),
          t.push(String.fromCharCode(o)));
    }
    return t.join('');
  },
  encode: function (e: string) {
    if (!e) return '';
    for (var t = this.UTF16ToUTF8(e), n = 0, i = t.length, r = []; n < i; ) {
      var o = 255 & t.charCodeAt(n++);
      if ((r.push(this.table[o >> 2]), n == i)) {
        r.push(this.table[(3 & o) << 4]), r.push('==');
        break;
      }
      var s = t.charCodeAt(n++);
      if (n == i) {
        r.push(this.table[((3 & o) << 4) | ((s >> 4) & 15)]), r.push(this.table[(15 & s) << 2]), r.push('=');
        break;
      }
      var a = t.charCodeAt(n++);
      r.push(this.table[((3 & o) << 4) | ((s >> 4) & 15)]),
        r.push(this.table[((15 & s) << 2) | ((192 & a) >> 6)]),
        r.push(this.table[63 & a]);
    }
    return r.join('');
  },
  decode: function (e: string) {
    if (!e) return '';
    for (var t = e.length, n = 0, i = []; n < t; ) {
      let code1 = this.table.indexOf(e.charAt(n++));
      let code2 = this.table.indexOf(e.charAt(n++));
      let code3 = this.table.indexOf(e.charAt(n++));
      let code4 = this.table.indexOf(e.charAt(n++));
      let c1 = (code1 << 2) | (code2 >> 4);
      let c2, c3;

      i.push(String.fromCharCode(c1));
      -1 != code3 && ((c2 = ((15 & code2) << 4) | (code3 >> 2)), i.push(String.fromCharCode(c2)));
      -1 != code4 && ((c3 = ((3 & code3) << 6) | code4), i.push(String.fromCharCode(c3)));
    }
    return this.UTF8ToUTF16(i.join(''));
  },
};

// process.env.IPZAN_ACCOUNT = '';
if (require.main === module) $.init(signCheckIn, 'IPZAN_ACCOUNT').then(() => $.done());
