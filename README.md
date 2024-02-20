# 青龙面板自用脚本

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

## 其他相关

### 获取指定位置的经纬度

- [腾讯位置服务](https://lbs.qq.com/getPoint/)
- [高德地图坐标拾取器](https://lbs.amap.com/tools/picker)
- [详细地址解析成经纬度/GPS坐标在线工具](https://www.toolnb.com/tools/areaDataToGps.html)
- [高德地图拾取器](https://www.toolnb.com/tools/gaodegetmap.html)
