/*
 * @Author: renxia
 * @Date: 2024-02-19 13:34:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-02-19 18:32:11
 * @Description: 书亦烧仙草小程序签到

 cron: 11 10 * * *
 const $ = new Env("书亦烧仙草签到");
 环境变量 sysxc，抓包获取 header 中的 auth，多个账户以 & 或 \n 换行分割
 */
import CryptoJS from 'crypto-js';
import axios from 'axios';
import { sendNotify } from './utils';
type AnyObject = { [key: string]: any };

const req = {
  async get(url: string, headers: AnyObject) {
    try {
      return axios.get(url, { headers }).then(d => d.data);
    } catch (err) {
      console.log(`error:${(err as Error).message}`);
    }
  },
  async post(url: string, data: AnyObject | string, headers: AnyObject) {
    try {
      return axios.post(url, data, { headers }).then(d => d.data);
    } catch (err) {
      console.log(`error:${(err as Error).message}`);
    }
  },
};

async function slider_match(img1: string, img2: string, type = 'api') {
  const ocrApi = process.env.LZWME_OCR_API;

  if (ocrApi && type === 'api') {
    const b = await fetch(ocrApi, {
      method: 'post',
      headers: { 'Content-Type': 'application/json', origin: '*', token: process.env.LZWME_OCR_TOKEN || '' },
      body: JSON.stringify({ mode: 'slide_match', base64: img1, originalBase64: img2 }),
    }).then(d => d.json());
    if (!b.data?.maxLoc.x) console.log('[ocr] decode by lzw:', b);
    return b.data?.maxLoc.x;
  } else {
    const cv = require('@u4/opencv4nodejs');
    const img1CV = cv.imdecode(Buffer.from(img1, 'base64'));
    const img2CV = cv.imdecode(Buffer.from(img2, 'base64'));
    const matched = img1CV.matchTemplate(img2CV, cv.TM_CCOEFF_NORMED);
    const matchedPoints = matched.minMaxLoc();
    return matchedPoints.maxLoc.x;
  }
}

function AES_Encrypt(word: string, k: string) {
  const key = CryptoJS.enc.Utf8.parse(k);
  const srcs = CryptoJS.enc.Utf8.parse(word);
  const encrypted = CryptoJS.AES.encrypt(srcs, key, { mode: CryptoJS.mode.ECB, padding: CryptoJS.pad.Pkcs7 });
  return encrypted.toString();
}

async function signIn(auth: string) {
  let headers = {
    auth,
    hostname: 'scrm-prod.shuyi.org.cn',
    'content-type': 'application/json',
    host: 'scrm-prod.shuyi.org.cn',
    'User-Agent':
      'Mozilla/5.0 (Linux; Android 10; V2203A Build/SP1A.210812.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/107.0.5304.141 Mobile Safari/537.36 XWEB/5023 MMWEBSDK/20221012 MMWEBID/1571 MicroMessenger/8.0.30.2260(0x28001E55) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android',
  };
  let url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/getVCode';
  const data = { captchaType: 'blockPuzzle', clientUid: '', ts: new Date().getTime() };
  let res = await req.post(url, data, headers);
  const { secretKey, token, jigsawImageBase64: img1, originalImageBase64: img2 } = res.data;
  const x = await slider_match(img1, img2);
  if (!x) return '验证码识别失败！';

  url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/checkVCode';
  const pointJson = AES_Encrypt(JSON.stringify({ x, y: 5 }), secretKey);
  res = await req.post(url, { captchaType: 'blockPuzzle', pointJson, token }, headers);

  let captchaVerification = AES_Encrypt(token + '---' + JSON.stringify({ x, y: 5 }), secretKey);
  url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/insertSignInV3';
  res = await req.post(url, `{"captchaVerification":"${captchaVerification}"}`, headers);
  //   console.log('captchaVerification', res);
  if (res.resultMsg == 'success') return '';
  return res.resultMsg;
}

(async () => {
  const token = process.env.sysxc || '';
  const sep = token.includes('&') ? '&' : '\n';
  let arr = token.split(sep);
  if (!token || !arr) return await console.log('未填写token');
  const msgs = [];
  let hasError = false;

  for (let index = 0; index < arr.length; index++) {
    msgs.push(`账号${index + 1}:`);
    const errmsg = await signIn(arr[index]);
    msgs.push(errmsg || '签到成功');
    if (errmsg) hasError = true;
  }
  await sendNotify('书亦烧仙草', msgs.join('\n'), { hasError });
})();
