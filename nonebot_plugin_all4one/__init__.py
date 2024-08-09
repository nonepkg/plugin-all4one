from copy import deepcopy

from nonebot.adapters import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot import on, require, get_driver
from nonebot.message import event_preprocessor

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

from .onebotimpl import Config, OneBotImplementation

__plugin_meta__ = PluginMetadata(
    name="OneBot 实现",
    description="让 NoneBot2 成为 OneBot 实现！",
    usage="""
    obimpl_connections = [{"type":"websocket_rev","url":"ws://127.0.0.1:8080/onebot/v12/"}]
    # 其它连接方式的配置同理
    middlewares = ["OneBot V11"]
    # 自定义加载的 Middleware，默认加载全部
    """,
    type="application",
    homepage="https://github.com/nonepkg/nonebot-plugin-all4one",
    config=Config,
    supported_adapters={"~onebot.v11", "~telegram", "~discord"},
)

driver = get_driver()
obimpl = OneBotImplementation(driver)

on(priority=1, block=False)


@event_preprocessor
async def _(bot: Bot, event: Event):
    if middleware := obimpl.middlewares.get(bot.self_id, None):
        for event in await middleware.to_onebot_event(event):
            for queue in obimpl.queues:
                if queue.full():
                    await queue.get()
                event = deepcopy(event)
                await queue.put(deepcopy(event))
