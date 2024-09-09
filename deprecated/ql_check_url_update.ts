/*
 * @Author: renxia
 * @Date: 2024-02-22 17:05:00
 * @LastEditors: renxia
 * @LastEditTime: 2024-03-25 13:48:52
 * @Description: 脚本内容变更检测。根据指定的脚本 URL 或本地访问路径获取脚本内容，并与缓存 hash 比对

 new Env('脚本内容变更检测')
 cron: 50 8 * * *
 环节变量： CHECK_URLS ，指定要检查的 URL 或文件路径，多个以换行或 $$ 分割
 */
import { existsSync, readFileSync } from 'node:fs';
import { dateFormat, md5 } from '@lzwme/fe-utils';
import { Env, getConfigStorage } from './utils';

const $ = new Env('脚本内容变更检测', { sep: ['\n', '$$'] });
const cacheStor = getConfigStorage<Record<string, { t: number; hash: string }>>('urlCheck', 'cache/lzwme_check_url_cache.json');

export async function urlCheck(url: string) {
  if (!url || url.startsWith('#') || url.startsWith('//')) return $.log(`忽略注释: ${url}`);

  let content = '';
  $.req.setHeaders({ 'content-type': 'text/plain' });
  if (url.startsWith('http')) content = await $.req.get<string>(url).then(d => d.data);
  else if (existsSync(url)) content = readFileSync(url, 'utf-8');
  else return $.log(`文件不存在：${url}`, 'error');

  const hash = md5(content);
  const cacheHash = cacheStor.getItem(url);
  if (cacheHash?.hash !== hash) {
    if (cacheHash) $.log(`🔔 内容已变更: ${url} [上次变更：${dateFormat('yyyy-MM-dd hh:mm:ss', cacheHash.t)}]`, 'error');
    else $.log(`➡ 首次检查，存入缓存：${url}`);
    cacheStor.setItem(url, { t: Date.now(), hash });
  } else console.log(`✅ 内容未变更: ${url}`);
}

(async function start() {
  let val = process.env.CHECK_URLS;
  if (val) {
    if (existsSync(val)) val = readFileSync(val, 'utf-8');
    const urls = val.split('\n').filter(d => d && !d.startsWith('#') && !d.startsWith('//'));
    $.log(`开始检查，共 ${urls.length} 个URL`);
    for (const url of urls) await urlCheck(url.trim()).catch(e => $.log(`处理失败: ${url}\n${(e as Error).message}`, 'error'));
  } else $.log('未指定要检查的URL列表。请配置环境变量 CHECK_URLS');
  $.done();
})();
