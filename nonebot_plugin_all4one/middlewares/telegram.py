from typing import Any, Dict, List, Union, Literal

from pydantic import parse_obj_as
from nonebot.adapters.telegram import Bot, Event, Message
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.telegram.event import PrivateMessageEvent
from nonebot.adapters.onebot.v12.event import (
    PrivateMessageEvent as OneBotPrivateMessageEvent,
)

from . import Middleware as BaseMiddleware, supported_action


class Middleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.events: List[OneBotEvent] = []

    def get_platform(self):
        return "telegram"

    def to_onebot_event(self, event: Event) -> OneBotEvent:
        if isinstance(event, PrivateMessageEvent):
            return OneBotPrivateMessageEvent(
                id=str(event.telegram_model.update_id),
                time=event.date,  # type:ignore
                type="message",
                detail_type="private",
                sub_type="",
                self=self.get_bot_self(),
                message_id=str(event.message_id),
                original_message=self.to_onebot_message(
                    event.message
                ),  # event.message,
                message=self.to_onebot_message(event.message),
                alt_message=str(event.message),
                user_id=str(event.from_.id),
            )
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
        user_id: str = ...,
        group_id: str = ...,
        guild_id: str = ...,
        channel_id: str = ...,
        message: OneBotMessage,
        **kwargs: Any,
    ) -> Dict[Union[Literal["message_id", "time"], str], Any]:
        if detail_type == "group":
            chat_id = group_id
        elif detail_type == "private":
            chat_id = user_id
        else:
            chat_id = channel_id
        result = (
            await self.bot.send_message(
                chat_id=chat_id,
                text=str(parse_obj_as(OneBotMessage, message)),
            )
        )["result"]
        return {"message_id": result["message_id"], "time": result["date"]}
