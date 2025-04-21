/*
 * @Author: renxia
 * @Date: 2025-04-17 20:50:46
 * @LastEditors: renxia
 * @LastEditTime: 2025-04-21 09:07:01
 * 每日天气推送。API 参考： https://www.sojson.com/api/weather.html
 cron: 30 7 1 1 1
 new Env('每日天气')

 环境变量:
 export city_code='101280101' # 城市code，可访问这个网址搜索查找： https://fastly.jsdelivr.net/gh/Oreomeow/checkinpanel@master/city.json
 */

import { sendNotify } from './utils';

interface WeatherData {
  cityInfo: {
    city: string;
  };
  data: {
    forecast: Array<{
      ymd: string;
      week: string;
      type: string;
      high: string;
      low: string;
      fx: string;
      fl: string;
      notice: string;
    }>;
    shidu: string;
    quality: string;
    pm25: string;
    pm10: string;
    ganmao: string;
  };
  time: string;
}

async function start(city_code?: string) {
  if (!city_code) city_code = process.env.city_code; // 北京： 101010100 广州 101280101
  if (!city_code) {
    console.log(
      'city_code 环境变量未配置。可访问该网址查找你的城市：https://fastly.jsdelivr.net/gh/Oreomeow/checkinpanel@master/city.json'
    );
    return;
  }

  const data: WeatherData = await fetch(`http://t.weather.itboy.net/api/weather/city/${city_code}`).then(d => d.json());
  // console.log(data);

  // 当天天气信息
  const today = data.data.forecast[0];
  const msg = [
    `城市：${data.cityInfo.city}`,
    `日期：${today.ymd} ${today.week}`,
    `天气：${today.type}`,
    `温度：${today.high} ${today.low}`,
    `湿度：${data.data.shidu}`,
    `空气质量：${data.data.quality}`,
    `PM2.5：${data.data.pm25}`,
    `PM10：${data.data.pm10}`,
    `风力风向：${today.fx} ${today.fl}`,
    `感冒指数：${data.data.ganmao}`,
    `[💌]温馨提示：${today.notice}`,
    `更新时间：${data.time}`,
  ].join('\n');

  // 未来 N 天天气预报
  const sevenDaysWeather = data.data.forecast.map(day => [
    day.ymd.replaceAll('-', '').slice(4),
    day.week.replace('星期', ''),
    `${day.low}~${day.high}`.replace('低温 ', '').replace('高温 ', ''),
    day.type,
    // day.notice,
  ]);
  const formattedSevenDays = sevenDaysWeather.map(day => day.join(' ')).join('\n');
  const body = `${msg}\n\n${formattedSevenDays}`;

  await sendNotify(`${data.cityInfo.city}今日天气`, body, { notifyType: 2, isPrint: true });
}

start()
  .catch(error => console.error('程序运行失败:', error))
  .finally(() => process.exit());
