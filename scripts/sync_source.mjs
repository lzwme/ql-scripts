#!/usr/bin/env node
/**
 * 按脚本配置同步上游内容。
 *
 * 核心流程固定为：读取本地 -> before -> 请求上游 -> after -> 写回/提交。
 * 每个脚本在 SCRIPTS 中以「脚本路径: 配置」定义，可用可选钩子做自定义处理：
 *   before(ctx) 请求前执行，ctx = { filename, local, source }，可返回 { local, source } 覆盖；
 *   after(ctx)  请求后执行，ctx = { filename, local, upstream, source }，返回最终内容。
 * 未配置 after 时默认整体使用上游内容。
 *
 * 用法：
 *   node scripts/sync_source.mjs                 # 同步 SCRIPTS 中配置的所有脚本
 *   node scripts/sync_source.mjs --dry-run       # 只对比，不写文件、不提交
 *   node scripts/sync_source.mjs --no-commit     # 写文件但不提交
 *   node scripts/sync_source.mjs ql_xxx.py       # 只同步指定脚本
 */
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import process from 'node:process';

const COMMIT_MESSAGE = 'chore: 同步上游脚本内容';

const rootDir = process.cwd();
const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const noCommit = argv.includes('--no-commit');
const cliFiles = argv.filter(arg => !arg.startsWith('-'));

const logger = {
  info: msg => console.log(msg),
  warn: msg => console.warn(msg),
  error: msg => console.error(msg),
};

/** 统一换行符并去掉 BOM */
function normalize(text) {
  return text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
}

/** 提取 @source / @see 链接 */
const SOURCE_PATTERNS = [
  /^\s*@source:?\s+(\S+)\s*$/m,
  /^\s*\*?\s*@see\s+(\S+)\s*$/m,
];
function extractSource(content) {
  for (const pattern of SOURCE_PATTERNS) {
    const match = pattern.exec(content);
    if (match) return match[1];
  }
}

// ── 合并辅助 ──────────────────────────────────────────────

/** 定位首个匹配行，找不到返回 -1 */
const findLine = match => lines => lines.findIndex(match);
/** 定位某匹配行之后的第一个空行 */
const findBlankAfter = match => lines => {
  const from = lines.findIndex(match);
  if (from < 0) return -1;
  for (let i = from + 1; i < lines.length; i++) {
    if (lines[i].trim() === '') return i;
  }
  return -1;
};

/** 本地保留到 localCut 行（含），上游从 upstreamCut 行之后开始 */
function mergeByCut(local, upstream, localCut, upstreamCut) {
  const localLines = local.split('\n');
  const upstreamLines = upstream.split('\n');
  const li = localCut(localLines);
  const ui = upstreamCut(upstreamLines);
  if (li < 0 || ui < 0) throw new Error('未找到同步切分位置');
  return localLines.slice(0, li + 1).join('\n') + '\n' + upstreamLines.slice(ui + 1).join('\n');
}

const isNewEnv = line => /^\s*new\s+Env\s*\(/.test(line);
const isDocStart = line => line.trim() === '"""';

const pythonAfter = ({ local, upstream }) =>
  mergeByCut(local, upstream, findBlankAfter(isNewEnv), findLine(isDocStart));

/** 工具脚本：本地仅在 docstring 注入 @source 行，保留该头部后同步上游正文 */
const isSourceLine = line => /^\s*@source\b/.test(line);
const sourceHeaderAfter = ({ local, upstream }) =>
  mergeByCut(local, upstream, findBlankAfter(isSourceLine), findLine(isDocStart));

/** MiniMax 专有 */
const minimaxAfter = ({ local, upstream }) => {
  const isMarker = line => line.includes('累计签到积分余额变量：');
  return mergeByCut(local, upstream, findLine(isMarker), findLine(isMarker));
};

// ── 脚本同步配置 ──────────────────────────────────────────

/**
 * 键为脚本路径，值为该脚本的同步配置。
 * before/after 均支持异步；before 返回的对象会覆盖 ctx 中的同名值。
 */
const SCRIPTS = {
  'ql_workbuddy_intl_daily.py': { after: pythonAfter },
  'ql_workbuddy_daily.py': { after: pythonAfter },
  'ql_qoder_daily.py': { after: pythonAfter },
  'ql_trace_checkin.py': { after: pythonAfter },
  'ql_minimax_checkin.js': { after: minimaxAfter },
  'scripts/trae_get_token.py': { after: sourceHeaderAfter },
  'scripts/qoder_login.py': { after: sourceHeaderAfter },
};

const targets = cliFiles.length ? cliFiles : Object.keys(SCRIPTS);

// ── 同步流程 ──────────────────────────────────────────────

async function fetchText(url) {
  const res = await fetch(url, {
    redirect: 'follow',
    signal: AbortSignal.timeout(60_000),
    headers: { 'user-agent': 'Mozilla/5.0 (compatible; ql-scripts-sync)' },
  });
  if (!res.ok) throw new Error(`请求失败 ${res.status} ${res.statusText}`);
  const text = normalize(await res.text());
  if (!text.trim()) throw new Error('上游内容为空');
  return text;
}

async function syncFile(filename) {
  const config = SCRIPTS[filename];
  if (!config) {
    logger.warn(`[跳过] ${filename}: 未在 SCRIPTS 中配置`);
    return null;
  }

  const filepath = resolve(rootDir, filename);
  let local = normalize(await readFile(filepath, 'utf8'));
  let source = extractSource(local);

  if (config.before) {
    const overrides = await config.before({ filename, local, source });
    if (overrides?.local !== undefined) local = overrides.local;
    if (overrides?.source !== undefined) source = overrides.source;
  }
  if (!source) {
    logger.warn(`[跳过] ${filename}: 未找到 @source / @see 链接`);
    return null;
  }

  logger.info(`[同步] ${filename} <- ${source}`);
  const upstream = await fetchText(source);
  const next = config.after
    ? await config.after({ filename, local, upstream, source })
    : upstream;

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
