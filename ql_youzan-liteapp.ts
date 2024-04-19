/*
 * @Author: renxia
 * @Date: 2024-04-01 09:34:40
 * @LastEditors: renxia
 * @LastEditTime: 2024-04-08 11:59:08
 * @Description: 有赞小程序签到
 * @see https://github.com/dreamtonight/js/blob/main/youzan.js
 *
 * new Env('有赞小程序签到');
 * cron: 55 8 * * *
 * 环境变量： youzan_le_data 。格式：checkinId:sessionId##desc，多账号 @、& 或换行 分割。
 *  checkinId 为 url 中的参数
 *  sessionId 为 Cookie 中 KDTWEAPPSESSIONID 的值
 *  desc 可选。
 */

import { Env } from './utils';

const $ = new Env('有赞小程序签到', { sep: ['@', '&', '\n'] });
const pd_map = {
  '1479428': 'ffit8',
  '2187565': '蜜蜂惊喜社',
  '2050884': '伯喜线上商城',
  '1631': '云南白药',
  '3262': 'TOIs朵茜情调生活馆',
  '9332': '三只松鼠旗舰店',
  '12307': 'colorkey珂拉琪旗舰店',
  '16453': 'PMPM',
  '17666': '爱依服商城-总店',
  '1465878': '隅田川旗舰店',
  '1595664': '参半口腔护理',
  '1597464': 'Xbox俱乐部',
  '1876007': 'FLORTTE花洛莉亚',
  '1903120': 'KIMTRUE且初',
  '1985507': '肤漾FORYON',
  '2176467': 'chillmore且悠',
  '2299510': '燕京啤酒电商旗舰店',
  '2386563': 'HBN品牌店',
  '2646845': '海贽医疗科技',
  '2910869': 'ficcecode菲诗蔻官方旗舰店',
  '2923467': '红之旗舰店',
  '3014060': 'LAN蘭',
  '3347128': '松鲜鲜官方旗舰店',
  '8249': '贝因美贝家商城',
  '18415': '得宝Tempo',
  '2713880': '莱克旗舰店',
  '2905214': '百事可乐',
  '13968': '圣牧有机官方商城',
  '3124': '东鹏特饮微店',
  '1380': '幸福西饼',
  '8': '韩都严选',
  '1220': '良品铺子官方商城', // 连续签到领优惠券
  '1700': '中粮-健康生活甄选',
  '2983020': '盘龙云海健康家', // 连续签到60天送 50 券
  '379': '燕之坊五谷为养官方商城', // 连续签到 10、20、30 天送券
  '1123': '有间全球购', // 积分+现金购物。不是很划算
};
// 黑名单，已不再支持签到
const pd_black = new Set<number | string>([
  1985111, // 'INTOYOU心慕与你', // 已无签到
  3520910, // 'a chock官方', // 打不开
  1579, // '等蜂来天然蜂蜜旗舰店', // 积分换满减优惠券。不划算
  '央广甄选购物',
  '云南白药生活',
  '奈雪的茶商城',
  '东鹏特饮官方微店', // 可签到但无礼物兑换
]);

type Res<T = any> = {
  code: number;
  msg: string;
  data: T;
};

class Task {
  private checkinId: string = '';
  private sessionId: string = '';
  constructor(str: string, _idx: number, private desc: string = '') {
    [this.checkinId, this.sessionId] = str.split(':');
    $.req.setHeaders({
      'extra-data': `{"is_weapp": 1, sid: "${this.sessionId}"}`,
      cookie: this.sessionId.includes('KDTWEAPPSESSIONID') ? this.sessionId : `KDTWEAPPSESSIONID=${this.sessionId}`,
      'user-agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x6309092b) XWEB/9079',
    });
  }
  isInBlackList() {
    return [...pd_black].some(d => d === this.checkinId || String(this.desc).includes(String(d)));
  }
  async start() {
    try {
      $.log(`开始执行签到任务：[${pd_map[this.checkinId as keyof typeof pd_map] || this.checkinId}]${this.desc}`, 'D');
      if (await this.signin()) await this.getCustomerPoints();
      await $.wait(2000, 1000);
    } catch (error) {
      $.log(`❌ 发生错误：${(error as Error).message}`, 'error');
    }
  }
  async signin() {
    const url = `https://h5.youzan.com/wscump/checkin/checkinV2.json?checkinId=${this.checkinId}`;
    const { data: result } = await $.req.get<Res<{ list: any[] }>>(url, {}, {}, { rejectUnauthorized: false });
    // console.log(result);
    if (result?.code == 0) {
      $.log(`签到成功！获得${result?.data?.list[0]?.infos?.title}`, 'D');
    } else {
      if (result?.msg.includes('无法参与')) $.log(`已签到过了：${result.msg}`, 'D');
      else {
        // 仅在白名单内的执行通知
        if (!this.isInBlackList()) $.log(`签到失败！${result?.msg || JSON.stringify(result)}`, 'error');
        return false;
      }
    }

    return true;
  }
  async getCustomerPoints() {
    const { data: result } = await $.req.get<Res<{ currentAmount: number; userId: number }>>(
      `https://h5.youzan.com/wscump/pointstore/getCustomerPoints.json`,
      {},
      {},
      { rejectUnauthorized: false }
    );
    // console.log(result);
    if (result.code == 0) $.log(`当前积分: ${result.data.currentAmount}`, 'D');
    else $.log(`查询积分失败！${result.msg}`);
  }
}

// 读取自定义的黑名单
if (process.env.youzan_le_id_blacklist) {
  process.env.youzan_le_id_blacklist.split(',').forEach(d => {
    const [id, _desc] = d.split(':');
    if (+id && !pd_black.has(+id)) pd_black.add(+id);
  });
}

// process.env.youzan_le_data = '';
if (require.main === module) $.init(Task, 'youzan_le_data').then(() => $.done());
