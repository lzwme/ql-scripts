/*
 * @Author: renxia
 * @Date: 2024-02-20 10:31:21
 * @LastEditors: renxia
 * @LastEditTime: 2025-07-24 16:19:17
 * @Description:
 */
import { type AnyObject, Request, color } from '@lzwme/fe-utils';
import { getCacheStorage, sendNotify } from './common';

process.env.NODE_USE_ENV_PROXY = '1' // 允许解析 HTTP_PROXY 代理
const { redBright, strip } = color;

interface EnvOptions {
  /** 多账号分隔符。默认为 &、\n */
  sep?: string[];
  /** 是否开启消息通知。默认为 true */
  notifyFlag?: boolean;
}

export class Env {
  public index = 0;
  private startTime = Date.now();
  private msgs: string[] = [];
  private options: EnvOptions = {
    sep: ['&', '\n'],
  };
  public hasError: boolean | number = 0;
  public req = new Request(undefined, { 'content-type': 'application/json' });
  public storage: ReturnType<typeof getCacheStorage<AnyObject>>;
  public color = color;
  constructor(public name: string, options?: EnvOptions) {
    this.log(`[${this.name}]开始运行\n`, 'debug');
    this.storage = getCacheStorage(name);
    if (options) Object.assign(this.options, options);
  }
  public async init(Task?: any, envName?: string, envValue?: string) {
    await this.storage.ready();

    if (Task) {
      if (!envValue && envName) envName.split('|').some((eName) => (envValue = process.env[eName]));
      if (envValue) {
        const users = this.parse(envValue, this.options.sep);
        await this.runTask(Task, users);
      } else {
        this.log(`环境变量 ${redBright(envName)} 未定义`, 'error');
      }
    }
    return this;
  }
  public async runTask(Task: any, usersConfig: any[]) {
    try {
      for (let [idx, userConfig] of Object.entries(usersConfig)) {
        try {
          this.index = +idx + 1;
          let desc = '';
          if (typeof userConfig === 'string') [userConfig, desc = ''] = userConfig.split('##').map(d =>d.trim()); // 支持以 ## 隔离描述，可主要用于唯一 uid 标记
          this.log(`🆔账号${this.index}：${desc || ''}`);
          if (typeof Task.prototype?.start === 'function') {
            const t = new Task(userConfig, this.index, desc);
            await t.start();
          } else await Task(userConfig, this.index, desc);
        } catch (error) {
          console.error(error);
          this.log(`❌账号 ${this.index} 运行异常：${(error as Error).message}`, 'error');
        }
      }
    } catch (e) {
      const error = e as Error;
      console.error(error);
      this.log(`❌运行异常：${error.message}`, 'error');
    }
    this.done();
  }
  public parse(envValue: string, mutiAccountSeps = this.options.sep!) {
    if (!envValue) return [];

    const sep = mutiAccountSeps.find((d) => envValue.includes(d)) || mutiAccountSeps[0];
    const arr = envValue.split(sep).filter(Boolean);
    if (arr.length > 1) this.log(`共找到了 ${arr.length} 个账号`);
    return arr;
  }
  public debug(...msg: any[]) {
    if (process.env.QL_LZW_DEBUG == '1') console.debug('[debug]', ...msg);
  }
  public log(msg: string, type: 'error' | 'info' | 'warn' | 'log' | 'debug' | 'D' = 'info') {
    if (type === 'D') type = 'debug';
    if (type === 'error') {
      this.hasError = true;
      if (!msg.startsWith('❌') && !/^[\ud800-\udbff][\udc00-\udfff]/.test(msg)) msg = `❌ ${msg}`;
    }
    if (type !== 'debug') this.msgs.push(strip(msg));
    console[type](msg);
  }
  uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
  }
  wait(delay: number, gap = 0, showTip = true) {
    if (gap > 0) delay += Math.floor(Math.random() * gap);
    if (showTip) this.log(`等待 ${delay}ms 后继续...`, 'debug');
    return new Promise((rs) => setTimeout(rs, delay));
  }
  public getMsgs() {
    return this.msgs.join('\n');
  }
  private end = false;
  public async done() {
    if (this.end) return;
    this.end = true;
    if (this.options.notifyFlag !== false && this.msgs.length) {
      await sendNotify(this.name, this.getMsgs(), { hasError: this.hasError, isPrint: false, exit: false });
    }
    this.log(`运行结束，共运行了 ${Math.ceil((Date.now() - this.startTime) / 1000)} 秒`);
    process.exit(this.hasError ? 1 : 0);
  }
}
