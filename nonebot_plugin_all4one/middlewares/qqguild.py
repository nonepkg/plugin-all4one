from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Union, Literal, Optional

from pydantic import parse_obj_as
from nonebot.adapters.qqguild.api import MessageReference
import nonebot.adapters.onebot.v12.exception as ob_exception
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.qqguild import (
    Bot,
    Event,
    Adapter,
    Message,
    MessageEvent,
    MessageSegment,
    MessageCreateEvent,
    DirectMessageCreateEvent,
)

from . import supported_action
from . import Middleware as BaseMiddleware
from ..database import get_file, upload_file


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "qqguild"

    async def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
        event_dict = {}
        if (type := event.get_type()) not in ["message", "notice", "request"]:
            return []
        event_dict["type"] = type
        event_dict["self"] = self.get_bot_self().dict()
        if isinstance(event, MessageEvent):
            event_dict["id"] = event.id
            event_dict["time"] = (
                event.timestamp.timestamp()
                if event.timestamp
                else datetime.now().timestamp()
            )
            event_dict["sub_type"] = ""
            event_dict["message_id"] = event.id
            event_dict["message"] = await self.to_onebot_message(event.get_message())
            event_dict["alt_message"] = str(event.get_message())
            if isinstance(event, DirectMessageCreateEvent):
                event_dict["detail_type"] = "private"
                event_dict["user_id"] = event.get_user_id()
                # 发送私信还需要临时频道 id
                event_dict["guild_id"] = event.guild_id
            elif isinstance(event, MessageCreateEvent):
                event_dict["detail_type"] = "channel"
                event_dict["guild_id"] = event.guild_id
                event_dict["channel_id"] = event.channel_id
                event_dict["user_id"] = event.get_user_id()
        if event_out := OneBotAdapter.json_to_event(
            event_dict, "nonebot-plugin-all4one"
        ):
            return [event_out]
        raise NotImplementedError

    async def to_onebot_message(self, message: Message) -> OneBotMessage:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "mention_user":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["user_id"])
                )
            elif segment.type == "reference":
                message_list.append(
                    OneBotMessageSegment.reply(segment.data["reference"].message_id)
                )
            elif segment.type == "attachment":
                url = segment.data["url"]
                http_url = f"https://{url}" if not url.startswith("https") else url
                file_id = await upload_file(
                    type="url",
                    name=url,
                    url=http_url,
                    src=self.get_platform(),
                    src_id=url,
                )
                message_list.append(OneBotMessageSegment.image(file_id))
            elif segment.type == "mention_everyone":
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
        if detail_type not in ["private", "channel"]:
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
                message_list.append(MessageSegment.mention_everyone())
        qqguild_message = Message(message_list)
        content = qqguild_message.extract_content() or None

        if file_image := (message["image"] or None):
            file_id = file_image[-1].data["file_id"]
            file = await get_file(file_id=file_id, src=self.get_platform())
            with open(Path(file.path), "rb") as f:
                file_image = f.read()
        if reply := (message["reply"] or None):
            message_id = reply[-1].data["message_id"]
            message_reference = MessageReference(message_id=message_id)

        if detail_type == "private":
            result = await self.bot.post_dms_messages(
                guild_id=int(guild_id),  # type: ignore
                content=content,
                msg_id=kwargs.get("event_id"),
                file_image=file_image,  # type: ignore
                message_reference=message_reference,  # type: ignore
            )
        else:
            result = await self.bot.post_messages(
                channel_id=int(channel_id),  # type: ignore
                content=content,
                msg_id=kwargs.get("event_id"),
                file_image=file_image,  # type: ignore
                message_reference=message_reference,  # type: ignore
            )
        # FIXME: 如果是主动消息，返回的时间会是 None
        # 暂时不清楚原因，先用当前时间代替
        time = (
            result.timestamp.timestamp()
            if result.timestamp
            else datetime.now().timestamp()
        )
        return {"message_id": str(result.id), "time": time}
