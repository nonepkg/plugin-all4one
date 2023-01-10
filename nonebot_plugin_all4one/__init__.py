import time

from nonebot import get_driver
from nonebot.adapters.telegram import Bot
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor
from nonebot.adapters.telegram.message import Entity
from nonebot.adapters.telegram.event import MessageEvent

from . import obimpl as obimpl
from .middlewares import import_middlewares

get_driver().on_startup(import_middlewares)


@event_preprocessor
async def _(bot: Bot, event: MessageEvent):
    # TODO
    raise IgnoredException("All4One has transfer it to OneBot V12")  # TODO 可配置是否跳过
