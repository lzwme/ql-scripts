import { type AnyObject, Request, generateUuid } from '@lzwme/fe-utils';
import { getCacheStorage, sendNotify } from './common';

interface EnvOptions {
  /** 多账号分隔符。默认为 &、\n */
  sep?: string[];
  /** 是否开启消息通知。默认为 true */
  notifyFlag?: boolean;
}

export class Env {
  private startTime = Date.now();
  private msgs: string[] = [];
  private options: EnvOptions = {
    sep: ['&', '\n'],
  };
  public hasError = false;
  public req = new Request(undefined, { 'content-type': 'application/json' });
  public storage: ReturnType<typeof getCacheStorage<AnyObject>>;
  constructor(public name: string, options?: AnyObject) {
    this.log(`[${this.name}]开始运行\n`, 'debug');
    this.storage = getCacheStorage(name);
    if (options) Object.assign(this.options, options);
  }
  public async init(Task?: any, envName?: string, envValue?: string) {
    await this.storage.ready();

    if (Task) {
      if (!envValue && envName) envValue = process.env[envName];
      if (envValue) {
        const users = this.parse(envValue, this.options.sep);
        await this.runTask(Task, users);
      } else {
        this.log(`环境变量 ${envName} 未定义`, 'error');
      }
    }
    return this;
  }
  public async runTask(Task: any, usersConfig: any[]) {
    try {
      for (const [idx, userConfig] of Object.entries(usersConfig)) {
        this.log(`账号${ +idx + 1 }：`);
        if (typeof Task.prototype?.start === 'function') {
          const t = new Task(userConfig);
          await t.start();
        } else await Task(userConfig);
      }
    } catch (e) {
      const error = e as Error;
      this.log(`运行异常：${error.message}`, 'error');
    }
    this.done();
  }
  public parse(envValue: string, mutiAccountSeps = this.options.sep!) {
    if (!envValue) return [];

    const sep = mutiAccountSeps.find(d => envValue.includes(d)) || mutiAccountSeps[0];
    const arr = envValue.split(sep).filter(Boolean);
    if (arr.length > 1) this.log(`共找到了 ${arr.length} 个账号`);
    return arr;
  }
  public log(msg: string, type: 'error' | 'info' | 'warn' | 'log' | 'debug' = 'info') {
    if (type !== 'debug') this.msgs.push(msg);
    if (type === 'error') this.hasError = true;
    console[type](msg);
  }
  uuid() {
    return generateUuid();
  }
  wait(delay: number, gap = 0) {
    if (gap > 0) delay += Math.floor(Math.random() * gap);
    return new Promise(rs => setTimeout(rs, delay));
  }
  public async done() {
    if (this.options.notifyFlag !== false && this.msgs.length) {
      await sendNotify(this.name, this.msgs.join('\n'), { hasError: this.hasError, isPrint: false, exit: false });
    }
    this.log(`运行结束，共运行了${Math.ceil((Date.now() - this.startTime) / 1000)}秒`);
    process.exit(this.hasError ? 1 : 0);
  }
}
