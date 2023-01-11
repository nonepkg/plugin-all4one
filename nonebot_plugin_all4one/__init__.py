import time

from nonebot import get_driver
from nonebot.adapters import Bot, Event
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor

from .obimpl import OneBotImplementation
from .middlewares import import_middlewares

driver = get_driver()
onebot_implementation = OneBotImplementation(get_driver())


@driver.on_startup
async def _():
    import_middlewares(*driver._adapters.keys())


@driver.on_bot_connect
async def _(bot: Bot):
    if bot.self_id.startswith("a4o@"):
        return
    onebot_implementation.bot_connect(bot)


@event_preprocessor
async def _(bot: Bot, event: Event):
    if middle := onebot_implementation.middleswares.get(bot.self_id, None):
        middle.events.append(middle.to_onebot_event(event))
        raise IgnoredException("All4One has transfer it to OneBot V12")  # TODO 可配置是否跳过
