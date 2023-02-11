# Nonebot Plugin All4One

让 [NoneBot2](https://github.com/nonebot/nonebot2) 成为 OneBot 实现！

[![License](https://img.shields.io/github/license/nonepkg/nonebot-plugin-all4one?style=flat-square)](LICENSE)
![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square)
![NoneBot Version](https://img.shields.io/badge/nonebot-2.0.0rc2+-red.svg?style=flat-square)
[![OneBot V12](https://img.shields.io/badge/OneBot-12-black?style=flat-square)](https://12.onebot.dev/)
[![PyPI Version](https://img.shields.io/pypi/v/nonebot-plugin-all4one.svg?style=flat-square)](https://pypi.python.org/pypi/nonebot-plugin-all4one)

## 安装

### 从 PyPI 安装（推荐）

- 使用 nb-cli  

```sh
nb plugin install nonebot-plugin-all4one
```

- 使用 pdm

```sh
pdm add nonebot-plugin-all4one
```

- 使用 pip

```sh
pip install nonebot-plugin-all4one
```

### 从 GitHub 安装（不推荐）

```sh
pdm add git+https://github.com/nonepkg/nonebot-plugin-all4one
```

## 使用

```dotenv
obimpl_connections = [{"type":"websocket_rev","url":"ws://127.0.0.1:8080/onebot/v12/"},{"type":"websocket_rev","url":"ws://127.0.0.1:4000/onebot/v12/", "self_id_prefix": "True"}] # 其它连接方式的配置同理
middlewares = ["OneBot V11"] # 自定义加载的 Middleware，默认加载全部
block_event = False # 是否中止已转发 Event 的处理流程，默认中止
blocked_plugins = ["echo"] # 在 block_event=False 时生效，可自定义处理流程中要中止的插件
```

## Feature

### OneBot

- [x] HTTP 测试中
- [x] HTTP Webhook 测试中
- [x] 正向 WebSocket 测试中
- [x] 反向 WebSocket

### Middlewares

- [x] Console -> OneBot V12
- [x] OneBot V11 -> OneBot V12 测试中
- [x] OneBot V12 -> OneBot V12
- [x] Telegram -> OneBot V12 测试中
- [ ] Kaiheila -> OneBot V12

## 鸣谢

All4One 的出现离不开以下项目：

- [nonebot-adapter-onebot](https://github.com/nonebot/adapter-onebot) 复用代码
- [zhamao-robot/go-cqhttp-adapter-plugin](https://github.com/zhamao-robot/go-cqhttp-adapter-plugin) OneBot V11 -> V12 逻辑参考
- [nonebot-plugin-params](https://github.com/iyume/nonebot-plugin-params) 灵感来源
