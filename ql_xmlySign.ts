/*
 * @Author: renxia
 * @Date: 2024-02-23 13:52:46
 * @LastEditors: renxia
 * @LastEditTime: 2024-03-18 13:16:56
 * @see https://github.com/ClydeTime/Quantumult/blob/main/Script/Task/xmlySign.js
 cron: 35 7 * * *
 new Env('喜马拉雅签到')
 环境变量: xmly_cookie 抓取请求中的 Cookie 。多账户用 @ 或换行分割
 */

import { assign } from '@lzwme/fe-utils';
import { Env } from './utils';

const $ = new Env('喜马拉雅签到', { sep: ['\n', '@'] });
process.env.xmly_cookie = ' channel=ios-b1; 1&_device=iPhone&48B7F647-DD40-4AEA-9BA2-97AA8B81F9F4&9.2.24; impl=com.gemd.iting; NSUP=42E2AD97%2C41B8FD70%2C1710723650383; c-oper=%E7%94%B5%E4%BF%A1; net-mode=WIFI; res=828%2C1792; 1&_token=194130582&F9B45EF0240C5197105DAE34E154DA3DCC28892AEA68D5673491617EF4DC719A64D3ED4CB745170MB70B7AF26D7F39C_; idfa=48B7F647-DD40-4AEA-9BA2-97AA8B81F9F4; device_model=iPhone%2011;  fp=00411264492222422v24v063111010k020211200100000001101341002040##194130582';
$.init(start, 'xmly_cookie').then(() => $.storage.setItem(configKey, config) && $.done());

let configKey = 'xmlyConfig';
let startTime = Date.now();
let xm_cookie = '';
const config = {
  watch: {
    num: 0,
    time: 0,
  },
  spec: {
    num: 0,
    time: 0,
  },
};

async function start(cookie: string) {
  await $.storage.ready();
  assign(config, $.storage.getItem(configKey));

  xm_cookie = cookie = cookie.replaceAll('%26', '&');
  $.req.setHeaders({ 'user-agent': 'ting/9.2.24.3 CFNetwork/1494.0.7 Darwin/23.4.0', cookie });
  startTime = Date.now();

  const sign_flag = await xmlySign();

  if (sign_flag) {
    let watch_message = '';
    let spec_message = '';

    if (check('watch', 5)) {
      let exec_times = 6 - config.watch.num;
      $.log('### 看广告任务进行中');
      for (let i = 0; i < exec_times; i++) {
        let token = await adVideoGetToken();
        if (token != 'null') {
          await adVideoFinish(token);
        } else {
          $.log('- 获取token失败,无法完成观看任务');
        }
      }
      if (config.watch.num == 6) {
        watch_message = `🟢 今日视频任务已全部完成`;
      } else {
        watch_message = `🟡 今日视频任务尚未完成`;
      }
    } else {
      watch_message = `🟢 今日视频任务已全部完成`;
    }
    $.log(watch_message);

    if (check('spec', 5)) {
      await share();
      await voiceAdd();
      await voiceDelete();
      await giveDynamicsLike();
      await cancelDynamicsLike();
      await giveVoiceLike();
      await cancelVoiceLike();
      await userAdd();
      await userDelete();
      /* let actCode = await jumpDzdp()
            if (actCode != "") {
                await dzdpComplete(actCode)
            } */
      let uid = await getUid();
      let content = urlencode(await wyy());
      let commentId = await createComment(uid, content);
      if (commentId != 0) {
        await deleteComment(commentId);
      } else {
        $.log('- 评论失败,无法删除评论');
        $.log('- 遇到此种情况,没有很好的解决办法,建议手动评论并交还任务');
      }

      await flushTaskRecords();
      $.log('### 特殊任务统一交还中');
      config.spec.num = 0;
      config.spec.time = Date.now();
      $.storage.setItem(configKey, config);

      let listset = [96, 168, 169, 170, 171, 336]; //任务列表分别为「分享声音, 收藏声音, 动态点赞, 声音点赞, 关注用户, 声音评论(172变更336), 大众点评(217已失效)」
      for (let i = 0; i < listset.length; i++) {
        await handInGeneralTask(listset[i]);
      }

      if (config.spec.num == 6) {
        spec_message = `🟢 今日特殊任务已全部完成`;
      } else {
        spec_message = `🟡 今日特殊任务尚未全部完成,请查看日志`;
      }
    } else {
      spec_message = `🟢 今日特殊任务已全部完成`;
    }
    $.log(spec_message);
    let message = `🟢【恭喜】签到状态:签到成功 \n` + `${watch_message}\n` + `${spec_message}\n` + '- 其中特殊任务完成进度以app内完成度为准';
    $.log(message);
  } else {
    let message = `🔴【抱歉】签到状态:签到失败 \n` + '请重新获取cookie';
    $.log(message);
  }
}

const check = (key: keyof typeof config, num: number) =>
  !config.hasOwnProperty(key) || !config[key].hasOwnProperty('time') || !(config[key]['num'] > num) || Date.now() > config[key].time;

const urlencode = (str: string) => {
  str = (str + '').toString();
  return encodeURIComponent(str)
    .replace(/!/g, '%21')
    .replace(/'/g, '%27')
    .replace(/\(/g, '%28')
    .replace(/\)/g, '%29')
    .replace(/\*/g, '%2A')
    .replace(/%20/g, '+');
};

async function xmlySign() {
  $.log('### 签到任务进行中');
  const { data: body } = await $.req.post('https://hybrid.ximalaya.com/web-activity/signIn/v2/signIn?v=new', { aid: 87 });

  if (body.ret == 0) {
    $.log(`- 签到成功: ${body.msg || body.data?.msg}`);
    return await getPointInfo();
  } else {
    $.log(`- 签到失败！[${body.ret}]${body.msg || '请重新获取 cookie'}`, 'error');
    console.log(body);
    return false;
  }
}

async function getPointInfo() {
  const { data: body } = await $.req.get('https://m.ximalaya.com/web-hybrid-server/api/point/info', { aid: 87 });

  if (body.ret == 0) {
    configKey = `xmlyConfig_${body.context?.currentUser?.uid}`;
    $.log(`- 当前积分：${body.data.point}`);
    return true;
  } else {
    $.log(`- 积分查询失败！[${body.ret}]${body.msg}`, 'error');
    console.log(body);
    return false;
  }
}

async function flushTaskRecords() {
  const { data: body } = await $.req.post(`https://m.ximalaya.com/web-activity/task/v2/taskRecords?tag=pc`, { aid: 112 });

  if (body.ret == 0) {
    $.log('- 刷新列表成功');
    return true;
  } else {
    $.log('- !!!刷新列表失败', 'error');
    console.log(body);
    return false;
  }
}

async function share() {
  const { data: body } = await $.req.get(
    `https://mobile.ximalaya.com/thirdparty-share/share/content?srcId=422711158&srcType=7&subType=1098&tpName=weixin`
  );
  if (body.ret == 0) {
    $.log('- 分享成功');
    return true;
  } else {
    $.log('- !!!分享失败');
    return false;
  }
}

async function getUid() {
  let uid = 0;
  const { data: body } = await $.req.get(`https://passport.ximalaya.com/user-http-app/v1/nickname/info`);
  if (body.ret == 0) {
    uid = body.data.uid;
    $.log('- 获取uid成功');
    return uid;
  } else {
    $.log('- !!!获取uid失败', 'error');
    return uid;
  }
}

async function wyy() {
  return $.req
    .get('https://keai.icu/apiwyy/api')
    .then((d) => d.data.contetnt as string)
    .catch((error) => {
      $.log('- 获取评论失败:' + (error as Error).message);
      return '真不错呀';
    });
}

async function voiceAdd() {
  let params = { relatedId: 423641159, businessType: 100 };
  const { data: body } = await $.req.post(`https://mobile.ximalaya.com/general-relation-service/track/collect/add/1667873518984`, params);
  if (body.ret == 0) {
    $.log('- 收藏声音成功');
    return true;
  } else if (body.ret == 103) {
    $.log('- !!!此声音已收藏, 无法再次收藏');
    return false;
  } else {
    $.log('- !!!未知收藏状况');
    return false;
  }
}

async function voiceDelete() {
  let params = { relatedId: 423641159, businessType: 100 };
  const { data: body } = await $.req.post(
    `https://mobile.ximalaya.com/general-relation-service/track/collect/delete/1667873518984`,
    params
  );

  if (body.ret == 0) {
    $.log('- 删除收藏声音成功');
    return true;
  } else if (body.ret == 112) {
    $.log('- !!!此声音未收藏, 无法删除');
    return false;
  } else {
    $.log('- !!!未知收藏状况');
    return false;
  }
}

async function userAdd() {
  let p = { bizType: 11, isFollow: 1, toUid: 2342717 };
  let url = `https://mobile.ximalaya.com/mobile/follow`;
  const { data: body } = await $.req.post(url, p, { 'Content-Type': `application/x-www-form-urlencoded` });
  if (body.ret == 0) {
    $.log('- 关注用户成功');
    return true;
  } else if (body.ret == 3002) {
    $.log('- !!!此用户已关注过');
    return false;
  } else if (body.ret == 3001) {
    $.log('- !!!关注频率过高,无法关注');
    $.log('- 遇到此种情况,没有很好的解决办法,建议手动关注并交还任务');
    return false;
  } else {
    $.log('- !!!未知关注状况');
    $.log(JSON.stringify(body));
    return false;
  }
}

async function userDelete() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/x-www-form-urlencoded`,
  };
  let body = `bizType=13&isFollow=0&toUid=2342717`;
  return await fetch(`https://mobile.ximalaya.com/mobile/follow`, {
    method: 'post',
    headers,
    body,
  })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 取关用户成功');
        return true;
      } else {
        $.log('- !!!未知关注状况');
        return false;
      }
    })
    .catch(() => {
      $.log('- !!!取关用户失败');
      return false;
    });
}

async function giveVoiceLike() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/x-www-form-urlencoded`,
  };
  let body = `favorite=1&trackId=423641159`;
  let url = `https://mobile.ximalaya.com/favourite-business/favorite/track`;
  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 点赞声音成功');
        return true;
      } else if (body.ret == 111) {
        $.log('- !!!此声音已点赞过');
        return false;
      } else {
        $.log('- !!!未知声音点赞状况');
        return false;
      }
    })
    .catch(() => {
      $.log('- !!!点赞声音失败');
      return false;
    });
}

async function cancelVoiceLike() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/x-www-form-urlencoded`,
  };
  let body = `favorite=0&trackId=423641159`;
  let url = `https://mobile.ximalaya.com/favourite-business/favorite/track`;
  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 取消声音点赞成功');
        return true;
      } else if (body.ret == -1) {
        $.log('- !!!此声音尚未点赞, 无法取消');
        return false;
      } else {
        $.log('- !!!未知声音点赞状况');
        return false;
      }
    })
    .catch(() => {
      $.log('- !!!取消声音点赞失败');
      return false;
    });
}

async function giveDynamicsLike() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/json`,
  };
  let body = `{"feedId":217014623}`;
  let url = `https://mobile.ximalaya.com/chaos/v2/feed/praise/create`;

  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 点赞动态成功');
        return true;
      } else {
        $.log('- !!!未知动态点赞状况');
        return false;
      }
    });
}

async function cancelDynamicsLike() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/json`,
  };
  let body = `{"feedId":217014623}`;
  let url = `https://mobile.ximalaya.com/chaos/v2/feed/praise/delete`;
  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 取消动态点赞成功');
        return true;
      } else {
        $.log('- !!!未知动态点赞状况');
        return false;
      }
    });
}

async function createComment(uid: number | string, content: string) {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/x-www-form-urlencoded`,
  };
  let body = `content=${content}&source=0&synchaos=1&timeStampType=1&trackId=424771991&uid=${uid}`;
  let url = 'https://mobile.ximalaya.com/comment-mobile/v1/create';
  let commentId = 0;
  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 评论成功');
        commentId = body.id;
      } else if (body.ret == 801) {
        $.log('- !!!请勿发送相同内容');
      } else if (body.ret == 805) {
        $.log('- !!!发送内容频繁');
      } else {
        $.log('- !!!评论失败');
      }
      return commentId;
    });
}

async function deleteComment(commentId: number) {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/x-www-form-urlencoded`,
  };
  let body = `commentId=${commentId}&trackId=424771991`;
  let url = 'https://mobile.ximalaya.com/comment-mobile/delete';
  return await fetch(url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        $.log('- 删除评论成功');
        return true;
      } else {
        $.log('- !!!未知评论状态');
        return false;
      }
    });
}

async function adVideoGetToken() {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/json`,
  };
  let body = `{"aid":112,"taskId":252}`;
  let myRequest = {
    url: `https://m.ximalaya.com/web-activity/task/v2/genTaskToken`,
    headers: headers,
    body: body,
  };
  return await fetch(myRequest.url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        let token = body.data.token;
        return token;
      } else {
        $.log('- !!!token获取失败');
        let token = 'null';
        return token;
      }
    });
}

async function adVideoFinish(token: string) {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/json`,
  };
  let body = `{"aid":112,"taskId":252,"token":"${token}","progress":1}`;
  let myRequest = {
    url: `https://m.ximalaya.com/web-activity/task/v2/incrTaskProgress`,
    headers: headers,
    body: body,
  };
  return await fetch(myRequest.url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        if (body.data.status == 0) {
          $.log('- 本条视频广告观看已完成, 获得50点奖励');
          config.watch.num += 1;
          config.watch.time = startTime;
          return true;
        } else if (body.data.status == -1) {
          $.log('### 今日观看广告任务已全部完成 ✅ ');
          config.watch.num = 6;
          config.watch.time = startTime;
          $.storage.setItem(configKey, config);
          return true;
        } else {
          $.log('- !!!未知完成状态');
          $.log(JSON.stringify(body.data));
          return false;
        }
      } else {
        $.log('- !!!观看广告任务交还失败');
        return false;
      }
    });
}

async function handInGeneralTask(taskId: number) {
  let headers = {
    Cookie: xm_cookie,
    'Content-Type': `application/json`,
  };
  let body = `{"aid":112,"taskId":${taskId}}`;
  let myRequest = {
    url: `https://m.ximalaya.com/web-activity/task/v2/drawTaskAward`,
    headers: headers,
    body: body,
  };
  return await fetch(myRequest.url, { method: 'post', headers, body })
    .then((d) => d.json())
    .then((body) => {
      if (body.ret == 0) {
        if (body.data.status == 0) {
          if ((taskId > 167 && taskId < 173) || taskId == 96 || taskId == 336) {
            config.spec.num += 1;
            config.spec.time = startTime;
            $.log('- 交还特殊任务成功, 获得奖励点数');
          } /* else {
                        config.gene.num += 1
                        config.gene.time = format(startTime)
                        $.setdata(JSON.stringify(config.gene), name + "_gene")
                        $.log("- 交还通用任务成功, 获得10点奖励")
                    } */
          return true;
        } else if (body.data.status == 1) {
          if ((taskId > 167 && taskId < 173) || taskId == 96 || taskId == 336) {
            config.spec.num += 1;
            config.spec.time = startTime;
            $.log('- 此项特殊任务今日已交还');
          } /* else {
                        config.gene.num += 1
                        config.gene.time = format(startTime)
                        $.setdata(JSON.stringify(config.gene), name + "_gene")
                        $.log("- 此项通用任务今日已交还")
                    } */
          return true;
        } else if (body.data.status == -1) {
          $.log('--- !!!此任务尚未完成,不能交还');
          return false;
        } else {
          $.log('--- !!!未知交还状态');
          $.log(JSON.stringify(body.data));
          return false;
        }
      } else {
        $.log('--- !!!交还任务失败');
        return false;
      }
    });
}
