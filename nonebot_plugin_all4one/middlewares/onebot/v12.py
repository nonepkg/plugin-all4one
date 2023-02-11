from typing import Any, List
from functools import partial

from nonebot.adapters.onebot.v12 import Bot, Event
from nonebot.adapters.onebot.v12.event import BotEvent, MessageEvent

from .. import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    bot: Bot

    def get_platform(self):
        return self.bot.platform

    def to_onebot_event(self, event: Event) -> List[Event]:
        if isinstance(event, BotEvent):
            event.self = self.get_bot_self()
        if isinstance(event, MessageEvent):
            event.message = event.original_message
        return [event]

    def __getattribute__(self, __name: str) -> Any:
        if (
            not __name.startswith("__")
            and __name not in BaseMiddleware.__abstractmethods__
            and __name not in ("events", "get_bot_self")
            and not hasattr(object.__getattribute__(self, __name), "is_supported")
        ):
            return partial(object.__getattribute__(self, "bot").call_api, __name)
        else:
            return object.__getattribute__(self, __name)
