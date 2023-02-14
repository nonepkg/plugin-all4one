from datetime import datetime
from typing import Any, Dict, Union, Literal, Optional

from pydantic import parse_obj_as
from nonebot.adapters.console import Adapter
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.console.bot import Bot, Event, Message, MessageEvent
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.onebot.v12.event import (
    PrivateMessageEvent as OneBotPrivateMessageEvent,
)

from . import supported_action
from . import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    bot: Bot

    def __init__(self, bot: Bot):
        super().__init__(bot)
        self.id = 0

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "console"

    def to_onebot_event(self, event: Event):
        if isinstance(event, MessageEvent):
            self.id = self.id + 1
            return [
                OneBotPrivateMessageEvent(
                    id=str(self.id),
                    time=datetime.now(),
                    type="message",
                    detail_type="private",
                    sub_type="",
                    self=self.get_bot_self(),
                    message_id=str(self.id),
                    original_message=self.to_onebot_message(event.message),
                    message=self.to_onebot_message(event.message),
                    alt_message=str(event.message),
                    user_id=event.user.id,
                )
            ]

        raise NotImplementedError

    def from_onebot_message(self, message: OneBotMessage) -> Message:
        return Message(str(message))

    def to_onebot_message(self, message: Message) -> OneBotMessage:
        return OneBotMessage(OneBotMessageSegment.text(str(message)))

    @supported_action
    async def send_message(
        self,
        *,
        detail_type: Union[Literal["private", "group", "channel"], str],
        user_id: str,
        group_id: Optional[str] = None,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        message: OneBotMessage,
        **kwargs: Any,
    ) -> Dict[Union[Literal["message_id", "time"], str], Any]:
        await self.bot.send_msg(
            user_id=user_id,
            message=self.from_onebot_message(parse_obj_as(OneBotMessage, message)),
        )
        self.id = self.id + 1
        return {"message_id": str(self.id), "time": int(datetime.now().timestamp())}
