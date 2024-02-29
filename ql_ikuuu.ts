/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-03-05 10:08:27
 * @Description: ikuuu机场签到。注册： https://ikuuu.pw/auth/register?code=75PU

 cron: 20 10 * * *
 环节变量： IKUUU_HOST，可选。可以指定任何基于 SSPANEL 搭建的机场用于签到
 环境变量： IKUUU，必填。格式： 邮箱#密码，也可以是 cookie（有效期一个星期）。多个账户以 & 或 \n 换行分割
  示例：process.env.IKUUU=邮箱1#密码1&邮箱2#密码2
  或：process.env.IKUUU=cookie1&cookie2
 */
import { Env } from './utils';

const $ = new Env('ikuuu机场签到');
const HOST = process.env.IKUUU_HOST || 'https://ikuuu.pw';
const url = {
  login: `${HOST}/auth/login`,
  checkin: `${HOST}/user/checkin`,
  profile: `${HOST}/user/profile`,
};

export async function signCheckIn(cfg: string) {
  const [email, passwd] = cfg.split('#');
  let cookie = passwd ? '' : email;

  if (!cookie) {
    const { data, headers } = await $.req.post(url.login, { email, passwd });
    if (data.ret === 1) {
        cookie = headers['set-cookie']!.map(d => d.split(';')[0]).join(';');
        $.log(data.msg || `登录成功！`);
    } else {
      $.log(data.msg || `登录失败！`, 'error');
      return;
    }
  }

  $.req.setCookie(cookie);

  const { data } = await $.req.post(url.checkin, {});
  if (data.ret === 1 || String(data.msg).includes('签到过')) {
    $.log(`签到成功！${data.msg}`);
  } else {
    $.log(`❌签到失败：${data.msg}`, 'error');
  }
}

// process.env.IKUUU = '';
if (require.main === module) $.init(signCheckIn, 'IKUUU').then(() => $.done());
