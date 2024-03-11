/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-03-29 09:31:00
 * @Description: 哈啰签到。奖励：积攒奖励金可换手机话费重置抵用券

 cron: 50 8 * * *
 环境变量： hlToken 抓包 api.hellobike.com/api?urser 请求里面的 token
  示例：export hlToken="23fexxxxxxxxxxxxxxxxxxxxxxxxxxxx"
 */
import { Env } from './utils';

const $ = new Env('哈啰签到');

export async function signCheckIn(hlToken: string) {
  // 签到接口
  const signUrl = 'https://api.hellobike.com/api?common.welfare.signAndRecommend';
  const signData = {
    from: 'h5',
    systemCode: 62,
    platform: 4,
    version: '6.46.0',
    action: 'common.welfare.signAndRecommend',
    token: hlToken,
    pointType: 1,
  };
  const { data: signRes } = await $.req.post(signUrl, signData);
  if (signRes.code === 0) {
    if (signRes.data.didSignToday === true) {
      $.log(`今日已签到成功 金币+${signRes.data.bountyCountToday}。${signRes.data.title}`);
    } else {
      $.log(`今日未签到，请检查TOKEN是否过期。`, 'error');
    }
  } else {
    console.error(signRes);
    $.log(`签到失败：${JSON.stringify(signRes.msg)}`, 'error');
    return;
  }

  const pointInfoUrl = 'https://api.hellobike.com/api?user.taurus.pointInfo';
  const pointInfoData = {
    from: 'h5',
    systemCode: 61,
    platform: 4,
    version: '6.46.0',
    action: 'user.taurus.pointInfo',
    token: hlToken,
    pointType: 1,
  };
  const { data: pRes } = await $.req.post(pointInfoUrl, pointInfoData);
  if (pRes.code === 0 && pRes.data) {
    const { points, expiring } = pRes.data;
    $.log(`可用奖励金为 ${points}，过期 ${expiring}`);
  } else {
    $.log(`查询奖励金信息失败: ${pRes.msg}`);
    console.error(pRes);
  }
}

// process.env.hlToken = '';
if (require.main === module) $.init(signCheckIn, 'hlToken').then(() => $.done());
