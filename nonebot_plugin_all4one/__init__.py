from copy import deepcopy

from nonebot import on, get_driver
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.exception import IgnoredException
from nonebot.message import run_preprocessor, event_preprocessor

from .config import Config
from .onebotimpl import OneBotImplementation

driver = get_driver()
a4o_config = Config(**driver.config.dict())
obimpl = OneBotImplementation(driver)

on(priority=1, block=False)


@event_preprocessor
async def _(bot: Bot, event: Event):
    if middleware := obimpl.middlewares.get(bot.self_id, None):
        for event in middleware.to_onebot_event(event):
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
