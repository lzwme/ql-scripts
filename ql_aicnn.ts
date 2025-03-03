/*
 * @Author: renxia
 * @Date: 2025-02-28 21:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2025-02-28 17:51:39
 * @Description: AICNN签到领积分 - 积分可以兑换大模型 API 调用量

  注册地址（使用此邀请注册可多得8888积分）：  http://aicnn.cn/loginPage?aff=4MvsDBGxfZ

  参考：提供免费额度大模型 API 的邀请注册（通过邀请方式注册，双方均可多得额度）
  - aicnn（送8888积分）：https://aicnn.cn/loginPage?aff=4MvsDBGxfZ
  - 硅基流动（送14元赠金）：https://cloud.siliconflow.cn/i/hDM9hDR6
  - 火山方舟（送145元赠金）：https://www.volcengine.com/experience/ark?utm_term=202502dsinvite&ac=DSASUQY5&rc=2D8BETN6
  - 派欧算力云（送50元赠金）：https://ppinfra.com/user/register?invited_by=XRMRL5

 cron: 30 8 * * *

 用法：
  - 环境变量：aicnn_token
  - 抓包 https://api.aicnn.cn/app-api/system/user/signin 请求里面的 authorization
  - 多账号使用 & 或换行符分割。示例：export aicnn_token="9c83d7144d7840a4ad4xxxxxxxxxxaad##memberId2&xxxxxx##memberId2"
 */
import { Env } from './utils';

const $ = new Env('AICNN签到领积分');

export async function signCheckIn(token: string) {
  $.req.setHeaders({
    authorization: `Bearer ${token.replace('Bearer ', '')}`,
    accept: 'application/json',
    referer: 'https://aicnn.cn',
    'user-agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0',
  });
  const { data } = await $.req.get<any>('https://api.aicnn.cn/app-api/system/user/signin');

  if (String(data?.msg).includes('已经签到过')) {
    $.log(data.msg);
  } else if (data?.code == 0) {
    // emoji 对钩
    $.log(`✅签到成功！${data.msg}`);
  } else {
    $.log(`签到失败！${data.msg}`, 'error');
    console.log(data);
  }
}

// process.env.aicnn_token = '';
if (require.main === module) $.init(signCheckIn, 'aicnn_token').then(() => $.done());
