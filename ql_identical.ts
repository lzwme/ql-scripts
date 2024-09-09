/**
 new Env("禁用青龙重复脚本")
 cron: 20 20 * * *
 */

import { Request, readJsonFileSync } from '@lzwme/fe-utils';
import { sendNotify } from './utils';
import { existsSync } from 'node:fs';

const req = new Request('', { 'Content-Type': 'application/json' });
let host = 'http://localhost:5700';

function getHost() {
  if (process.env.IPPORT) {
    host = process.env.IPPORT;
    if (!host.startsWith('http')) host = `http://localhost:${host}`;
  } else {
    console.log(
      `如果报错请在环境变量中添加你的真实 IP:端口\n名称：IPPORT\t值：127.0.0.1:5700\n或在 config.sh 中添加 export IPPORT='127.0.0.1:5700'`
    );
  }
}

function getToken() {
  let qlToken = process.env.QL_TOKEN;
  if (!qlToken) {
    let qlAuthFile = '/ql/data/config/auth.json';
    if (!existsSync(qlAuthFile)) qlAuthFile = '/ql/config/auth.json';
    if (existsSync(qlAuthFile)) qlToken = readJsonFileSync<{ token: string }>(qlAuthFile).token;
  }
  req.setHeaders({ Authorization: `Bearer ${qlToken}` });
  return qlToken;
}

async function getTaskList() {
  const { data } = await req.get<{ code: number; data: { data: TaskItem[] } }>(`${host}/api/crons?searchValue=&t=${Date.now()}`);
  return data.data?.data || [];
}

async function disableTask(tasks: TaskItem[]) {
  const ids = tasks.map(d => d.id);
  const { data } = await req.request('PUT', `${host}/api/crons/disable`, ids);
  return data.code === 200 ? '🎉成功禁用重复任务~' : `❌出错!!!错误信息为：${JSON.stringify(data)}`;
}

async function start() {
  const msg: string[] = [];
  const disableTaskList: TaskItem[] = [];

  getHost();
  if (getToken()) {
    const taskMap = new Map<string, TaskItem[]>();
    const tasklist = await getTaskList();
    const disabledList = tasklist.filter(d => d.isDisabled);

    msg.push(`总任务数：${tasklist.length}，已禁用：${disabledList.length}，已开启：${tasklist.length - disabledList.length}\n`);

    for (const item of tasklist) {
      if (!item.command) continue;
      if (!taskMap.has(item.name)) taskMap.set(item.name, []);
      taskMap.get(item.name)!.push(item);
    }

    for (const list of taskMap.values()) {
      if (list.length > 1) {
        // console.log('发现存在重复的任务：\n', list.map(d => `[${d.name}][${d.command.replace('task ', '')}]`).join('\n'));
        const enabledList = list.filter(d => d.isDisabled === 0);

        if (enabledList.length > 1) {
          const sorted = enabledList.sort((a, b) => {
            if (a.command.includes('lzwme')) return -1;
            return b.last_execution_time - a.last_execution_time;
          });

          msg.push(sorted.map((d, i) => `${i ? '【🚫禁用】' : '【✅保留】'}[${d.name}] ${d.command.replace('task ', '')}`).join('\n'), '\n');
          disableTaskList.push(...sorted.slice(1));
        }
      }
    }

    msg.push(disableTaskList.length ? await disableTask(disableTaskList) : '✅没有需要禁用的重复任务');
  } else {
    msg.push(`💔禁用重复任务失败!无法获取 token!`);
  }

  if (disableTaskList.length) await sendNotify('禁用青龙重复脚本', msg.join('\n'));
  else console.log(msg.join('\n'));
}

start();

interface TaskItem {
  id: number;
  name: string;
  command: string;
  schedule: string;
  timestamp: string;
  saved: boolean;
  status: number;
  isSystem: number;
  pid: number;
  isDisabled: number;
  isPinned: number;
  log_path: string;
  labels: any[];
  last_running_time: number;
  last_execution_time: number;
  sub_id: number;
  extra_schedules?: string;
  task_before?: string;
  task_after?: string;
  createdAt: string;
  updatedAt: string;
  _disable: boolean;
}
