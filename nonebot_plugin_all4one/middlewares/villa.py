from datetime import datetime
from typing import Any, Dict, List, Union, Literal, Optional

from nonebot import logger
from pydantic import parse_obj_as
import nonebot.adapters.onebot.v12.exception as ob_exception
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.villa import (
    Bot,
    Event,
    Adapter,
    Message,
    ActionFailed,
    MessageSegment,
    SendMessageEvent,
)

from .base import supported_action
from .base import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "villa"

    async def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
        event_dict = {}
        if (type := event.get_type()) not in ["message", "notice", "request"]:
            return []
        event_dict["type"] = type
        event_dict["self"] = self.get_bot_self().dict()
        event_dict["sub_type"] = ""
        if isinstance(event, SendMessageEvent):
            event_dict["id"] = event.id
            event_dict["time"] = (
                event.send_at
                if event.send_at
                else datetime.now().timestamp()
            )
            event_dict["message_id"] = event.msg_uid
            event_dict["message"] = await self.to_onebot_message(event)
            event_dict["alt_message"] = str(event.get_message())
            event_dict["detail_type"] = "channel"
            event_dict["guild_id"] = str(event.villa_id)
            event_dict["channel_id"] = str(event.room_id)
            event_dict["user_id"] = event.get_user_id()
        else:
            logger.warning(f"未转换事件: {event}")
            return []

        if event_out := OneBotAdapter.json_to_event(
            event_dict, "nonebot-plugin-all4one"
        ):
            return [event_out]
        return []

    async def to_onebot_message(self, event: SendMessageEvent) -> OneBotMessage:
        message = event.get_message()

        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "mention_user":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["user_id"])
                )
            elif segment.type == "mention_all":
                message_list.append(OneBotMessageSegment.mention_all())
        return OneBotMessage(message_list)

    @supported_action
    async def send_message(
        self,
        *,
        detail_type: Union[Literal["private", "group", "channel"], str],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        guild_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        message: OneBotMessage,
        **kwargs: Any,
    ) -> Dict[Union[Literal["message_id", "time"], str], Any]:
        if detail_type not in ["channel"]:
            raise ob_exception.UnsupportedParam("failed", 10004, "不支持的类型", None)
        
        if not guild_id or not channel_id:
            raise ob_exception.UnsupportedParam("failed", 10004, "不支持的类型", None)

        message_list = []
        message = parse_obj_as(OneBotMessage, message)
        for segment in message:
            if segment.type == "text":
                message_list.append(MessageSegment.text(segment.data["text"]))
            elif segment.type == "mention":
                message_list.append(
                    MessageSegment.mention_user(int(segment.data["user_id"]))
                )
            elif segment.type == "mention_all":
                message_list.append(MessageSegment.mention_all())
        
        villa_message = Message(message_list)
        content_info = await self.bot.parse_message_content(villa_message)

        # TODO: 当前仅支持文本消息
        object_name = "MHY:Text"
        try:
            bot_msg_id = await self.bot.send_message(
                villa_id=int(guild_id),
                room_id=int(channel_id),
                object_name=object_name,
                msg_content=content_info,
            )
        except ActionFailed as e:
            raise ob_exception.PlatformError("failed", 34001, str(e), None)

        return {
            "message_id": bot_msg_id,
            "time": datetime.now().timestamp(),
        }
