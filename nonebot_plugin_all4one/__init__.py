from copy import deepcopy

from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot import on, require, get_driver
from nonebot.exception import IgnoredException
from nonebot.message import run_preprocessor, event_preprocessor

require("nonebot_plugin_datastore")

from .config import Config
from .onebotimpl import OneBotImplementation

__plugin_meta__ = PluginMetadata(
    name="OneBot 实现",
    description="让 NoneBot2 成为 OneBot 实现！",
    usage="""obimpl_connections = [{"type":"websocket_rev","url":"ws://127.0.0.1:8080/onebot/v12/"},{"type":"websocket_rev","url":"ws://127.0.0.1:4000/onebot/v12/", "self_id_prefix": "True"}] # 其它连接方式的配置同理
middlewares = ["OneBot V11"] # 自定义加载的 Middleware，默认加载全部
block_event = False # 是否中止已转发 Event 的处理流程，默认中止
blocked_plugins = ["echo"] # 在 block_event=False 时生效，可自定义处理流程中要中止的插件""",
    type="application",
    homepage="https://github.com/nonepkg/nonebot-plugin-all4one",
    config=Config,
    supported_adapters={"~console", "~onebot.v11", "~telegram", "~qqguild"},
)

driver = get_driver()
a4o_config = Config(**driver.config.dict())
obimpl = OneBotImplementation(driver)

on(priority=1, block=False)


@event_preprocessor
async def _(bot: Bot, event: Event):
    if middleware := obimpl.middlewares.get(bot.self_id, None):
        for event in await middleware.to_onebot_event(event):
            for queue in middleware.queues:
                if queue.full():
                    await queue.get()
                await queue.put(deepcopy(event))
        if a4o_config.block_event:
            raise IgnoredException("All4One has transfer it to OneBot V12")


if not a4o_config.block_event and a4o_config.blocked_plugins:

    @run_preprocessor
    async def _(bot: Bot, matcher: Matcher):
        if (
            bot.type in obimpl._middlewares
            and matcher.plugin_name
            and matcher.plugin_name in a4o_config.blocked_plugins  # type: ignore
        ):
            raise IgnoredException("All4One has blocked it")
