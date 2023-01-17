from functools import partial
from typing import Any, List

from nonebot.adapters.onebot.v12.event import BotEvent
from nonebot.adapters.onebot.v12 import Bot, Event, Message

from .. import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.events: List[Event] = []

    def get_platform(self):
        return self.bot.platform

    def to_onebot_event(self, event: Event) -> Event:
        if isinstance(event, BotEvent):
            event.self = self.get_bot_self()
        return event

    def from_onebot_message(self, message: Message) -> Message:
        return message

    def to_onebot_message(self, message: Message) -> Message:
        return message

    def __getattribute__(self, __name: str) -> Any:
        if (
            not __name.startswith("__")
            and hasattr(BaseMiddleware, __name)
            and __name not in BaseMiddleware.__abstractmethods__
            and __name != "get_bot_self"
        ):
            return partial(object.__getattribute__(self, "bot").call_api, __name)
        else:
            return object.__getattribute__(self, __name)
