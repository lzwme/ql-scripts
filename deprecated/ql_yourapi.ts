/*
 * @Description: yourapi 签到领额度 - 免费兑换使用Claude等国际顶级大模型 API 调用额度

  yourapi 注册地址：  https://yourapi.cn/register?aff=Cx3T
  wolfai 注册地址： https://wolfai.top/register?aff=XhG6

  参考：提供免费额度大模型 API 的邀请注册（通过邀请方式注册，双方均可多得额度）
  - 硅基流动（送14元赠金）：https://cloud.siliconflow.cn/i/hDM9hDR6
  - 火山方舟（送145元赠金）：https://www.volcengine.com/experience/ark?utm_term=202502dsinvite&ac=DSASUQY5&rc=2D8BETN6
  - 派欧算力云（送50元赠金）：https://ppinfra.com/user/register?invited_by=XRMRL5

 cron: 30 8 * * *

 用法：
  - 环境变量： yourapi_ck
    - 抓包 https://yourapi.cn/api/ 获取请求headers中 cookie 参数中的 session 值，并使用 ## 符号拼接个人 ID，示例：session=xxxxx ## 1234
    - 多账号使用 & 或换行符分割。示例：export yourapi_ck="session=xxxx##2400&session=yyyy##2401"
  - 环境变量： BAIDU_APP_API_KEY 和 BAIDU_APP_SECRET_KEY，用于调用百度 OCR 文本识别验证码
    - baidu 文字识别服务获取地址：https://console.bce.baidu.com/ai-engine/ocr/overview/index
    - 应用列表 - 新建应用，复制 API Key 和 Secret Key
  - 环境变量： DDDOCR_API 和 DDDOCR_KEY，用于调用 dddocr 识别验证码
 */
import { cookieParse, toQueryString } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('yourapi签到领积分');

function validateCaptchaCode(code: string) {
  return typeof code === 'string' && code.length >= 4 && !/^\d{4}/.test(code);
}

/** 使用 dddorc 识别验证码 */
async function dddocrCaptcha(imageb64: string, retry = 2) {
  const result = { data: '', errmsg: '' };

  if (!process.env.DDDOCR_API) {
    result.errmsg = '请设置环境变量 DDDOCR_API 用于调用 dddocr 识别验证码', 'error';
    return result;
  }

  const b = await fetch(process.env.DDDOCR_API, {
    method: 'post',
    body: imageb64.replace(/^data:image\/\w+;base64,/, '').trim(),
    headers: { token: process.env.DDDOCR_KEY || '' },
  }).then(d => d.json());
  if (!b.result) console.log('dddocr result:', b);
  result.data =  b.result || '';

  if (validateCaptchaCode(result.data)) {
    result.data = '';
    result.errmsg = `OCR 识别验证码结果不符合要求：${result.data}`;
    if (retry > 0) {
      $.debug(`${result.errmsg}，重试 ${retry} 次`);
      return dddocrCaptcha(imageb64, retry - 1);
    }
  }

  return result;
}

/** 使用百度云 OCR 识别验证码*/
async function baiduOCR(imageb64: string, retry = 2, access_token?: string) {
  const result = { data: '', errmsg: '' };
  if (!process.env.BAIDU_APP_API_KEY || !process.env.BAIDU_APP_SECRET_KEY) {
    result.errmsg = '请设置环境变量 BAIDU_APP_API_KEY 和 BAIDU_APP_SECRET_KEY 用于调用百度 OCR 识别验证码';
    return result;
  }

  // 1. 获取 access_token
  if (!access_token) {
    const params = {
      grant_type: 'client_credentials',
      client_id: process.env.BAIDU_APP_API_KEY || '',
      client_secret: process.env.BAIDU_APP_SECRET_KEY || '',
    };
    const { data: atdata } = await $.req.post(`https://aip.baidubce.com/oauth/2.0/token?${toQueryString(params)}`, {});
    access_token = atdata.access_token || access_token;
    if (!access_token) {
      result.errmsg = '获取百度 OCR access_token 失败，请检查环境变量 BAIDU_APP_API_KEY 和 BAIDU_APP_SECRET_KEY 是否正确';
      return result;
    }
    $.debug('百度 OCR access_token 获取成功', access_token);
  }

  // 2. 调用 OCR 接口识别验证码
  const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
  const { data: r } = await $.req.post(
    `https://aip.baidubce.com/rest/2.0/ocr/v1/numbers?access_token=${access_token}`,
    { image: imageb64 },
    headers
  );
  $.debug('百度 OCR 识别结果', r);
  result.data = r.words_result?.[0].words || '';

  if (!validateCaptchaCode(result.data)) {
    result.data = '';
    result.errmsg = `OCR 识别验证码结果不符合要求：${result.data}`;
    if (retry > 0) {
      $.debug(`${result.errmsg}，重试 ${retry} 次`);
      return baiduOCR(imageb64, retry - 1, access_token);
    }
  }

  if (!result.data) {
    console.log('百度 OCR 识别验证码失败！', r);
    result.errmsg = `百度 OCR 识别验证码失败！${JSON.stringify(r)}`;
  }

  return result;
}

async function getCaptcha() {
  const result = { image_captcha_id: '', data: '', errmsg: '' };
  // 获取验证码图片
  type TCaptcha = { success: boolean; captcha_id: string; image: string; message: string };
  const { data: captchaData } = await $.req.get<TCaptcha>('https://yourapi.cn/api/captcha/image/base64');
  $.debug('获取验证码结果', captchaData);
  if (!captchaData.success || !captchaData.image) {
    console.log(captchaData);
    result.errmsg = `获取验证码失败：${captchaData.message}`;
    return result;
  }
  result.image_captcha_id = captchaData.captcha_id;

  if (!result.data) Object.assign(result, await dddocrCaptcha(captchaData.image));
  if (!result.data) Object.assign(result, await baiduOCR(captchaData.image));

  return result;
}

export async function signCheckIn(ck: string, _idx?: number, userid?: string) {
  const ckobj = cookieParse(ck);
  const headers = {
    'content-type': 'application/json',
    'new-api-user': userid || ckobj.ID || ckobj.id || '',
    cookie: `session=${ckobj.session || ''}`,
    Referer: 'https://yourapi.cn/personal',
  };

  const captcha = await getCaptcha();
  if (captcha.errmsg || !captcha.data) {
    $.log(captcha.errmsg, 'error');
    return;
  }

  const body = { image_captcha_id: captcha.image_captcha_id, image_captcha_code: captcha.data };
  type TRes = { success: boolean; message: string; data: { consecutive_days: number; quota_reward: number; quota_reward_text: string } };
  const { data } = await $.req.post<TRes>('https://yourapi.cn/api/user/check_in', body, headers);
  $.debug('签到请求结果', body, data);

  if (String(data.message).includes('已经签到')) {
    $.log(data.message);
  } else if (data.success) {
    $.log(`✅签到成功！获取 ${data.data?.quota_reward_text}`);
  } else {
    $.log(`签到失败！${data.message}`, 'error');
    console.log(data);
  }
}

// process.env.QL_LZW_DEBUG = '1'; // 开启调试模式，输出调试信息
// process.env.DDDOCR_KEY = ''
// process.env.DDDOCR_API = ''
// process.env.BAIDU_APP_API_KEY = '';
// process.env.BAIDU_APP_SECRET_KEY = '';
// process.env.yourapi_ck = '';
// getCaptcha().then(d => console.log(d));
if (require.main === module) $.init(signCheckIn, 'yourapi_ck').then(() => $.done());
