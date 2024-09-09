/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-05-23 09:25:24
 * @Description: ikuuu机场签到。注册： https://ikuuu.pw/auth/register?code=75PU

 cron: 20 9 * * *
 环境变量： IKUUU，必填。格式： 邮箱#密码，也可以是 cookie（有效期一个星期）。多个账户以 & 或 \n 换行分割
 环节变量： SSPANEL_HOST，可选。可以指定任何基于 SSPANEL 搭建的机场用于签到
  示例：process.env.IKUUU=邮箱1#密码1&邮箱2#密码2
  或：process.env.IKUUU=cookie1&cookie2
 */
import { Env } from './utils';

const $ = new Env('ikuuu机场签到');

async function getIkuuuHost() {
  if (process.env.SSPANEL_HOST) return process.env.SSPANEL_HOST;
  let host = 'https://ikuuu.pw';
  try {
    const {data:html} = await $.req.get<string>('https://ikuuu.club', {}, { 'content-type': 'text/html' });
    host = /<p><a href="(https:\/\/[^"]+)\/?"/g.exec(html)?.[1] || host;
  } catch (e) {
    console.error((e as Error).message);
  }
  return host.replace(/\/$/, '');
}

export async function signCheckIn(cfg: string) {
  const [email, passwd, HOST = await getIkuuuHost()] = cfg.split('#');
  const url = {
    login: `${HOST}/auth/login`,
    checkin: `${HOST}/user/checkin`,
  };
  let cookie = passwd ? '' : email;
  const cache = $.storage.getItem(`ikuuu_cookie`) || {};
  const cacheKey = `${HOST}_${email}`;

  if (email && passwd) {
    cookie = cache[cacheKey];
    if (cookie) {
      $.log(`使用缓存 cookie: ${cookie}`);
      $.req.setCookie(cookie);
      if (await checkin(url.checkin, true)) return;
      cookie = '';
    }
  }

  if (!cookie) {
    const { data, headers } = await $.req.post(url.login, { email, passwd });
    if (data.ret === 1) {
        cookie = headers['set-cookie']!.map(d => d.split(';')[0]).join(';');
        $.log(data.msg || `登录成功！`);
        cache[cacheKey] = cookie;
        $.storage.setItem(`ikuuu_cookie`, cache);
    } else {
      $.log(data.msg || `登录失败！`, 'error');
      return;
    }
  }

  $.req.setCookie(cookie);
  return checkin(url.checkin);
}

async function checkin(url: string, isUseCache = false) {
  console.log('checkin url:', url);
  const { data } = await $.req.request('POST', url, {}, {}, false);
  if (data.ret === 1 || String(data.msg).includes('签到过')) {
    $.log(`签到成功！${data.msg}`);
    return true;
  } else {
    $.log(`❌签到失败：${data.msg}`, isUseCache ? 'info' : 'error');
  }
  return false;
}

// process.env.IKUUU = '';
if (require.main === module) $.init(signCheckIn, 'IKUUU').then(() => $.done());
