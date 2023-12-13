/*
 * @Author: renxia
 * @Date: 2023-11-28 11:09:04
 * @LastEditors: renxia
 * @LastEditTime: 2023-12-13 09:49:20
 * @Description:
 */
import { LiteStorage, Request } from '@lzwme/fe-utils';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { resolve, sep } from 'node:path';

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

export function getLiteStorage<T extends object = Record<string, any>>(uuid: string, filepath = process.env.LZWME_QL_CONFIG_FILE) {
  if (!uuid) throw Error('请指定 uuid');

  if (!filepath) {
    filepath = findFile('lzwme_ql_config.json') || 'lzwme_ql_config.json';
  }

  return new LiteStorage<T>({ filepath: resolve(process.cwd(), filepath), uuid });
}

export async function sendNotify(text: string, body: string, params: Record<string, any> = {}, author = '\n本通知 By：lzwme/ql-scripts', isPrint = true) {
  const notifyFilePath = findFile('sendNotify.js');
  if (notifyFilePath) {
    await require(notifyFilePath).sendNotify(text, body, params, author);
  }

  if (!notifyFilePath || isPrint) console.log(`[notify][${text}]\n`, body);
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
