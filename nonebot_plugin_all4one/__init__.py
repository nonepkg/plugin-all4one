from nonebot import on, get_driver
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.exception import IgnoredException
from nonebot.message import run_preprocessor, event_preprocessor

from .config import Config
from .obimpl import OneBotImplementation
from .middlewares import _middlewares, import_middlewares

driver = get_driver()
a4o_config = Config(**driver.config.dict())
if not a4o_config.obimpl_connections:
    raise Exception("请至少配置一种连接方式！")
onebot_implementation = OneBotImplementation(driver, a4o_config.obimpl_connections)


@driver.on_startup
async def _():
    import_middlewares(
        *a4o_config.middlewares if a4o_config.middlewares else driver._adapters
    )


@driver.on_bot_connect
async def _(bot: Bot):
    if bot.self_id.startswith("a4o@"):
        return
    middleware = _middlewares[bot.type](bot, a4o_config.self_id_prefix)
    onebot_implementation.bot_connect(middleware)


@driver.on_bot_disconnect
async def _(bot: Bot):
    if bot.self_id.startswith("a4o@"):
        return
    if middleware := onebot_implementation.middleswares.get(bot.self_id, None):
        onebot_implementation.bot_disconnect(middleware)


on(priority=1, block=False)


@event_preprocessor
async def _(bot: Bot, event: Event):
    if middle := onebot_implementation.middleswares.get(bot.self_id, None):
        middle.events.append(middle.to_onebot_event(event))
        if a4o_config.block_event:
            raise IgnoredException("All4One has transfer it to OneBot V12")


if not a4o_config.block_event and a4o_config.blocked_plugins:

    @run_preprocessor
    async def _(bot: Bot, matcher: Matcher):
        if (
            bot.type in _middlewares
            and matcher.plugin_name
            and matcher.plugin_name in a4o_config.blocked_plugins  # type: ignore
        ):
            raise IgnoredException("All4One has blocked it")
