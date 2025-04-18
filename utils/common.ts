/*
 * @Author: renxia
 * @Date: 2023-11-28 11:09:04
 * @LastEditors: renxia
 * @LastEditTime: 2025-04-17 17:08:33
 * @Description:
 */

import { LiteStorage, Request, color, NLogger } from '@lzwme/fe-utils';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { resolve, sep } from 'node:path';

export const logger = new NLogger('[ql-scripts]');

export function findFile(filename: string, dirs = [process.cwd(), __dirname]) {
  const dirList = new Set([...dirs, process.cwd(), __dirname, homedir()]);

  for (let dir of dirList) {
    while (dir.length > 3 && dir.includes(sep)) {
      const fullpath = resolve(dir, filename);
      if (existsSync(fullpath)) return fullpath;
      dir = dir.substring(0, dir.lastIndexOf(sep));
    }
  }

  return '';
}

/** 获取本地持久缓存对象 */
export function getCacheStorage<T extends object = Record<string, any>>(uuid: string) {
  return getConfigStorage<T>(uuid, resolve(process.cwd(), 'cache/lzwme_ql_cache.json'));
}

/** 获取配置持久化对象 */
export function getConfigStorage<T extends object = Record<string, any>>(uuid: string, filepath = process.env.LZWME_QL_CONFIG_FILE) {
  if (!uuid) throw Error('请指定 uuid');

  if (!filepath) {
    filepath = findFile('lzwme_ql_config.json5') || findFile('lzwme_ql_config.json') || 'lzwme_ql_config.json';
  }

  // if (!existsSync(filepath) && !filepath.includes('cache.json')) console.warn(`未发现配置文件。请创建：${color.cyan(filepath)}`);

  return new LiteStorage<T>({ filepath: resolve(process.cwd(), filepath), uuid });
}

interface SendNotifyParams extends Record<string, any> {
  hasError?: boolean | number;
  notifyType?: 0 | 1 | 2;
  isPrint?: boolean;
  exit?: boolean;
}

export async function sendNotify(title: string, body: string, params: SendNotifyParams = {}, author = '\n本通知 By：lzwme/ql-scripts') {
  const notifyFilePath = findFile('sendNotify.js');
  const { hasError, notifyType = Number(process.env.LZWME_QL_NOTIFY_TYPE) || 1, isPrint, exit = true } = params;
  let needNotify = true;

  if (notifyType === 0) needNotify = false; // 0 - 禁用通知
  else if (notifyType === 1) {
    // 1 - 有异常才通知
    needNotify = hasError === true;
  } else if (notifyType === 2) {
    // 2 - 全通知
    needNotify = true;
  } else needNotify = process.env.LZWME_QL_NOTIFY !== 'false';

  if (isPrint !== false && (isPrint || !notifyFilePath || !needNotify)) console.log(`[needNotify=${needNotify}][${title}]\n${body}`);

  if (!notifyFilePath) {
    console.warn('未发现 sendNotify.js 文件！');
  } else if (needNotify) {
    await require(notifyFilePath).sendNotify(title, body, params, author);
  }

  exit && process.exit(hasError ? 1 : 0);
}

/** 根据指定的位置返回附近位置及经纬度列表 */
export async function getGeoByGD(address: string, AMAP_KEY: string) {
  const req = new Request();
  const { data } = await req.get<{
    status: string;
    geocodes: {
      province: string;
      city: string;
      formatted_address: string;
      location: string;
    }[];
  }>(`https://restapi.amap.com/v3/geocode/geo?key=${AMAP_KEY}&output=json&address=${address.trim()}`);

  return data.geocodes;
}

export async function getLocationByIp(ip = '') {
  const url = `https://searchplugin.csdn.net/api/v1/ip/get?ip=${ip}`;
  const req = new Request();
  const { data } = await req.get<{ code: number; data: { address: string; ip: string } }>(url);

  if (data.code === 200 && data.data.address) {
    let [_area, province, city] = data.data.address.split(' ');

    if (['北京', '上海', '天津', '重庆'].includes(province)) {
      province += '市';
      city = province;
    } else {
      if (!province.includes('省')) province += '省';
      if (!city.includes('市')) city += '市';
    }

    return { province, city };
  } else {
    console.error('[err][getLocationByIp', ip, data);
  }

  return;
}
