/**
 I茅台预约 v1.0

 cron: 20 9 * * *
 const $ = new Env("I茅台预约");

 执行 `tsx src/active/imaotai.ts -m <手机号>`，可以输入收到的验证码，并请求返回 token，并在当前文件夹下保存
 自行抓包并在 lzwme_ql_config.json5 文件中配置 config 信息

 支持环境变量配置方式（多个账号以 & 或换行分割）：
 export QL_IMAOTAI=token=xxx;tokenWap=xxx;city=北京市;province=北京市&token=xxx...
 */

import { Request, dateFormat, assign, md5, aesEncrypt, formatToUuid, color, sleep } from '@lzwme/fe-utils';
import { program } from 'commander';
import { IncomingHttpHeaders } from 'node:http';
import { homedir, hostname } from 'node:os';
import { resolve } from 'node:path';
import { getGeoByGD, getConfigStorage, sendNotify } from './utils';

const itemMap: Record<string, string> = {
  10213: '贵州茅台酒（癸卯兔年）',
  10056: '茅台1935',
  2478: '贵州茅台酒（珍品）',
  10214: '贵州茅台酒（癸卯兔年）x2',
  10941: '贵州茅台酒（甲辰龙年）',
  10942: '贵州茅台酒（甲辰龙年）x2',
};
const config = {
  /** 发送通知的方式 */
  notifyType: 1 as 0 | 1 | 2, // 0: 不通知； 1： 异常才通知； 2： 全都通知
  AMAP_KEY: '', // 高德地图 key，用于命令行方式登录获取经纬度，可以不用
  appVersion: '1.5.6', // APP 版本，可以不写，会尝试自动获取
  // 预约店铺策略。max: 最大投放量；maxRate: 近30日中签率最高；nearby: 距离最近店铺（默认）; keyword: shopKeywords 列表优先
  type: 'nearby' as 'max' | 'maxRate' | 'nearby' | 'keyword',
  shopKeywords: [], // 店铺白名单：用于指定高优先级的店铺，type=keyword 时，优先查找符合列表关键字的店铺申购
  shopKeywordsFilter: [], // 店铺黑名单：用于过滤不希望申购的店铺，避免距离过远无法去领取
  user: [
    {
      disabled: false, // 是否禁用
      mobile: '', // 手机号码，用于账号配置识别
      itemCodes: [] as string[], // ['10941', '10942'], // 要预约的类型，若不设置，默认过滤 1935 和 珍品
      province: 'xx省',
      city: 'xx市',
      shopKeywords: [] as string[], // 店铺白名单（优先级更高）：用于指定高优先级的店铺，若设置了该项，则优先查找符合列表关键字的店铺申购
      shopKeywordsFilter: [] as string[], // 店铺黑名单（优先级更高）：用于过滤不希望申购的店铺，避免距离过远无法去领取
      // 以下项可抓包获取
      lng: '', //经度
      lat: '', // 纬度
      deviceId: formatToUuid(md5(hostname() + homedir()))[0].toUpperCase(), // MT-Device-ID
      token: '', // MT-Token
      tokenWap: '', // MT-Token-Wap
      header: {
        // 自定义 header，抓包自己的 header，避免被识别为多设备登录的可能性
        h5: {
          'Client-User-Agent': 'iOS;15.0.1;Apple;iPhone 12 ProMax',
        } as IncomingHttpHeaders,
        app: {
          'User-Agent': 'iOS;16.0.1;Apple;iPhone 14 ProMax',
        } as IncomingHttpHeaders,
      },
    },
  ],
};
const defautUser = config.user[0];
config.user[0] = assign({} as any, defautUser);

const { green, red, cyan, cyanBright } = color;
const today = dateFormat('yyyy-MM-dd', new Date());
const time_keys = new Date(`${today}T00:00:00`).getTime();
const configStor = getConfigStorage('I茅台预约');
const cacheInfo = {
  info: {
    date: '',
    sessionInfo: {
      sessionId: 0,
      itemList: [] as Record<'title' | 'itemCode' | 'content', string>[],
    },
  },
  lottery: {} as { [shopId: string]: { [sessionId: string]: { [itemCode: string]: ILottery } } },
};
const cacheStor = getConfigStorage<Partial<typeof cacheInfo>>('I茅台预约缓存', resolve(process.cwd(), 'cache/imaotai-cache.json5'));

const req = new Request('', {
  'MT-User-Tag': '0',
  'Accept-Language': 'zh-Hans-CN;q=1, en-CN;q=0.9',
  'Accept-Encoding': 'gzip, deflate, br',
  userId: '1',
  'mt-token': '2',
});
const mt_r = 'clips_OlU6TmFRag5rCXwbNAQ/Tz1SKlN8THcecBp/';
const AES_KEY = 'qbhajinldepmucsonaaaccgypwuvcjaa';
const AES_IV = '2018534749963515';
const SALT = '2af72f100c356273d46284f6fd1dfc08';
const imaotai = {
  debug: process.env.DEBUG === '1',
  /** 所有的店铺信息 */
  mall: {} as {
    [shopId: string]: IShopInfo;
  },
  /** 是否发生了处理异常 */
  hasError: false,
  user: { ...defautUser },
  async getMap() {
    if (!Object.keys(this.mall).length) {
      const res = await req.get('https://static.moutai519.com.cn/mt-backend/xhr/front/mall/resource/get');
      const r = await req.get(res.data.data.mtshops_pc.url, {}, { 'content-type': 'application/json' });
      this.mall = r.data;
    }
    return this.mall;
  },
  async mtAdd(itemId: string, shopId: string, sessionId: number, userId: string) {
    const MT_K = Date.now().toString();
    const { data: mtv } = await req.get<string>(
      `http://82.157.10.108:8086/get_mtv?DeviceID=${this.user.deviceId}&MTk=${MT_K}&version=${config.appVersion}&key=yaohuo`,
      {},
      { 'content-type': 'text/html' }
    );
    const headers = this.getHeaders({ 'MT-K': MT_K, 'MT-V': mtv });
    const d = { itemInfoList: [{ count: 1, itemId }], sessionId: sessionId, userId: String(userId), shopId: String(shopId) };
    const actParam = aesEncrypt(JSON.stringify(d), AES_KEY, 'aes-256-cbc', AES_IV).toString('base64');
    const params = { ...d, actParam };
    const r = await req.post('https://app.moutai519.com.cn/xhr/front/mall/reservation/add', params, headers);
    if (this.debug) console.log('[mtAdd]', r.data);
    if (r.data.code == 2000) return r.data?.data?.successDesc || '未知';
    return '申购失败:' + (r.data.message || JSON.stringify(r.data));
  },
  async getSessionId() {
    if (cacheInfo.info.date !== today) {
      const r = await req.get<{ data: { itemList: any[]; sessionId: number } }>(
        `https://static.moutai519.com.cn/mt-backend/xhr/front/mall/index/session/get/${time_keys}`
      );
      if (!r.data.data?.sessionId) console.log('获取 sessionId 失败', JSON.stringify(r.data));
      else {
        cacheInfo.info.date = today;
        cacheInfo.info.sessionInfo = r.data.data;
        cacheStor.save({ info: cacheInfo.info });
      }
    }
    return cacheInfo.info.sessionInfo || {};
  },
  /** 查询所在省市的投放产品和数量 */
  async queryMallShopList(sessionId: number, itemId: string, province: string, city?: string) {
    // https://static.moutai519.com.cn/mt-backend/xhr/front/mall/shop/list/slim/v3/837/%E9%87%8D%E5%BA%86%E5%B8%82/10213/1701100800000
    const url = `https://static.moutai519.com.cn/mt-backend/xhr/front/mall/shop/list/slim/v3/${sessionId}/${province}/${itemId}/${time_keys}`;
    const r = await req.get<{
      code: number;
      data: {
        shops: { shopId: string; items: MallShopItem[] }[];
        validTime: number;
        items: { title: string; itemId: string; price: string }[];
      };
    }>(url);
    const data = r.data.data;
    if (!data) {
      console.error(`【${city}】未获取到投放店铺数据`, r.data);
      return;
    }
    if (city) {
      data.shops = data.shops.filter(shop => this.mall[shop.shopId]?.cityName === city);
    }
    return data;
  },
  /** 查询投放量，返回要预约的店铺 id */
  async getShopItem(sessionId: number, itemId: string, province: string, city: string) {
    const data = await this.queryMallShopList(sessionId, itemId, province, city);
    const selectedShopItem: { shopId: string; item?: MallShopItem } = { shopId: '' };

    if (!data) return;

    data.shops = data.shops.filter(s => this.mall[s.shopId]);

    // 黑名单关键词过滤
    if (this.user.shopKeywordsFilter?.length > 0) {
      data.shops = data.shops.filter(shop => {
        const shopInfo = this.mall[shop.shopId];
        for (const keyword of this.user.shopKeywordsFilter) {
          if (shopInfo.name.includes(keyword) || shopInfo.name.includes(keyword)) return false;
        }
        return true;
      });
    }

    // 白名单关键词优先
    if (config.type === 'keyword') {
      for (const keyword of this.user.shopKeywords) {
        const t = data.shops.find(shop => {
          const shopInfo = this.mall[shop.shopId];
          if (!shopInfo || (!shopInfo.name.includes(keyword) && !shopInfo.fullAddress.includes(keyword))) return false;

          const item = shop.items.find(d => d.itemId == itemId);
          if (!item) return false;
          selectedShopItem.shopId = shop.shopId;
          selectedShopItem.item = item;
          return true;
        });

        if (t) return selectedShopItem;
      }
    }

    // 最大申购率店铺
    if (config.type === 'maxRate') {
      const r = await this.cityLotteyStat(this.user.city, [itemId]);

      for (const maxItem of r[itemId].list) {
        const shop = data.shops.find(d => d.shopId === maxItem.shop.shopId);
        if (shop) {
          const item = shop.items.find(d => d.itemId == itemId);
          if (item) {
            // console.log(`选取近N天中签率最高的店铺：[${maxItem.shop.name}][${maxItem.rate}%]`);
            selectedShopItem.shopId = shop.shopId;
            selectedShopItem.item = item;
            return selectedShopItem;
          }
        }
      }
    }

    for (const shop of data.shops) {
      const item = shop.items.find(d => d.itemId == itemId);
      if (!item) continue;

      if (!selectedShopItem.item || selectedShopItem.item.inventory < item.inventory!) {
        selectedShopItem.shopId = shop.shopId;
        selectedShopItem.item = item;

        if (config.type === 'nearby') return selectedShopItem;
      }
    }

    return selectedShopItem;
  },
  getHeaders(cheaders: IncomingHttpHeaders = {}, type: 'h5' | 'app' = 'app', setcookie = true) {
    const header: IncomingHttpHeaders = { 'MT-R': mt_r };

    if (type === 'app') {
      Object.assign(header, {
        Accept: '*/*',
        'MT-Bundle-ID': 'com.moutai.mall',
        'content-type': 'application/json',
        'MT-Network-Type': 'WIFI',
        'MT-User-Tag': '0',
        'MT-Info': '028e7f96f6369cafe1d105579c5b9377',
        'MT-Device-ID': this.user.deviceId,
        'MT-Lat': this.user.lat,
        'MT-Lng': this.user.lng,
        ...this.user.header.app,
      });
    } else {
      Object.assign(header, {
        Connection: 'keep-alive',
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json, text/javascript, */*; q=0.01',
        YX_SUPPORT_WEBP: '1',
        'MT-Device-ID-Wap': this.user.deviceId,
        ...this.user.header.h5,
      });
      if (setcookie && !header.cookie) {
        header.cookie = [`MT-Device-ID-Wap=${this.user.deviceId}`, `MT-Token-Wap='${this.user.tokenWap}`, 'YX_SUPPORT_WEBP=1'].join(';');
      }
    }

    header['MT-Request-ID'] = `${Date.now() * 100000 + Math.ceil(10000 * Math.random())}`;
    return Object.assign(header, cheaders);
  },
  async getUserId(): Promise<{ userName: string; userId: string; mobile: string }> {
    const { data: r } = await req.get('https://app.moutai519.com.cn/xhr/front/user/info', {}, this.getHeaders());

    if (r.code != 2000) {
      if (r.data?.version && r.data.version != config.appVersion) {
        console.log('不是最新的版本号', config.appVersion, r.data);
        config.appVersion = r.data.version;
        configStor.save(config);
        return this.getUserId() as any;
      }
      console.log(`[error][getuserid][${this.user.mobile}]:`, r);
    }
    return r.data || {}; // userName, userId, mobile
  },
  async getAppVersion(isSave = true) {
    const f = await req.get('https://apps.apple.com/cn/app/i%E8%8C%85%E5%8F%B0/id1600482450', {}, { 'content-type': 'text/html' });
    const r = String(f.data).match(/whats-new__latest__version.+(\d+\.\d+\.\d+)/);

    if (r && r[1] !== config.appVersion) {
      console.log(`获取到新版本：${config.appVersion} => ${r[1]}`);
      config.appVersion = r[1];
      if (isSave) configStor.save(config);
    }
    req.setHeaders({ 'MT-APP-Version': config.appVersion });
  },
  signature(data: Record<string, unknown>, timestamp = Date.now().toString()) {
    const keys = Object.keys(data).sort();
    const text = SALT + keys.map(k => data[k]).join('') + timestamp;
    return md5(text);
  },
  /** 获取手机验证码 */
  async getPhoneCode(mobile: string | number, timestamp = Date.now().toString()) {
    const params: Record<string, any> = { mobile };
    params.md5 = this.signature(params, timestamp);
    params.timestamp = timestamp;
    params['MT-APP-Version'] = config.appVersion;
    const headers = this.getHeaders({ 'mt-lat': this.user.lat, 'mt-lng': this.user.lng });
    const { data } = await req.post('https://app.moutai519.com.cn/xhr/front/user/register/vcode', params, headers);
    if (+data.code !== 2000) console.log(`发送验证码异常【${mobile}】：`, data);
    return data;
  },
  /** 指定城市中签率统计 */
  async cityLotteyStat(city = '广州市', itemCodes = ['10941', '10942', '10213', '10214']) {
    await imaotai.getMap();
    await imaotai.getSessionId();

    const shopList = Object.values(imaotai.mall).filter(d => d.cityName == city);
    const stats = {} as { [itemCode: string]: { list: Awaited<ReturnType<typeof shopLotteryStats>>[]; rankingDetail: string } };

    for (const itemCode of itemCodes) {
      stats[itemCode] = { list: [], rankingDetail: `【${cyanBright(itemMap[itemCode])}】【${cyan(city)}】近30日中签率统计排行：\n` };

      for (const shop of shopList) {
        const info = await shopLotteryStats(shop, { itemCode, days: 30, tryUpdateFailed: false });
        if (info.rate) stats[itemCode].list.push(info);
        else if (imaotai.debug) console.log(` > 获取中签率失败：${itemMap[itemCode]} ${shop.name}`);
      }

      stats[itemCode].list = stats[itemCode].list.sort((a, b) => b.rate - a.rate);
      stats[itemCode].rankingDetail += stats[itemCode].list
        .map(
          (d, i) =>
            `[${String(i + 1).padStart(2, '0')}] ${green(d.rate)}% (${cyan(d.hitCntTotal)}/${cyanBright(d.reservationCntTotal)}) [${
              d.shop.name
            }]`
        )
        .join('\n');
    }

    if (imaotai.debug) {
      for (const itemCode of itemCodes) console.log(`\n${stats[itemCode].rankingDetail}\n\n`);
    }

    return stats;
  },
  /** 登录 */
  async login(mobile: string | number, vCode: string) {
    const params: Record<string, any> = {
      mobile,
      vCode,
      ydToken: '',
      ydLogId: '',
    };
    const timestamp = Date.now().toString();
    params.md5 = this.signature(params, timestamp);
    params.timestamp = timestamp;
    params.MT_APP_Version = config.appVersion;

    const { data } = await req.post<{
      code: number;
      data: { token: string; userId: number; cookie: string; did: string; verifyStatus: number; idCode: string; birthday: string };
    }>('https://app.moutai519.com.cn/xhr/front/user/register/login', params, this.getHeaders());
    console.log('\n', data.data?.token ? '[login]:' : '登录失败，请重试：', data);
    if (data.data?.verifyStatus !== 1) console.warn('请注意，该账号尚未实名认证');
    return data.data;
  },
  /**  领取连续申购奖励 */
  async getUserEnergyAward() {
    const headers = this.getHeaders({ Referer: 'https://h5.moutai519.com.cn/gux/game/main?appConfig=2_1_2' }, 'h5');
    const r = await req.post('https://h5.moutai519.com.cn/game/isolationPage/getUserEnergyAward', {}, headers);
    if (r.data.code !== 2000) this.hasError = true;
    return r.data.message || '领取奖励成功';
  },
  /** 领取 7 日连续申购 */
  async receive7DaysApplyingReward() {
    const qurl = 'https://h5.moutai519.com.cn/game/xmyApplyingReward/7DaysContinuouslyApplyingProgress';

    type R1 = Res<{ previousProgress: number; appliedToday: boolean; rewardReceived: boolean }>;
    const { data: r1 } = await req.post<R1>(qurl, {}, this.getHeaders({}, 'h5'));
    if (imaotai.debug) console.log(r1);
    if (r1.code !== 2000) {
      this.hasError = true;
      return r1.message || r1.error;
    }
    if (r1.data.rewardReceived) return '今日已领取';
    if (r1.data.previousProgress < 6) return `[${r1.data.previousProgress}]连续申购不满7日，无法领取`;

    const url = 'https://h5.moutai519.com.cn/game/xmyApplyingReward/receive7DaysContinuouslyApplyingReward';
    const { data: r2 } = await req.post<Res>(url, {}, this.getHeaders({}, 'h5'));
    if (imaotai.debug) console.log(r2);
    if (r2.code !== 2000) this.hasError = true;
    return r2.code == 2000 ? `领取小茅运 +${r2.data?.rewardAmount}` : r2.message;
  },
  /** 领取累计申购奖励 */
  async cumulativelyApplyingDays() {
    const qurl = 'https://h5.moutai519.com.cn/game/xmyApplyingReward/cumulativelyApplyingDays';
    type R1 = Res<{ previousDays: number; appliedToday: boolean; rewardReceived: Record<'7' | '14' | '21' | '28', boolean> }>;
    const { data: r1 } = await req.post<R1>(qurl, {}, this.getHeaders({}, 'h5'));
    if (imaotai.debug) console.log(r1);
    if (r1.code !== 2000) {
      this.hasError = true;
      return r1.message || r1.error;
    }

    let msg = '';
    for (const day of [7, 14, 21, 28] as const) {
      if (r1.data.rewardReceived[day]) continue;
      if (r1.data.previousDays + 1 < day) break;

      const url = `https://h5.moutai519.com.cn/game/xmyApplyingReward/receiveCumulativelyApplyingReward`;
      const { data: r2 } = await req.post<Res>(url, {}, this.getHeaders({}, 'h5'));
      if (imaotai.debug) console.log(r1);
      if (r2.code !== 2000) this.hasError = true;
      msg += `[累计申购${day}天]${r2.code == 2000 ? `领取小茅运 +${r2.data?.rewardAmount}` : r2.message}`;
    }

    return msg || `[累计申购${r1.data.previousDays + 1}天]无可领取奖励`;
  },
  async start(inputData = config) {
    const msgList = [];
    let userCount = 0;
    try {
      await this.getAppVersion();
      await this.getMap();
      const sessionInfo = await this.getSessionId();

      if (!sessionInfo.sessionId) {
        msgList.push(`获取 sessionId 失败: ${JSON.stringify(sessionInfo)}`);
        this.hasError = true;
      } else {
        for (let user of inputData.user) {
          userCount++;

          try {
            this.user = user = assign(
              {} as any,
              {
                ...defautUser,
                shopKeywords: inputData.shopKeywords,
                shopKeywordsFilter: inputData.shopKeywordsFilter,
              },
              user,
              {
                header: {
                  app: { 'MT-Token': user.token },
                  h5: { 'MT-Token-Wap': user.tokenWap },
                },
              } as Partial<typeof defautUser>
            );

            if (user.disabled || !user.token) continue;

            const { userName, userId, mobile } = await this.getUserId();
            if (!userId) {
              msgList.push(`第 ${userCount} 个用户 token 失效，请重新登录`);
              this.hasError = true;
              continue;
            }

            req.setHeaders({ userId });
            msgList.push(`第 ${userCount} 个用户【${userName}_${mobile}】开始任务-------------`);

            if (!user.itemCodes?.length || !user.itemCodes.some(d => sessionInfo.itemList.some(e => e.itemCode == d))) {
              user.itemCodes = sessionInfo.itemList
                .filter(d => {
                  return !['10056', '2478'].includes(d.itemCode);
                  // const title = String(d.title);
                  // return title.includes('贵州茅台酒') && !title.includes('珍品');
                })
                .map(d => d.itemCode);
            }

            for (const item of sessionInfo.itemList) {
              if (user.itemCodes.includes(item.itemCode)) {
                const shop = await this.getShopItem(sessionInfo.sessionId, item.itemCode, user.province, user.city);
                if (shop?.shopId) {
                  const shopInfo = this.mall[shop.shopId];
                  const r = await this.mtAdd(item.itemCode, shop.shopId, sessionInfo.sessionId, userId);
                  msgList.push(`选中店铺：【${shopInfo.name}】【${shopInfo.fullAddress}】【投放量：${shop.item!.inventory}】`);
                  msgList.push(`${item.itemCode}_${item.title}------${r}`);
                } else {
                  msgList.push(`【${item.itemCode}_${item.title}】未获取到可预约的店铺，未能预约`);
                  this.hasError = true;
                }
              }
            }

            msgList.push(`领取耐力值：${await this.getUserEnergyAward()}`);
            msgList.push(`领取七日连续申购奖励：${await this.receive7DaysApplyingReward()}`);
            msgList.push(`领取累计申购奖励：${await this.cumulativelyApplyingDays()}`);
          } catch (err) {
            console.error(err);
            msgList.push(`[${userCount}]error: ${(err as Error).message || JSON.stringify(err)}`);
            this.hasError = true;
          }
        }
      }
    } catch (err) {
      console.error(err);
      msgList.push(`error: ${(err as Error).message || JSON.stringify(err)}`);
    }
    console.log(`执行完毕。共执行了 ${userCount} 个账号`);

    await sendNotify('I茅台预约', msgList.join('\n'), { notifyType: config.notifyType, hasError: imaotai.hasError });
  },
};

async function promptLogin(opts: { login: boolean; force?: boolean }) {
  const { prompt } = (await import('enquirer')).default;
  const inputData = {
    AMAP_KEY: process.env.AMAP_KEY || config.AMAP_KEY,
    vcode: '',
  };
  const { mobile } = await prompt<{ mobile: string }>([
    {
      type: 'input',
      name: 'mobile',
      message: '请输入登录使用的 11 位手机号码',
      initial: '',
      validate: mobile => /\d{11}/.test(mobile) || '请输入正确的11位手机号码',
    },
  ]);

  const existUser = config.user.find(d => d.mobile === mobile);
  if (existUser) imaotai.user = existUser;
  imaotai.user.mobile = mobile;

  if (!imaotai.user.lat || opts.force) {
    if (!inputData.AMAP_KEY) {
      const { AMAP_KEY } = await prompt<{ AMAP_KEY: string }>({
        type: 'input',
        name: 'AMAP_KEY',
        initial: config.AMAP_KEY,
        message: '请输入高德地图 KEY （用于获取经纬度，没有则直接回车下一步）',
      });
      if (AMAP_KEY.length > 20) config.AMAP_KEY = inputData.AMAP_KEY = AMAP_KEY;
    }

    if (inputData.AMAP_KEY) {
      const { address } = await prompt<{ address: string }>([
        {
          type: 'input',
          name: 'address',
          message: '请输入您当前的位置或要预约的地点（如：北京市朝阳区xxx路xx小区）',
          initial: '',
          validate: address => address.length > 4 || '输入字符太少',
        },
      ]);
      const list = await getGeoByGD(address, inputData.AMAP_KEY);
      const { idx } = await prompt<{ idx: string }>({
        type: 'select',
        name: 'idx',
        message: '请选择最近的一个位置',
        choices: list.map(d => ({
          name: d.formatted_address,
          message: `地址：${d.formatted_address}, 定位：${d.location}`,
        })),
      });
      const item = list.find(d => d.formatted_address === idx) || list[0];
      const [lng, lat] = item.location.split(',');
      const t = {
        province: item.province,
        city: item.city,
        lat: +lat < +lng ? lat : lng,
        lng: +lat > +lng ? lat : lng,
      };
      assign(imaotai.user, t);
    } else {
      await prompt([
        {
          type: 'input',
          name: 'province',
          message: '请输入预约的省份（如广东省）',
          initial: imaotai.user.province,
          validate: async province => {
            imaotai.user.province = province.trim();
            return /省|市$/.test(province.trim()) || '输入格式不正确';
          },
        },
        {
          type: 'input',
          name: 'city',
          message: '请输入预约的城市（如广州市）',
          initial: imaotai.user.city,
          validate: async city => {
            imaotai.user.city = city.trim();
            return /市$/.test(city.trim()) || '输入格式不正确';
          },
        },
        {
          type: 'input',
          name: 'location',
          message: '请输入预约位置经纬度，逗号分割',
          validate: async location => {
            if (!/\d+.\d+,\d+.\d+/.test(location.trim())) return '输入格式不正确';
            const [lng, lat] = location.split(',');
            imaotai.user.lat = +lat < +lng ? lat : lng;
            imaotai.user.lng = +lat > +lng ? lat : lng;

            return true;
          },
        },
      ]);
    }
  }

  const r = await imaotai.getPhoneCode(mobile);
  if (r.code != 2000) {
    console.error('发送验证码错误', r);
    return;
  }

  await prompt<typeof inputData>([
    {
      type: 'input',
      name: 'vcode',
      message: '请输入接收到的验证码',
      validate: async vcode => {
        if (!/\d+/.test(vcode)) return false;
        const data = await imaotai.login(mobile, vcode);
        if (data?.token) {
          inputData.vcode = vcode;
          imaotai.user.token = data.token;
          imaotai.user.tokenWap = data.cookie || '';
        }
        return Boolean(data?.token);
      },
    },
  ]);

  if (!existUser) config.user.push(imaotai.user);

  for (const key in imaotai.user) if (!imaotai.user[key as never]) delete imaotai.user[key as never];
  configStor.save(config);

  console.log(`获取到token信息：`, imaotai.user.token);
  // @ts-ignore
  console.log('请在配置文件中补充完善配置：', configStor.options.filepath, '\n', JSON.stringify(imaotai.user, null, 2));
}

async function shopLotteryStats(shop: IShopInfo, { itemCode = '10213', sessionId = 0, days = 30, tryUpdateFailed = false }) {
  if (!sessionId) {
    await imaotai.getSessionId();
    sessionId = cacheInfo.info.sessionInfo.sessionId;
  }
  if (!cacheInfo.lottery[shop.shopId]) cacheInfo.lottery[shop.shopId] = {};

  const req = new Request();
  const sessionList = new Array(days)
    .fill(+sessionId)
    .map((v, idx) => v - idx)
    .filter(v => v > 100);

  let failedCount = 0;
  for (let sId of sessionList) {
    if (!cacheInfo.lottery[shop.shopId][sId]) cacheInfo.lottery[shop.shopId][sId] = {};

    const item = cacheInfo.lottery[shop.shopId][sId][itemCode];
    if (item && (!tryUpdateFailed || item.hitCnt)) continue;
    // 连续失败次数大于 5，则不再继续获取
    if (failedCount >= 3) {
      cacheInfo.lottery[shop.shopId][sId][itemCode] = {} as never;
      continue;
    }

    const url = `https://static.moutai519.com.cn/mt-backend/mt/lottery/${sId}/${itemCode}/${shop.shopId}/page1.json?csrf_token`;
    const { data } = await req.get<{ code: string; data: ILottery }>(url);
    console.log(`[get][${data.data?.lotteryDate ? green('ok') : red('failed')}]`, cyan(url));
    if (data.data?.lotteryDate) {
      const info = (cacheInfo.lottery[shop.shopId][sId][itemCode] = data.data);
      info.rate = Math.floor((info.hitCnt / info.reservationCnt) * 100000) / 1000;
      info.rateAll = Math.floor((info.allItemDetail.hitCnt / info.allItemDetail.reservationCnt) * 100000) / 1000;
      failedCount = 0;
    } else {
      if (imaotai.debug && (typeof data !== 'string' || String(data).includes('xml '))) console.log(red(' > 获取失败：'), data);
      cacheInfo.lottery[shop.shopId][sId][itemCode] = {} as never;
      failedCount++;
    }
  }
  cacheStor.save(cacheInfo);

  const list = sessionList.map(sId => cacheInfo.lottery[shop.shopId][sId][itemCode]).filter(d => d?.hitCnt);
  const rankingInfo = list
    .sort((a, b) => b.rate - a.rate)
    .map((v, idx) => `${idx}. 【${dateFormat('yyyy-MM-dd', v?.lotteryDate)}】 中签率：${v.rate}%(${v.hitCnt}/${v.reservationCnt})`);
  const result = { hitCntTotal: 0, reservationCntTotal: 0, rate: 0, rankingInfo, itemCode, shop };

  list.forEach(item => {
    result.hitCntTotal += item.hitCnt;
    result.reservationCntTotal += item.reservationCnt;
  });
  result.rate = Math.floor((result.hitCntTotal / result.reservationCntTotal) * 100000) / 1000;

  if (imaotai.debug && result.hitCntTotal) {
    console.log(
      `[${green(itemMap[itemCode])}][${cyan(shop.name)}]店铺近${cyan(days)}日平均中签率：${green(result.rate)}% (${result.hitCntTotal} / ${
        result.reservationCntTotal
      })。中签率排名：\n`,
      result.rankingInfo.join('\n')
    );
  }

  return result;
}

program
  .option('-l,--login', '是否位 login 模式，登录模式会写入到配置文件中供预约使用。默认为预约模式')
  .option('-f, --force', '强制模式')
  .option('-s, --stat [city]', '统计指定城市中签率')
  .option('-d, --debug', '调试模式')
  .action(async (opts: { login: boolean; force?: boolean; debug: boolean; stat?: string }) => {
    // await configStor.reload();
    await sleep(50);
    assign(config, configStor.get());
    assign(cacheInfo, cacheStor.get());
    if (opts.debug) imaotai.debug = opts.debug;

    // 支持按 deviceId 从环境变量读取已配置的值
    if (process.env.QL_IMAOTAI) {
      const list = process.env.QL_IMAOTAI.split(process.env.QL_IMAOTAI.includes('&') ? '&' : '\n');
      list.forEach(line => {
        const item: Partial<typeof config['user'][0]> = {};
        line.split(';').map(item => item.split('=').map(d=>d.trim())).forEach(([key, value]) => {
          if (!key || !value) return;
          // @ts-ignore
          item[key] = value;
        });

        if (item.deviceId && item.token) {
          const o = config.user.find(d => d.deviceId === item.deviceId);
          if (o) Object.assign(o, item);
          else if (item.city && item.province) {
            // todo: 支持环境变量新增配置，支持配置城市和省份等信息
            config.user.push(item as never);
          }
        }
      });
    }

    if (opts.stat) {
      imaotai.debug = true;
      await imaotai.cityLotteyStat(typeof opts.stat === 'string' ? opts.stat : '广州市');
    } else {
      await imaotai.getAppVersion(false);
      opts.login ? promptLogin(opts) : imaotai.start();
    }
  })
  .parse();

type ILottery = {
  rate: number;
  rateAll: number;
  actualInvCnt: number;
  hitCnt: number;
  lotteryDate: string;
  reservationCnt: number;
  allItemDetail: { actualInvCnt: number; hitCnt: number; hitDisCnt: number; reservationCnt: number; reservationDisCnt: number };
};
type IShopInfo = {
  lat: number;
  lng: number;
  city: number;
  cityName: string;
  province: number;
  fullAddress: string;
  layaway: boolean;
  provinceName: string;
  name: string;
  shopId: string;
};
type MallShopItem = { count: number; itemId: string; ownerName: string; maxReserveCount: number; inventory: number };
type Res<T = any> = {
  code: number;
  message?: string;
  data: T;
  error?: string;
};
