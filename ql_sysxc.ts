/*
 * @Author: renxia
 * @Date: 2024-02-19 13:34:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-02-20 15:06:48
 * @Description: 书亦烧仙草小程序签到

 cron: 11 10 * * *
 const $ = new Env("书亦烧仙草签到");
 环境变量 sysxc，抓包获取 header 中的 auth，多个账户以 & 或 \n 换行分割
 */
import CryptoJS from 'crypto-js';
import axios from 'axios';
import { Env } from './utils';

const $ = new Env('书亦烧仙草签到');
$.init(signIn, 'sysxc').then(() => $.done());

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
  const headers = {
    auth,
    hostname: 'scrm-prod.shuyi.org.cn',
    'content-type': 'application/json',
    host: 'scrm-prod.shuyi.org.cn',
    'User-Agent':
      'Mozilla/5.0 (Linux; Android 10; V2203A Build/SP1A.210812.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/107.0.5304.141 Mobile Safari/537.36 XWEB/5023 MMWEBSDK/20221012 MMWEBID/1571 MicroMessenger/8.0.30.2260(0x28001E55) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android',
  };
  let url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/getVCode';
  const { data: vCodeRes } = await axios.post(url, { captchaType: 'blockPuzzle', clientUid: '', ts: new Date().getTime() }, { headers });
  const { secretKey, token, jigsawImageBase64: img1, originalImageBase64: img2 } = vCodeRes.data;
  const x = await slider_match(img1, img2);
  if (!x) return $.log('验证码识别失败！', 'error');

  url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/checkVCode';
  const pointJson = AES_Encrypt(JSON.stringify({ x, y: 5 }), secretKey);
  const { data: checkVCodeRes } = await axios.post(url, { captchaType: 'blockPuzzle', pointJson, token }, { headers });
  if (checkVCodeRes.resultMsg) console.log(checkVCodeRes.resultMsg);

  const captchaVerification = AES_Encrypt(token + '---' + JSON.stringify({ x, y: 5 }), secretKey);
  url = 'https://scrm-prod.shuyi.org.cn/saas-gateway/api/agg-trade/v1/signIn/insertSignInV3';
  const { data: signInRes } = await axios.post(url, `{"captchaVerification":"${captchaVerification}"}`, { headers });
  signInRes.resultMsg == 'success' ? $.log('签到成功') : $.log(signInRes.resultMsg, 'error');
}
