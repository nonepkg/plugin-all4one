<div align="center">
    <img width="200" src="https://raw.githubusercontent.com/nonepkg/nonebot-plugin-all4one/master/docs/logo.png" alt="logo"></br>

# Nonebot Plugin All4One

让 [NoneBot2](https://github.com/nonebot/nonebot2) 成为 OneBot 实现！

[![License](https://img.shields.io/github/license/nonepkg/nonebot-plugin-all4one?style=flat-square)](LICENSE)
[![codecov](https://codecov.io/gh/nonepkg/plugin-all4one/branch/master/graph/badge.svg?token=BOK429DAHO)](https://codecov.io/gh/nonepkg/plugin-all4one)  
[![pdm-managed](https://img.shields.io/endpoint?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fpdm-project%2F.github%2Fbadge.json)](https://pdm-project.org)
![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)  
[![PyPI Version](https://img.shields.io/pypi/v/nonebot-plugin-all4one.svg?style=flat-square)](https://pypi.python.org/pypi/nonebot-plugin-all4one)
[![OneBot 4A](https://img.shields.io/badge/OneBot-4A-black?style=flat-square)](https://onebot4all.vercel.app/)
[![NoneBot Version](https://img.shields.io/badge/nonebot-2.3.0+-red.svg?style=flat-square)](https://v2.nonebot.dev/)
[![NoneBot Registry](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin%2Fnonebot-plugin-all4one)](https://registry.nonebot.dev/plugin/nonebot-plugin-all4one:nonebot_plugin_all4one)
[![Supported Adapters](https://img.shields.io/endpoint?url=https%3A%2F%2Fnbbdg.lgc2333.top%2Fplugin-adapters%2Fnonebot-plugin-all4one)](https://registry.nonebot.dev/plugin/nonebot-plugin-all4one:nonebot_plugin_all4one)

</div>

## 安装

- 使用 nb-cli

```sh
nb plugin install nonebot-plugin-all4one
```

- 使用 pdm

```sh
pdm add nonebot-plugin-all4one
```

## 使用

```dotenv
obimpl_connections = [{"type":"websocket_rev","url":"ws://127.0.0.1:8080/onebot/v12/"}] # 其它连接方式的配置同理
middlewares = ["OneBot V11"] # 自定义加载的 Middleware，默认加载全部
```

## Feature

### OneBot

- [x] HTTP
- [x] HTTP Webhook
- [x] 正向 WebSocket
- [x] 反向 WebSocket

### Middlewares

- [x] [OneBot V11](https://github.com/nonebot/adapter-onebot)
- [x] [Telegram](https://github.com/nonebot/adapter-telegram)
- [x] [Discord](https://github.com/nonebot/adapter-discord) 测试中
- [ ] [QQ](https://github.com/nonebot/adapter-qq) [@he0119](https://github.com/he0119) 寻求新维护者

## 相关链接

- [nonebot/adapter-onebot](https://github.com/nonebot/adapter-onebot) 复用代码
- [zhamao-robot/go-cqhttp-adapter-plugin](https://github.com/zhamao-robot/go-cqhttp-adapter-plugin) OneBot V11 -> V12 逻辑参考
- [iyume/nonebot-plugin-params](https://github.com/iyume/nonebot-plugin-params) 灵感来源
- [felinae98/nonebot-plugin-send-anything-anywhere](https://github.com/felinae98/nonebot-plugin-send-anything-anywhere) 友情推荐
- [nonebot/plugin-alconna](https://github.com/nonebot/plugin-alconna) 同上
