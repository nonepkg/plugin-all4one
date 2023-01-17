import time
import uuid
from typing import Any, Dict, List, Union, Literal, Optional

from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.onebot.v11.event import (
    MetaEvent,
    NoticeEvent,
    MessageEvent,
    RequestEvent,
    HeartbeatMetaEvent,
    FriendAddNoticeEvent,
    GroupRecallNoticeEvent,
    FriendRecallNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
)

from .. import Middleware as BaseMiddleware, supported_action


class Middleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.events: List[OneBotEvent] = []

    def get_platform(self):
        return "qq"

    def to_onebot_event(self, event: Event) -> OneBotEvent:
        replaced_by_detail_type = (
            "notice_type",
            "message_type",
            "request_type",
            "meta_event_type",
        )
        should_be_str = (
            "message_id",
            "user_id",
            "operator_id",
            "group_id",
            "guild_id",
            "channel_id",
        )
        good_to_be_ob12 = ("time", "sub_type", "to_me")
        event_dict = {
            f"qq.{k}": v
            for k, v in event.dict(
                exclude=set(
                    replaced_by_detail_type
                    + should_be_str
                    + should_be_str
                    + good_to_be_ob12
                    + ("self_id", "post_type")
                )
            ).items()
        }
        event_dict.update(event.dict(include=set(good_to_be_ob12)))
        event_dict.update(
            {k: str(v) for k, v in event.dict(include=set(should_be_str)).items()}
        )
        event_dict["id"] = str(uuid.uuid4())
        event_dict["type"] = event.post_type
        if not isinstance(event, MetaEvent):
            event_dict["self"] = self.get_bot_self().dict()
        if isinstance(event, MessageEvent):
            event_dict["detail_type"] = event.message_type
            event_dict["message"] = self.to_onebot_message(event.message)
            event_dict["alt_message"] = event.raw_message
        elif isinstance(event, NoticeEvent):
            if isinstance(event, FriendRecallNoticeEvent):
                event_dict["detail_type"] = "private_message_delete"
            elif isinstance(event, FriendAddNoticeEvent):
                event_dict["detail_type"] = "friend_increase"
            elif isinstance(event, GroupIncreaseNoticeEvent):
                event_dict["detail_type"] = "group_member_increase"
                if event.sub_type == "approve" or not event.sub_type:
                    event_dict["sub_type"] = "join"
                elif event.sub_type == "invite":
                    event_dict["sub_type"] = "invite"
                else:
                    event_dict["sub_type"] = f"qq.{event.sub_type}"
            elif isinstance(event, GroupDecreaseNoticeEvent):
                event_dict["detail_type"] = "group_member_decrease"
                if event.sub_type == "leave":
                    event_dict["sub_type"] = "leave"
                elif event.sub_type in ("kick", "kick_me"):
                    event_dict["sub_type"] = "kick"
                else:
                    event_dict["sub_type"] = f"qq.{event.sub_type}"
            elif isinstance(event, GroupRecallNoticeEvent):
                event_dict["detail_type"] = "group_message_delete"
                event_dict["sub_type"] = (
                    "recall" if event.user_id == event.operator_id else "delete"
                )
            else:
                event_dict["detail_type"] = f"qq.{event.notice_type}"
        elif isinstance(event, RequestEvent):
            event_dict["detail_type"] = f"qq.{event.request_type}"
        elif isinstance(event, MetaEvent):
            event_dict["type"] = "meta"
            if isinstance(event, HeartbeatMetaEvent):
                event_dict["detail_type"] = "heartbeat"
                event_dict["interval"] = event.interval
            else:
                event_dict["detail_type"] = f"qq.{event.meta_event_type}"
            event_dict["sub_type"] = getattr(event, "sub_type", "")
        event_dict.setdefault("sub_type", "")
        if event_out := OneBotAdapter.json_to_event(event_dict, "qq"):
            return event_out
        raise NotImplementedError

    def from_onebot_message(self, message: OneBotMessage) -> Message:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(MessageSegment.text(segment.data["text"]))
            elif segment.type == "mention":
                message_list.append(MessageSegment.at(segment.data["qq"]))
            elif segment.type == "image":
                message_list.append(MessageSegment.image(segment.data["file"]))
        return Message(message_list)

    def to_onebot_message(self, message: Message) -> OneBotMessage:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "at":
                message_list.append(OneBotMessageSegment.mention(segment.data["qq"]))
            elif segment.type == "image":
                message_list.append(OneBotMessageSegment.image(segment.data["file"]))
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
        message: Message,
        **kwargs: Any,
    ) -> Dict[Union[Literal["message_id", "time"], str], Any]:
        if group_id:
            result = await self.bot.send_msg(group_id=int(group_id), message=message)
        elif user_id:
            result = await self.bot.send_msg(user_id=int(user_id), message=message)
        return {"message_id": result["message_id"], "time": time.time()}  # type:ignore

    async def delete_message(self, *, message_id: str, **kwargs: Any) -> None:
        raise NotImplementedError

    async def get_self_info(
        self, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        raise NotImplementedError

    async def get_user_info(
        self, *, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        raise NotImplementedError

    async def get_friend_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        raise NotImplementedError

    async def get_group_info(
        self, *, group_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["group_id", "group_name"], str], str]:
        raise NotImplementedError

    async def get_group_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["group_id", "group_name"], str], str]]:
        raise NotImplementedError

    async def get_group_member_info(
        self, *, group_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        raise NotImplementedError

    async def get_group_member_list(
        self, *, group_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        raise NotImplementedError

    async def set_group_name(
        self, *, group_id: str, group_name: str, **kwargs: Any
    ) -> None:
        raise NotImplementedError

    async def leave_group(self, *, group_id: str, **kwargs: Any) -> None:
        raise NotImplementedError

    async def get_guild_info(
        self, *, guild_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["guild_id", "guild_name"], str], str]:
        raise NotImplementedError

    async def get_guild_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["guild_id", "guild_name"], str], str]]:
        raise NotImplementedError

    async def set_guild_name(
        self, *, guild_id: str, guild_name: str, **kwargs: Any
    ) -> None:
        raise NotImplementedError

    async def get_guild_member_info(
        self, *, guild_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        raise NotImplementedError

    async def get_guild_member_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        raise NotImplementedError

    async def leave_guild(self, *, guild_id: str, **kwargs: Any) -> None:
        raise NotImplementedError

    async def get_channel_info(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["channel_id", "channel_name"], str], str]:
        raise NotImplementedError

    async def get_channel_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["channel_id", "channel_name"], str], str]]:
        raise NotImplementedError

    async def set_channel_name(
        self, *, guild_id: str, channel_id: str, channel_name: str, **kwargs: Any
    ) -> None:
        raise NotImplementedError

    async def upload_file(
        self,
        *,
        type: Union[Literal["url", "path", "data"], str],
        name: str,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        path: Optional[str] = None,
        data: Optional[bytes] = None,
        sha256: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[Union[Literal["file_id"], str], str]:
        raise NotImplementedError

    async def get_file(
        self,
        *,
        type: Union[Literal["url", "path", "data"], str],
        file_id: str,
        **kwargs: Any,
    ) -> Dict[
        Union[Literal["name", "url", "headers", "path", "data", "sha256"], str], str
    ]:
        raise NotImplementedError
