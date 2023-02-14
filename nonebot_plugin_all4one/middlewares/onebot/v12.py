from typing import Any, List

from nonebot.adapters.onebot.v12.event import MessageEvent
from nonebot.adapters.onebot.v12 import Bot, Event, Adapter

from .. import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return self.bot.platform

    def to_onebot_event(self, event: Event) -> List[Event]:
        if isinstance(event, MessageEvent):
            event.message = event.original_message
        return [event]

    async def get_supported_actions(self, **kwargs: Any) -> List[str]:
        return await self.bot.get_supported_actions(**kwargs)

    async def _call_api(self, api: str, **kwargs: Any) -> Any:
        return await self.bot.call_api(api, **kwargs)
