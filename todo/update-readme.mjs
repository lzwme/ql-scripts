/*
 * @Author: renxia
 * @Date: 2024-05-21 10:20:11
 * @LastEditors: renxia
 * @LastEditTime: 2025-01-09 10:22:26
 * @Description:
 */
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { getLogger } from '@lzwme/fe-utils';

const logger = new getLogger('[QL-SCRIPTS]');
const rootDir = process.cwd();


function getScriptsList() {
  const list = readdirSync(rootDir).filter(d => /^ql_.+\.(ts|js)$/.test(d));
  const mdContent = list.map(filename => {
    const content = readFileSync(resolve(rootDir, filename), 'utf8');
    const title = /Env\(["' ]+([^'"]+)["' ]+\)/.exec(content)?.[1].trim() || '';

    return `- [${title}](./${filename})`;
    // return `- [${title}](https://ghpr.cc/github.com/lzwme/ql-scripts/raw/main/${filename})`;
  }).join('\n');

  return { list, mdContent };
}

function updateReadme() {
  const rdFile = resolve(rootDir, 'README.md');
  const { list, mdContent } = getScriptsList();
  const content = readFileSync(rdFile, 'utf8');
  const noticeStr = `> 注意：本仓库脚本不支持单独订阅。可订阅仓库并禁用不需要的脚本。\n\n`;
  const updated = content.replace(/## 脚本列表\([\s\S]+\n## /g, `## 脚本列表(${list.length})：\n${noticeStr}${mdContent}\n\n## `);

  if (updated !== content) {
    writeFileSync(rdFile, updated, 'utf8');
    logger.info('已更新', list.length);
  } else logger.info('[UPDATE-READE] No Chagned');
  return list.length;
}

function start() {
    updateReadme();
}

start();
