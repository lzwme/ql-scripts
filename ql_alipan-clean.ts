/*
 new Env("小雅挂载阿里云资源盘清理")
 cron: 20 22 1 1 1

 process.env.ALIPAN_CLEAN = 'host=http://192.168.1.10:5678;password=3aVyo8YnaXJ2XJjoTjxxxxxxxxxx';
 设置环境变量 ALIPAN_CLEAN，格式为：
      username=[admin];password=xxx;token=认证token;dir=xxx;host=xxx;limit=50
 参数说明：
  username 默认为 admin
  password 管理员密码。可执行该命令获取： ./alist admin
  token 登录认证 token，与 passord 设置其一即可
  host 为小雅访问地址，默认值为： http://127.0.0.1:5678
  dir 为小雅挂载阿里云盘缓存目录的路径，默认为： /📀我的阿里云盘/资源盘/小雅转存
 */

import { cookieParse, Request } from '@lzwme/fe-utils';

interface XiaoYaResponse<T = any> {
  code: number;
  message: string;
  data?: T;
}
type FsItem = { name: string; modified: string | number; size: number; is_dir: string };

const config = {
  host: 'http://127.0.0.1:5678',
  dir: '/📀我的阿里云盘/资源盘/小雅转存',
  username: 'admin',
  password: '', // 获取方法： ./alist admin
  token: '',
  limit: 10,
};
const req = new Request('', { 'content-type': 'application/json' });

/** 小雅挂载的阿里云盘指定目录内容删除 */
async function alipanDirClean() {
  if (process.env.ALIPAN_CLEAN) Object.assign(config, cookieParse(process.env.ALIPAN_CLEAN));
  else
    return console.log(
      '未设置环境变量 ALIPAN_CLEAN 配置。格式参考：username=admin;password=xxx;dir=xxx;host=http://127.0.0.1:5678;limit=50'
    );
  if (!config.dir) return console.log('未设置阿里云盘缓存目录在小雅的挂载路径 dir 参数');

  const getAuthUrl = `${config.host}/api/auth/login`;
  const fsListUrl = `${config.host}/api/fs/list`;
  const fsRemoveUrl = `${config.host}/api/fs/remove`;

  const { username, password } = config;
  if (username && password) {
    const { data: auth } = await req.post<XiaoYaResponse<{ token: string }>>(getAuthUrl, { username, password });
    config.token = auth.data?.token || '';

    if (!config.token) throw new Error('Failed to authenticate');

    req.setHeaders({ Authorization: config.token });
  } else if (!config.token) {
    return console.log('请设置小雅登录的 username 和 password，或 token 参数');
  }

  const listParams = {
    path: config.dir,
    password: '',
    page: 1,
    per_page: 0,
    refresh: false,
  };
  const { data: listJson } = await req.post<XiaoYaResponse<{ content: Array<FsItem> }>>(fsListUrl, listParams);
  const contentList = listJson.data?.content || [];
  console.log(`当前[${config.dir}]中共有资源数量：`, contentList.length);

  if (contentList.length > config.limit) {
    const names = contentList
      .sort((a, b) => {
        if (typeof a.modified === 'string') a.modified = new Date(a.modified).getTime();
        if (typeof b.modified === 'string') b.modified = new Date(b.modified).getTime();
        return b.modified - a.modified;
      })
      .slice(config.limit)
      .map((d) => d.name);

    const { data: removeJson } = await req.post<XiaoYaResponse>(fsRemoveUrl, { dir: config.dir, names });
    if (removeJson.code === 200) console.log(`本次删除了 ${names.length} 个资源。`, removeJson);
    else console.log('删除失败！', names, removeJson);
  }
}

alipanDirClean()
  .then(() => console.log('Process completed'))
  .catch((error) => console.error('Error:', error));
