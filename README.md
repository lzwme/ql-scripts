# 支持青龙面板的脚本集

## 免责说明

- 本项目发布的脚本及其中涉及的任何逆向解密分析内容，仅用于个人测试和学习研究，不用于其他任何目的，严禁用于商业用途和非法用途，否则由此产生的一切后果均与作者无关。
- 请自行评估使用本项目内容可能产生的安全风险，不能保证其合法性，准确性，完整性和有效性，请根据情况自行判断。本人对使用本项目涉及的任何脚本引发的问题概不负责，包括但不限于由脚本错误引起的任何损失或损害。
- 间接使用脚本的任何用户，包括但不限于建立VPS或在某些行为违反国家/地区法律或相关法规的情况下进行传播, 本人对于由此引起的任何隐私泄漏或其他后果概不负责。
- 本项目内所有资源文件，禁止任何公众号、自媒体进行任何形式的转载、发布。
- 如果任何单位或个人认为该项目的脚本可能涉嫌侵犯其权利，则应及时通知并提供身份证明，所有权证明，我们将在收到认证文件后删除相关脚本。
- 任何以任何方式查看此项目的人或直接或间接使用该项目的任何脚本的使用者都应仔细阅读此声明。本人保留随时更改或补充此免责声明的权利。一旦使用并复制了任何相关脚本或Script项目的规则，则视为您已接受此免责声明。
- **请在下载本项目后的24小时内予以删除全部内容。**
- 您使用或者复制了本仓库制作的任何脚本，则视为 **已接受** 以上声明，请仔细阅读。

## 安装

### 命令行方式

```bash
# ql repo <repo_url> <whitelist> <blacklist> <dependence> <branch> <extensions>
ql repo https://github.com/lzwme/ql-scripts.git "ql_|ql-" "backup|todo|deprecated" "utils" "" "js ts"
cd /ql/scripts
pnpm add @lzwme/fe-utils commander enquirer moment json5 crypto-js axios
```

### 面板方式

`订阅管理 -> 创建订阅`，表单填写参考：

- 名称：`lzwme/ql-scripts`
- 链接：`https://github.com/lzwme/ql-scripts.git`
- 分支：`main`
- 定时：`0 0 1 * * *`
- 白名单：`ql_|ql-`
- 黑名单：`backup|todo|deprecated`
- 依赖文件：`utils`
- 文件后缀：`js ts`

依赖管理 -> `nodejs` 类型依赖添加：`@lzwme/fe-utils commander enquirer moment json5 crypto-js axios`

## 配置

青龙面板 `配置文件` -> 编辑 `config.sh` 文件，搜索 `RepoFileExtensions`，增加 `ts` 配置。参考：

```bash
RepoFileExtensions="ts js py"
```

各脚本的具体配置，可参考具体脚本内注释说明进行设置。

### 通用环境变量

- `process.env.LZWME_QL_NOTIFY_TYPE` 配置通知策略：
    - 0 - 关闭通知
    - 1 - 仅发送异常时通知。`默认值`
    - 2 - 全通知

### 脚本变量快速自动获取与更新至青龙面板的方法参考

一些脚本的认证参数有效期较短，频繁的手动更新比较麻烦。下面介绍一种基于 `whistle` 代理工具及插件 `@lzwme/whistle.x-scripts` 编写规则，实现自动收集相关环境变量参数并更新至青龙面板的方法。

环境安装与配置（编辑青龙面板的 `配置文件 - extra.sh` 文件，追加如下内容）：

```bash
# 全局安装 whistle 代理工具。注意，需本机已安装 node.js
npm i -g whistle @lzwme/whistle.x-scripts

# 创建工作目录（青龙面板示例）
mkdir -p /ql/data/scripts/whistle
cd /ql/data/scripts/whistle

if [ ! -e w2.x-scripts.config.js ]; then
  cp /usr/local/lib/node_modules/@lzwme/whistle.x-scripts/w2.x-scripts.config.sample.js w2.x-scripts.config.js
fi

# 拉取公开供参考学习的常用脚本规则
if [ ! -e x-scripts-rules ]; then
    git clone https://mirror.ghproxy.com/github.com/lzwme/x-scripts-rules.git
fi

# 用于存放自定义的脚本规则
# 脚本规则编写方法参考：https://github.com/lzwme/whistle.x-scripts.git
mkdir local-x-scripts-rules

# 启动代理插件
w2 start
```

接着 PC 或手机设置代理地址为 `w2 start` 启动打印的地址。代理设置方法参考：https://github.com/lzwme/whistle.x-scripts.git

最后， 从 PC 或手机访问相关脚本对应的 APP 或小程序。在正常使用过程中，当代理插件脚本匹配到目标参数数据，即会自动更新至青龙面板的环境变量中。

此外，还可以在“脚本管理”中新建一个脚本（如 `rules-update.sh`），并新建一个定时任务每天执行一次，用于定时拉取更新公开的脚本规则。示例：

```bash
#! /usr/bin/env bash
cd /ql/data/scripts/whistle/x-scripts-rules
git pull -r -n -v
cd ..
w2 restart
```

扩展参考：

- https://github.com/lzwme/whistle.x-scripts.git
- https://github.com/lzwme/x-scripts-rules.git

## 脚本列表(20)：

- [每日早报-60s读懂世界](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_60s.ts)
- [青龙sendNotify通知修改拦截](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_ModifySendNotify.js)
- [小雅挂载阿里云资源盘清理](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_alipan-clean.ts)
- [阿里云盘签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_alipan_signin.ts)
- [长虹美菱小程序签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_chml.ts)
- [古井贡酒会员中心小程序](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_gujing.ts)
- [哈啰签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_hl.ts)
- [葫芦娃预约](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_huluwa.ts)
- [禁用青龙重复脚本](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_identical.ts)
- [ikuuu机场签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_ikuuu.ts)
- [I茅台预约](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_imaotai.ts)
- [whistle.x-scripts 插件安装与更新](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_install_whistle.x-scripts.ts)
- [品赞代理签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_ipzan_signin.ts)
- [爱奇艺签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_iqiyi.ts)
- [ssone机场签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_ssone.ts)
- [同花顺签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_thsSignIn.ts)
- [腾讯视频VIP会员签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_videoqq.ts)
- [喜马拉雅签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_xmlySign.ts)
- [有赞小程序签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_youzan-liteapp.ts)
- [云闪付签到](https://mirror.ghproxy.com/github.com/lzwme/ql-scripts/raw/main/ql_ysfqd.ts)

## 其他相关

### 获取指定位置的经纬度

- [腾讯位置服务](https://lbs.qq.com/getPoint/)
- [高德地图坐标拾取器](https://lbs.amap.com/tools/picker)
- [详细地址解析成经纬度/GPS坐标在线工具](https://www.toolnb.com/tools/areaDataToGps.html)
- [高德地图拾取器](https://www.toolnb.com/tools/gaodegetmap.html)
