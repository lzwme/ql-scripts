#!/usr/bin/env node
/**
 * 从脚本头部 `@source:` 链接同步上游内容。
 *
 * 规则：
 *   1. 读取本地脚本，提取 `@source:` 后的链接；
 *   2. 拉取链接内容，去掉其头部的 shebang 与文档字符串起始的 `"""`；
 *   3. 在本地文件中定位 `new Env` 行，保留到其后的第一个空行，其余内容整体替换；
 *   4. 有变动时提交代码。
 *
 * 用法：
 *   node scripts/sync_source.mjs                 # 同步 FILES 列表
 *   node scripts/sync_source.mjs --dry-run       # 只对比，不写文件、不提交
 *   node scripts/sync_source.mjs --no-commit     # 写文件但不提交
 *   node scripts/sync_source.mjs ql_xxx.py       # 只同步指定文件
 */
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import process from 'node:process';

/** 需要同步的脚本文件名列表（相对项目根目录） */
const FILES = [
  'ql_workbuddy_intl_daily.py',
  'ql_workbuddy_daily.py',
  'ql_qoder_daily.py',
  'ql_trace_checkin.py',
];

/** 固定提交信息 */
const COMMIT_MESSAGE = 'chore: 同步上游脚本内容';

const rootDir = process.cwd();
const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const noCommit = argv.includes('--no-commit');
const cliFiles = argv.filter(arg => !arg.startsWith('-'));
const targets = cliFiles.length ? cliFiles : FILES;

const logger = {
  info: msg => console.log(msg),
  warn: msg => console.warn(msg),
  error: msg => console.error(msg),
};

/** 统一换行符并去掉 BOM */
function normalize(text) {
  return text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
}

/** 提取 @source 链接 */
function extractSource(content) {
  return /^\s*@source:\s*(\S+)\s*$/m.exec(content)?.[1];
}

/** 去掉上游内容头部的 shebang 等前置行，以及文档字符串起始的 """ */
function stripUpstreamHeader(text) {
  const lines = text.split('\n');
  const idx = lines.findIndex(line => line.trim() === '"""');
  if (idx === -1) throw new Error('上游内容未找到文档字符串起始的 """');
  return lines.slice(idx + 1).join('\n');
}

/** 保留本地文件到 new Env 行后的空行，其余替换为上游正文 */
function mergeContent(local, body) {
  const lines = local.split('\n');
  const envIdx = lines.findIndex(line => /^\s*new\s+Env\s*\(/.test(line));
  if (envIdx === -1) throw new Error('本地文件未找到 new Env 行');

  let blankIdx = -1;
  for (let i = envIdx + 1; i < lines.length; i++) {
    if (lines[i].trim() === '') {
      blankIdx = i;
      break;
    }
  }
  if (blankIdx === -1) throw new Error('new Env 行后未找到空行');

  return lines.slice(0, blankIdx + 1).join('\n') + '\n' + body;
}

async function fetchText(url) {
  const res = await fetch(url, {
    redirect: 'follow',
    signal: AbortSignal.timeout(60_000),
    headers: { 'user-agent': 'Mozilla/5.0 (compatible; ql-scripts-sync)' },
  });
  if (!res.ok) throw new Error(`请求失败 ${res.status} ${res.statusText}`);

  const text = normalize(await res.text());
  if (!/\b(def|import|class)\b/.test(text)) throw new Error('返回内容不是 Python 脚本，已跳过');
  return text;
}

async function syncFile(filename) {
  const filepath = resolve(rootDir, filename);
  const local = normalize(await readFile(filepath, 'utf8'));
  const source = extractSource(local);
  if (!source) {
    logger.warn(`[跳过] ${filename}: 未找到 @source 链接`);
    return null;
  }

  logger.info(`[同步] ${filename} <- ${source}`);
  const upstream = await fetchText(source);
  const next = mergeContent(local, stripUpstreamHeader(upstream));
  if (next === local) {
    logger.info(`[无变化] ${filename}`);
    return null;
  }

  if (!dryRun) await writeFile(filepath, next, 'utf8');
  logger.info(`[已更新] ${filename}`);
  return filename;
}

function commit(changed) {
  const status = execFileSync('git', ['status', '--porcelain', '--', ...changed], {
    cwd: rootDir,
    encoding: 'utf8',
  }).trim();
  if (!status) {
    logger.info('[提交] 无代码变动，跳过');
    return;
  }

  execFileSync('git', ['add', '--', ...changed], { cwd: rootDir, stdio: 'inherit' });
  execFileSync('git', ['commit', '-m', COMMIT_MESSAGE], { cwd: rootDir, stdio: 'inherit' });
  logger.info(`[提交] ${COMMIT_MESSAGE}`);
}

async function main() {
  const changed = [];
  for (const filename of targets) {
    try {
      const result = await syncFile(filename);
      if (result) changed.push(result);
    } catch (err) {
      logger.error(`[失败] ${filename}: ${err.message}`);
    }
  }

  if (dryRun) {
    logger.info(`[dry-run] 待更新 ${changed.length} 个文件`);
    return;
  }
  if (noCommit || !changed.length) return;
  commit(changed);
}

main().catch(err => {
  logger.error(err.stack || err.message);
  process.exitCode = 1;
});
