/*
 * @Author: renxia
 * @Date: 2024-04-03 19:33:28
 * @LastEditors: renxia
 * @LastEditTime: 2024-04-03 19:49:49
 * @Description:
 *
 * new Env('whistle.x-scripts 插件安装与更新')
 * cron: 0 18 * * *
 */
import fs from 'node:fs';
import { dirname, resolve } from 'node:path';
import { execPromisfy, rmrf } from '@lzwme/fe-utils';

console.log(process.cwd());

const baseDir = process.env.QL_WHISTLE_BASEDIR || '/ql/data/scripts/whistle/';

const repoList = ['whistle.x-scripts', 'x-scripts-rules'];

async function updateRepo(repoName: string) {
  const dir = resolve(baseDir, repoName);

  if (fs.existsSync(dir)) {
    const r = await execPromisfy(`git fetch --all && git reset --hard remotes/origin/main`, true, { cwd: dir });
    if (r.stderr) {
      rmrf(dir);
      return updateRepo(repoName);
    }
  } else {
    await execPromisfy(`git clone https://mirror.ghproxy.com/github.com/lzwme/${repoName}.git`, true, { cwd: dirname(dir) });
  }

  if (repoName === 'whistle.x-scripts') {
    await execPromisfy('pnpm install && pnpm build', true, { cwd: dir });
  }
}

async function start() {
  const r = await execPromisfy('w2 stop', true, { cwd: baseDir });
  if (r.stderr) await execPromisfy('npm i -g whistle', true, { cwd: baseDir });
  for (const repoName of repoList) await updateRepo(repoName);

  await execPromisfy('w2 start', true, { cwd: baseDir });
  process.exit();
}

start().catch((e) => {
  console.error(e);
  process.exit();
});
