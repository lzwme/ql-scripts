#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 .env 载入工具，让 python 脚本与 node 侧 `import 'dotenv/config'` 能力对齐。

用法（推荐，脚本顶部可选导入，import 时自动载入 .env；文件缺失/异常不影响脚本运行）：
    try:
        from utils import qlenv  # noqa: F401  可选 .env 支持
    except Exception:
        pass

若脚本与 qlenv.py 同目录（单独下载运行时），也可 `import qlenv`。

也可手动控制：
    from utils.qlenv import load_dotenv
    load_dotenv()                    # 默认不覆盖已存在的环境变量
    load_dotenv('/path/.env', override=True)

特性：
  - 无第三方依赖；优先级：真实环境变量 > .env（与 python-dotenv 默认一致）
  - 支持 `export KEY=VALUE`、# 注释、行尾注释、单/双引号（含多行值）
  - 双引号内支持转义：\\n \\t \\r \\" \\\\ ；单引号内为原样文本
  - .env 查找顺序：QL_ENV_FILE 指定 > 运行脚本所在目录 > 本模块目录 > 当前工作目录
  - 空值仅跳过不注入；QL_ENV_DISABLED=1 可禁止自动载入
"""
import os
import re
import sys

__all__ = ['load_dotenv', 'parse_env', 'find_dotenv']

_KEY_RE = re.compile(r'^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=(.*)$')
_INLINE_COMMENT_RE = re.compile(r'\s+#.*$')
_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', "'": "'", '\\': '\\', '`': '`', '$': '$'}


def _read_quoted(body, quote):
    """读取引号内内容，返回 (value, rest)；未闭合返回 None"""
    if quote == "'":
        end = body.find("'")
        return (body[:end], body[end + 1:]) if end >= 0 else None
    out, j = [], 0
    while j < len(body):
        c = body[j]
        if c == '\\':
            nxt = body[j + 1:j + 2]
            out.append(_ESCAPES.get(nxt, '\\' + nxt))
            j += 2
            continue
        if c == quote:
            return ''.join(out), body[j + 1:]
        out.append(c)
        j += 1
    return None


def parse_env(text):
    """解析 .env 文本，返回 {key: value}（同名 key 以最后定义为准）"""
    result = {}
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = _KEY_RE.match(line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw[:1] in ('"', "'"):
            quote, body = raw[0], raw[1:]
            parsed = _read_quoted(body, quote)
            while parsed is None and i < n:  # 多行引号值
                body += '\n' + lines[i]
                i += 1
                parsed = _read_quoted(body, quote)
            value = parsed[0] if parsed else body
        else:
            value = _INLINE_COMMENT_RE.sub('', raw).strip()
        result[key] = value  # 同名 key 以最后定义为准
    return result


def find_dotenv(filename='.env'):
    """按优先级查找 .env 文件路径，找不到返回 ''"""
    explicit = os.environ.get('QL_ENV_FILE', '').strip()
    if explicit:
        if os.path.isdir(explicit):
            explicit = os.path.join(explicit, filename)
        return explicit if os.path.isfile(explicit) else ''

    dirs = []
    try:
        if sys.argv and sys.argv[0] and sys.argv[0] not in ('-c', '-'):
            dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    except Exception:
        pass
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.getcwd())
    for d in dirs:
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            return p
    return ''


_loaded = False


def load_dotenv(path=None, override=False, filename='.env'):
    """载入 .env 并注入 os.environ；返回本次实际注入的 {key: value}"""
    global _loaded
    path = path or find_dotenv(filename)
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            envs = parse_env(f.read())
    except Exception as e:
        print('[qlenv] 读取 %s 失败: %s' % (path, e), file=sys.stderr)
        return {}
    injected = {}
    for k, v in envs.items():
        if not v or (k in os.environ and not override):
            continue
        os.environ[k] = v
        injected[k] = v
    if path:
        _loaded = True
    return injected


if not os.environ.get('QL_ENV_DISABLED', '').strip() in ('1', 'true', 'yes'):
    load_dotenv()


if __name__ == '__main__':
    f = find_dotenv()
    print('[qlenv] .env 路径:', f or '(未找到)')
    if f:
        keys = sorted(parse_env(open(f, encoding='utf-8-sig').read()))
        print('[qlenv] 共 %d 个配置项: %s' % (len(keys), ', '.join(keys) or '-'))
