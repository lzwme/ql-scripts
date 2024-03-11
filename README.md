# 支持青龙面板的脚本集

## 免责说明

- 本项目提供的内容用于个人对 web 程序逆向的兴趣研究学习，仅供学习交流使用，不用于其他任何目的，严禁用于商业用途和非法用途，否则由此产生的一切后果均与作者无关。**请在学习研究完毕24小时内予以删除。**
- 请自行评估使用本项目内容可能产生的安全风险。本人对使用本项目涉及的任何脚本引发的问题概不负责，包括但不限于由脚本错误引起的任何损失或损害。

## 安装

### 命令行方式

```bash
# ql repo <repo_url> <whitelist> <blacklist> <dependence> <branch> <extensions>
ql repo https://github.com/lzwme/ql-scripts.git "ql_|ql-" "backup|todo|deprecated" "utils"
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
- 执行后：`pnpm add @lzwme/fe-utils commander enquirer moment`

## 配置

各脚本的具体配置，可参考具体脚本内注释说明进行设置。

### 通用环境变量

- `process.env.LZWME_QL_CONFIG_FILE` 通用配置文件的路径。默认从当前目录及服务目录查找  `lzwme_ql_config.json5` 文件。
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

## 其他相关

### 获取指定位置的经纬度

- [腾讯位置服务](https://lbs.qq.com/getPoint/)
- [高德地图坐标拾取器](https://lbs.amap.com/tools/picker)
- [详细地址解析成经纬度/GPS坐标在线工具](https://www.toolnb.com/tools/areaDataToGps.html)
- [高德地图拾取器](https://www.toolnb.com/tools/gaodegetmap.html)
