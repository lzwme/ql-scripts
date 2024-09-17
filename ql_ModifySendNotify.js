/*
 * @Author: renxia
 * @Date: 2024-02-19 13:34:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-09-18 08:47:44
 * @Description: 青龙面板sendNotify通知修改拦截。
 * @link https://github.com/lzwme/ql-scripts/blob/main/ql_ModifySendNotify.js
 *
 * 背景：拉取的第三方脚本，执行成功与否都会发大量的广告通知。但我们希望失败时才通知，否则消息轰炸会很烦。
 * 本脚本通过注入的方式修改青龙 sendNotify 函数，可以实现仅允许消息中包含自定义关键字时才发送通知，否则拦截处理。
 * 建议配置到订阅脚本的 "执行后" 内容里： node /ql/data/scripts/lzwme_ql-scripts/ql_ModifySendNotify.js

 cron: 1 18 * * *
 const $ = new Env("青龙sendNotify通知修改拦截");

 环境变量：
  - QL_NOTIFY_ALLOW_WORD 通知中包含指定的关键词则允许发送通知，其它均拦截，多个关键词用逗号分割。默认值参考代码中定义
  - QL_NOTIFY_BAN_WORD 通知中包含指定的关键字则禁止发送通知。
  - QL_NOTIFY_REPO_WORD 允许修改的仓库名称关键字，多个关键词用逗号分割。默认为空，则全部订阅的仓库都处理
  - QL_SCRIPTS_DIR 青龙面板 scripts 目录的路径。默认为 `/ql/data/scripts`
  - SKIP_PUSH_TITLE 青龙面板 sendNotify 自带支持的环境变量，支持配置脚本通知名称，多个使用换行分割
 */

const { resolve } = require('path');

async function modifySendNotify() {
  const allowWordsString =
    process.env.QL_NOTIFY_ALLOW_WORD ||
    '登录失败,签到失败,异常,未登录,❌,已失效,无效,重新登录,未找到,水果奖励,京东资产统计,[60s],[🔔]';
  const ignoreWordsString = process.env.QL_NOTIFY_BAN_WORD || '';

  const allowWords = allowWordsString
    .split(',')
    .map(d => d.trim())
    .filter(Boolean);
  const banWords = ignoreWordsString
    .split(',')
    .map(d => d.trim())
    .filter(Boolean);
  const allowRepoWords = (process.env.QL_NOTIFY_REPO_WORD || '')
    .split(',')
    .map(d => d.trim())
    .filter(Boolean);

  if (allowWords.length === 0) return;

  const fs = require('fs');
  const scriptsDir = process.env.QL_SCRIPTS_DIR || '/ql/data/scripts';

  if (!fs.existsSync(scriptsDir)) {
    console.log(`cwd: ${process.cwd()} \nscriptsDir: ${scriptsDir}`);
    return console.error('青龙脚本目录不存在！请配置环境变量 QL_SCRIPTS_DIR 指定正确的位置');
  }

  const notifyFiles = {
    'sendNotify.js': [],
    'notify.py': [],
  };
  const allowModifyFiles = new Set();
  const findNotifyFiles = dir => {
    fs.readdirSync(dir).forEach(filename => {
      const filepath = resolve(dir, filename);

      if (fs.statSync(filepath).isDirectory()) findNotifyFiles(filepath);
      else if (filename in notifyFiles) {
        notifyFiles[filename].push(filepath);

        if (allowRepoWords.length === 0 || allowRepoWords.some(d => dir.includes(d))) {
          allowModifyFiles.add(filepath);
        }
      }
    });
  };
  let insertStr = [
    `var allowWords = ${JSON.stringify(allowWords)};`,
    `if (!allowWords.some(k => String(desp).includes(k) || String(text).includes(k))) return console.log('已忽略消息推送[ALLOW_WORDS]');`,
    `var banWords = ${JSON.stringify(banWords)};`,
    `if (banWords.some(k => String(desp).includes(k) || String(text).includes(k))) return console.log('消息推送已忽略');`,
  ].join('\n');

  findNotifyFiles(scriptsDir);

  for (const filepath of notifyFiles['sendNotify.js']) {
    let content = fs.readFileSync(filepath, 'utf8');

    if (!allowModifyFiles.has(filepath)) {
      const newContent = removeInsertCode(content, 'js');
      if (content !== newContent) {
        fs.writeFileSync(filepath, newContent, 'utf8');
        console.log(`[js]不在允许修改列表中，移除修改内容`, filepath);
      }

      return;
    }

    if (content.includes('function sendNotify') && content.includes('desp += author;')) {
      if (content.includes(insertStr)) {
        console.log('[js]已存在插入内容：', filepath);
      } else {
        content = removeInsertCode(content, 'js').replace(/(desp \+= author.+)/, `$1\n${insertStr}`);

        fs.writeFileSync(filepath, content, 'utf8');
        console.log('[js]文件修改成功:', filepath);
      }
    }
  }

  insertStr = [
    `    allow_words = ${JSON.stringify(allowWords)}`,
    `    if not any(k in str(content) for k in allow_words):`,
    `        print("已忽略消息推送[ALLOW_WORDS]")`,
    `        return`,
    `    ban_words = ${JSON.stringify(banWords)}`,
    `    if any(k in str(content) for k in ban_words):`,
    `        print("消息推送已忽略")`,
    `        return`,
  ].join('\n');

  for (const filepath of notifyFiles['notify.py']) {
    let content = fs.readFileSync(filepath, 'utf8');

    if (!allowModifyFiles.has(filepath)) {
      const newContent = removeInsertCode(content, 'py');
      if (content !== newContent) {
        fs.writeFileSync(filepath, newContent, 'utf8');
        console.log(`[py]不在允许修改列表中，移除修改内容`, filepath);
      }

      return;
    }

    if (content.includes('def send(title') && content.includes('if not content:')) {
      if (content.includes(insertStr)) {
        console.log('[py]已存在插入内容：', filepath);
      } else {
        content = removeInsertCode(content, 'py').replace(/( +if not content:.*)/, `${insertStr}\n\n$1`);

        fs.writeFileSync(filepath, content, 'utf8');
        console.log('[py]文件修改成功:', filepath);
      }
    }
  }
}

function removeInsertCode(content, type = 'js') {
  if (type === 'js') {
    return content.replaceAll(/var allowWords = (.+\r?\n)+.+消息推送已忽略'\);\r?\n/g, '');
  }
  return content.replaceAll(/ +allow_words = (.+\r?\n.+)+消息推送已忽略"\)(\r?\n\ +return)?(\r?\n)+/g, '\n');
}

// process.env.QL_SCRIPTS_DIR = 'tmp';
modifySendNotify();
