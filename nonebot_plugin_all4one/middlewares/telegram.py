from pathlib import Path
from typing import Any, Dict, List, Union, Literal, Optional

from pydantic import parse_obj_as
from nonebot.adapters.onebot.v12 import UnsupportedSegment
from nonebot.adapters.telegram.message import File, Entity
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.telegram import Bot, Event, Adapter, Message
from nonebot.adapters.telegram.model import Message as TelegramMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.telegram.event import (
    Chat,
    NoticeEvent,
    MessageEvent,
    ChannelPostEvent,
    GroupMessageEvent,
    NewChatMemberEvent,
    LeftChatMemberEvent,
    PrivateMessageEvent,
    ForumTopicMessageEvent,
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
        return "telegram"

    async def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
        event_dict = {}
        event_dict["id"] = str(event.telegram_model.update_id)
        if (type := event.get_type()) not in ["message", "notice", "request"]:
            return []
        event_dict["type"] = type
        event_dict["self"] = self.get_bot_self().dict()
        if isinstance(event, MessageEvent):
            event_dict["time"] = event.date
            event_dict["detail_type"] = event.get_event_name().split(".")[1]
            event_dict["sub_type"] = ""
            event_dict["message_id"] = f"{event.chat.id}/{event.message_id}"
            event_dict["message"] = await self.to_onebot_message(event.message)
            event_dict["alt_message"] = str(event.message)
            if isinstance(event, PrivateMessageEvent):
                event_dict["user_id"] = event.get_user_id()
            elif isinstance(event, ForumTopicMessageEvent):
                event_dict["detail_type"] = "channel"
                event_dict["guild_id"] = str(event.chat.id)
                event_dict["channel_id"] = str(event.message_thread_id)
                event_dict["user_id"] = event.get_user_id()
            elif isinstance(event, GroupMessageEvent):
                event_dict["group_id"] = str(event.chat.id)
                event_dict["user_id"] = event.get_user_id()
            if isinstance(event.reply_to_message, MessageEvent):
                event_dict["message"].insert(
                    0,
                    OneBotMessageSegment.reply(
                        f"{event.reply_to_message.chat.id}/{event.reply_to_message.message_id}",
                        user_id=event.reply_to_message.get_user_id()
                        if not isinstance(event.reply_to_message, ChannelPostEvent)
                        else "",
                    ),
                )
        elif isinstance(event, NoticeEvent):
            if isinstance(event, NewChatMemberEvent):
                event_dict["time"] = event.date
                event_dict["detail_type"] = "group_member_increase"
                event_dict["sub_type"] = "join"
                event_dict["group_id"] = str(event.chat.id)
                event_dict["operator_id"] = str(event.from_.id) if event.from_ else ""
                event_list = []
                for user in event.new_chat_members:
                    event_dict["user_id"] = user.id
                    if event_out := OneBotAdapter.json_to_event(
                        event_dict, "nonebot-plugin-all4one"
                    ):
                        event_list.append(event_out)
                return event_list
            if isinstance(event, LeftChatMemberEvent):
                event_dict["time"] = event.date
                event_dict["detail_type"] = "group_member_decrease"
                event_dict["sub_type"] = "leave"
                event_dict["group_id"] = str(event.chat.id)
                event_dict["user_id"] = event.left_chat_member.id
                event_dict["operator_id"] = str(event.from_.id) if event.from_ else ""
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
            elif segment.type == "mention":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["text"][1:])
                )
            elif isinstance(segment, Entity):
                message_list.append(OneBotMessageSegment.text(str(segment)))
            elif segment.type == "photo":
                message_list.append(OneBotMessageSegment.image(segment.data["file"]))
            elif segment.type in ("voice", "audio", "video"):
                message_list.append(
                    OneBotMessageSegment(
                        segment.type, {"file_id": segment.data["file"]}
                    )
                )
            elif segment.type == "document":
                message_list.append(OneBotMessageSegment.file(segment.data["file"]))
        for segment in message_list:
            if segment.type in ("image", "voice", "audio", "video", "file"):
                file = await self.bot.get_file(segment.data["file_id"])
                if file.file_path is None:
                    continue
                segment.data["file_id"] = await upload_file(
                    Path(file.file_path).name,
                    self.get_platform(),
                    file.file_id,
                    url=f"https://api.telegram.org/file/bot{self.bot.bot_config.token}/{file.file_path}",
                )
        return OneBotMessage(message_list)

    async def send(
        self,
        chat_id: int,
        message: Message,
        message_thread_id: Optional[int] = None,
        **kwargs,
    ) -> Union[TelegramMessage, List[TelegramMessage]]:
        class FakeEvent(Event):
            chat: Chat

        fake_event = FakeEvent(
            **{
                "chat": Chat(id=chat_id, type="private"),
                "message_thread_id": message_thread_id,
            }
        )

        return await self.bot.send(fake_event, message, **kwargs)

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
        if detail_type == "group":
            chat_id = group_id
        elif detail_type == "private":
            chat_id = user_id
        else:
            chat_id = guild_id
        chat_id = str(chat_id)

        message_list = []
        message = parse_obj_as(OneBotMessage, message)
        for segment in message:
            if segment.type == "text":
                message_list.append(Entity.text(segment.data["text"]))
            elif segment.type == "mention":
                user = await self.bot.get_chat_member(chat_id, segment.data["user_id"])
                user_name = user.user.username or user.user.first_name
                message_list.append(
                    Entity.text_mention(f"@{user_name}", segment.data["user_id"])
                )
            elif segment.type == "mention_all":
                raise UnsupportedSegment("failed", 10005, "不支持的消息段类型", {})
            elif segment.type == "image":
                message_list.append(File.photo(segment.data["file_id"]))
            elif segment.type in ("voice", "audio", "video"):
                message_list.append(
                    File(segment.type, {"file": segment.data["file_id"]})
                )
            elif segment.type == "file":
                message_list.append(File.document(segment.data["file_id"]))
        for segment in message_list:
            if isinstance(segment, File):
                file = await get_file(segment.data["file"], self.get_platform())
                if file.src_id:
                    segment.data["file"] = file.src_id
                else:
                    segment.data["file"] = file.path
        telegram_message = Message(message_list)

        reply_to_message_id = None
        if message.count("reply"):
            reply_to_message_id = int(
                message["reply", 0].data["message_id"].split("/")[1]
            )

        result = await self.send(
            int(chat_id),
            telegram_message,
            message_thread_id=int(channel_id) if channel_id else None,
            reply_to_message_id=reply_to_message_id,
            **kwargs,
        )
        if isinstance(result, list):
            result = result[0]
        return {"message_id": str(result.message_id), "time": result.date}

    @supported_action
    async def delete_message(self, *, message_id: str, **kwargs: Any) -> None:
        await self.bot.delete_message(*map(int, message_id.split("/")))

    @supported_action
    async def get_self_info(
        self, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_me()
        return {
            "user_id": str(result.id),
            "user_name": result.username,  # type: ignore
            "user_displayname": result.first_name,
        }

    @supported_action
    async def get_user_info(
        self, *, user_id: str, **kwargs: Any
    ) -> Dict[
        Union[Literal["user_id", "user_name", "user_displayname", "user_remark"], str],
        str,
    ]:
        result = await self.bot.get_chat(int(user_id))
        return {
            "user_id": str(result.id),
            "user_name": result.username if result.username else "",
            "user_displayname": result.first_name,  # type: ignore
            "user_remark": "",
        }

    @supported_action
    async def get_group_info(
        self, *, group_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["group_id", "group_name"], str], str]:
        result = await self.bot.get_chat(int(group_id))
        return {"group_id": str(result.id), "group_name": result.title}  # type: ignore

    @supported_action
    async def get_group_member_info(
        self, *, group_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_chat_member(int(group_id), int(user_id))
        return {
            "user_id": str(result.user.id),
            "user_name": result.user.username if result.user.username else "",
            "user_displayname": result.user.first_name,
        }

    @supported_action
    async def set_group_name(
        self, *, group_id: str, group_name: str, **kwargs: Any
    ) -> None:
        await self.bot.set_chat_title(int(group_id), group_name)

    @supported_action
    async def leave_group(self, *, group_id: str, **kwargs: Any) -> None:
        await self.bot.leave_chat(int(group_id))

    @supported_action
    async def get_guild_info(
        self, *, guild_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["guild_id", "guild_name"], str], str]:
        result = await self.bot.get_chat(int(guild_id))
        return {"guild_id": str(result.id), "guild_id": result.title}  # type: ignore

    @supported_action
    async def set_guild_name(
        self, *, guild_id: str, guild_name: str, **kwargs: Any
    ) -> None:
        await self.bot.set_chat_title(int(guild_id), guild_name)

    @supported_action
    async def get_guild_member_info(
        self, *, guild_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_chat_member(int(guild_id), int(user_id))
        return {
            "user_id": str(result.user.id),
            "user_name": result.user.username if result.user.username else "",
            "user_displayname": result.user.first_name,
        }

    @supported_action
    async def leave_guild(self, *, guild_id: str, **kwargs: Any) -> None:
        await self.bot.leave_chat(int(guild_id))

    @supported_action
    async def set_channel_name(
        self, *, guild_id: str, channel_id: str, channel_name: str, **kwargs: Any
    ) -> None:
        await self.bot.edit_forum_topic(int(guild_id), int(channel_id), channel_name)

    @supported_action
    async def get_channel_member_info(
        self, *, guild_id: str, channel_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_chat_member(int(guild_id), int(user_id))
        return {
            "user_id": str(result.user.id),
            "user_name": result.user.username if result.user.username else "",
            "user_displayname": result.user.first_name,
        }
