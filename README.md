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

通用配置：

配置文件及格式可参考文件：[lzwme_ql_config.json5](./sample/lzwme_ql_config.json5)
新增环境变量：`LZWME_QL_CONFIG_FILE`，值为 `/ql/data/scripts/lzwme_ql_config.json5`。后续各脚本配置都会从此路径文件读取。

环境变量：

- `process.env.LZWME_QL_CONFIG_FILE` 通用配置文件的路径。默认从当前目录及服务目录查找  `lzwme_ql_config.json5` 文件。
- `process.env.LZWME_QL_NOTIFY_TYPE` 配置通知策略：
    - 0 - 关闭通知
    - 1 - 仅发送异常时通知。`默认值`
    - 2 - 全通知

## 其他相关

### 获取指定位置的经纬度

- [腾讯位置服务](https://lbs.qq.com/getPoint/)
- [高德地图坐标拾取器](https://lbs.amap.com/tools/picker)
- [详细地址解析成经纬度/GPS坐标在线工具](https://www.toolnb.com/tools/areaDataToGps.html)
- [高德地图拾取器](https://www.toolnb.com/tools/gaodegetmap.html)
