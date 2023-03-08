import uuid
from datetime import datetime
from typing import Any, Dict, List, Union, Literal, Optional

from anyio import open_file
from httpx import AsyncClient
from pydantic import parse_obj_as
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.adapters.onebot.v12 import ActionFailedWithRetcode
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.onebot.v11 import Bot, Event, Adapter, Message, ActionFailed
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

from .. import supported_action
from .. import Middleware as BaseMiddleware
from ...database import get_file, upload_file


class Middleware(BaseMiddleware):
    bot: Bot

    async def _call_api(self, api: str, **kwargs: Any) -> Any:
        try:
            return await super()._call_api(api, **kwargs)
        except ActionFailed as e:
            raise ActionFailedWithRetcode(
                status="failed",
                retcode=int(e.info["retcode"]),
                message=e.info["msg"],
                data={},
            )

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "qq"

    async def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
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
        good_to_be_ob12 = ("time", "sub_type")
        event_dict = {
            f"qq.{k}": v
            for k, v in event.dict(
                exclude=set(
                    replaced_by_detail_type
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
        event_dict["id"] = uuid.uuid4().hex
        event_dict["type"] = event.post_type
        if not isinstance(event, MetaEvent):
            event_dict["self"] = self.get_bot_self().dict()
        if isinstance(event, MessageEvent):
            event_dict["detail_type"] = event.message_type
            event_dict["message"] = await self.to_onebot_message(event.original_message)
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
        if event_out := OneBotAdapter.json_to_event(
            event_dict, "nonebot-plugin-all4one"
        ):
            return [event_out]
        return []

    async def to_onebot_message(self, message: Message) -> OneBotMessage:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "at":
                qq = segment.data["qq"]
                if qq == "all":
                    message_list.append(OneBotMessageSegment.mention_all())
                    continue
                message_list.append(OneBotMessageSegment.mention(qq))
            elif segment.type == "image":
                file = await self.bot.get_image(file=segment.data["file"])
                async with AsyncClient() as client:
                    message_list.append(
                        OneBotMessageSegment.image(
                            await upload_file(
                                file["filename"],
                                self.get_name(),
                                segment.data["file"],
                                data=(await client.get(file["url"])).content,
                            )
                        )
                    )
            elif segment.type in ("video", "record"):
                message_list.append(
                    OneBotMessageSegment(
                        "video" if segment.type == "video" else "voice",
                        {
                            "file": await upload_file(
                                "",
                                self.get_name(),
                                segment.data["file"],
                            )
                        },
                    )
                )
            elif segment.type == "reply":
                message_list.append(
                    OneBotMessageSegment.reply(
                        segment.data["id"], user_id=message["at", 0].data["qq"]
                    )
                )
        return OneBotMessage(message_list)

    async def from_onebot_message(self, message: OneBotMessage) -> Message:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(MessageSegment.text(segment.data["text"]))
            elif segment.type == "mention":
                message_list.append(MessageSegment.at(segment.data["user_id"]))
            elif segment.type == "mention_all":
                message_list.append(MessageSegment.at("all"))
            elif segment.type == "image":
                file = await get_file(segment.data["file_id"], self.get_name())
                if file.src_id:
                    message_list.append(MessageSegment.image(file.src_id))
                elif file.path:
                    async with await open_file(file.path, "rb") as f:
                        data = await f.read()
                    message_list.append(MessageSegment.image(data))
            elif segment.type == "video":
                file = await get_file(segment.data["file_id"], self.get_name())
                if file.src_id:
                    message_list.append(MessageSegment.video(file.src_id))
                elif file.url:
                    message_list.append(MessageSegment.video(file.url))
            elif segment.type == "voice":
                file = await get_file(segment.data["file_id"], self.get_name())
                if file.src_id:
                    message_list.append(MessageSegment.record(file.src_id))
                elif file.path:
                    async with await open_file(file.path, "rb") as f:
                        data = await f.read()
                    message_list.append(MessageSegment.record(data))
            elif segment.type == "reply":
                message_list.append(MessageSegment.reply(segment.data["message_id"]))
        return Message(message_list)

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
        message = parse_obj_as(OneBotMessage, message)
        if group_id:
            result = await self.bot.send_msg(
                group_id=int(group_id), message=await self.from_onebot_message(message)
            )
        elif user_id:
            result = await self.bot.send_msg(
                user_id=int(user_id), message=await self.from_onebot_message(message)
            )
        return {
            "message_id": result["message_id"],  # type: ignore
            "time": int(datetime.now().timestamp()),
        }

    @supported_action
    async def delete_message(self, *, message_id: str, **kwargs: Any) -> None:
        await self.bot.delete_msg(message_id=int(message_id))

    @supported_action
    async def get_self_info(
        self, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        result = await self.bot.get_login_info()
        return {
            "user_id": str(result["user_id"]),
            "user_name": result["nickname"],
            "user_displayname": "",
        }

    @supported_action
    async def get_user_info(
        self, *, user_id: str, no_cache: bool = False, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        result = await self.bot.get_stranger_info(
            user_id=int(user_id), no_cache=no_cache
        )
        resp = {
            "user_id": str(result["user_id"]),
            "user_name": result["nickname"],
            "user_displayname": "",
            "user_remark": "",
        }
        resp.update({f"qq.{k}": v for k, v in result.items() if k not in resp})
        return resp

    @supported_action
    async def get_friend_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        result = await self.bot.get_friend_list()
        resp = []
        for friend in result:
            friend_dict = {
                "user_id": str(friend["user_id"]),
                "user_name": friend["nickname"],
                "user_displayname": "",
                "user_remark": friend["remark"],
            }
            friend_dict.update(
                {f"qq.{k}": v for k, v in friend.items() if k not in friend_dict}
            )
            resp.append(friend_dict)
        return resp

    @supported_action
    async def get_group_info(
        self, *, group_id: str, no_cache: bool = False, **kwargs: Any
    ) -> Dict[Union[Literal["group_id", "group_name"], str], str]:
        result = await self.bot.get_group_info(
            group_id=int(group_id), no_cache=no_cache
        )
        resp = {
            "group_id": str(result["group_id"]),
            "group_name": result["group_name"],
        }
        resp.update({f"qq.{k}": v for k, v in result.items() if k not in resp})
        return resp

    @supported_action
    async def get_group_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["group_id", "group_name"], str], str]]:
        result = await self.bot.get_group_list()
        resp = []
        for group in result:
            group_dict = {
                "group_id": str(group["group_id"]),
                "group_name": group["group_name"],
            }
            group_dict.update(
                {f"qq.{k}": v for k, v in group.items() if k not in group}
            )
            resp.append(group_dict)
        return resp

    @supported_action
    async def get_group_member_info(
        self, *, group_id: str, user_id: str, no_cache: bool = False, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        result = await self.bot.get_group_member_info(
            group_id=int(group_id), user_id=int(user_id), no_cache=no_cache
        )
        resp = {
            "user_id": str(result["user_id"]),
            "user_name": result["nickname"],
            "user_displayname": result["card"],
        }
        resp.update({f"qq.{k}": v for k, v in result.items() if k not in resp})
        return resp

    async def get_group_member_list(
        self, *, group_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        result = await self.bot.get_group_member_list(group_id=int(group_id))
        resp = []
        for member in result:
            tmp = {
                "user_id": str(member["user_id"]),
                "user_name": member["nickname"],
                "user_displayname": member["card"],
            }
            tmp.update({f"qq.{k}": v for k, v in member.items() if k not in tmp})
            resp.append(tmp)
        return resp

    @supported_action
    async def set_group_name(
        self, *, group_id: str, group_name: str, **kwargs: Any
    ) -> None:
        await self.bot.set_group_name(group_id=int(group_id), group_name=group_name)

    @supported_action
    async def leave_group(
        self, *, group_id: str, is_dismiss: bool = False, **kwargs: Any
    ) -> None:
        await self.bot.set_group_leave(group_id=int(group_id), is_dismiss=is_dismiss)
