import time
from typing import Any, Dict, List, Union, Literal

from pydantic import parse_obj_as
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.console.bot import Bot, Event, Message, MessageEvent
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.onebot.v12.event import (
    PrivateMessageEvent as OneBotPrivateMessageEvent,
)

from . import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.events: List[OneBotEvent] = []
        self.id = 0

    def get_platform(self):
        return "console"

    def to_onebot_event(self, event: Event) -> OneBotEvent:
        if isinstance(event, MessageEvent):
            self.id = self.id + 1
            return OneBotPrivateMessageEvent(
                id=str(self.id),
                time=time.time(),  # type: ignore
                type="message",
                detail_type="private",
                sub_type="",
                self=self.get_bot_self(),
                message_id=str(self.id),
                original_message=self.to_onebot_message(
                    event.message
                ),  # event.message,
                message=self.to_onebot_message(event.message),
                alt_message=str(event.message),
                user_id=event.user_info.user_id,
            )
        raise NotImplementedError

    def from_onebot_message(self, message: OneBotMessage) -> Message:
        return Message(str(message))

    def to_onebot_message(self, message: Message) -> OneBotMessage:
        return OneBotMessage(OneBotMessageSegment.text(str(message)))

    async def send_message(
        self,
        *,
        detail_type: Union[Literal["private", "group", "channel"], str],
        user_id: str = ...,
        group_id: str = ...,
        guild_id: str = ...,
        channel_id: str = ...,
        message: OneBotMessage,
        **kwargs: Any,
    ) -> Dict[Union[Literal["message_id", "time"], str], Any]:
        print(str(parse_obj_as(OneBotMessage, message)))
        await self.bot.send_message(
            message=str(parse_obj_as(OneBotMessage, message)),
        )
        self.id = self.id + 1
        return {"message_id": str(self.id), "time": time.time()}
