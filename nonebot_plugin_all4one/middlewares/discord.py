from typing import Any, Union, Literal, Optional

from anyio import open_file
from pydantic import TypeAdapter
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.discord import (
    Bot,
    Event,
    Adapter,
    Message,
    MessageEvent,
    MessageSegment,
    GuildMessageCreateEvent,
    DirectMessageCreateEvent,
)

from .base import supported_action
from ..database import get_file, upload_file
from .base import Middleware as BaseMiddleware


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "discord"

    async def to_onebot_event(self, event: Event) -> list[OneBotEvent]:
        event_dict = {}
        if (type := event.get_type()) not in ["message", "notice", "request"]:
            return []
        event_dict["type"] = type
        event_dict["self"] = (await self.get_bot_self()).model_dump()
        if isinstance(event, MessageEvent):
            event_dict["id"] = str(event.id)
            event_dict["time"] = event.timestamp
            event_dict["sub_type"] = ""
            event_dict["message_id"] = str(event.message_id)
            event_dict["message"] = await self.to_onebot_message(event)
            event_dict["alt_message"] = str(event.original_message)
            event_dict["user_id"] = event.get_user_id()
            if isinstance(event, GuildMessageCreateEvent):
                event_dict["detail_type"] = "channel"
                event_dict["guild_id"] = str(event.guild_id)
                event_dict["channel_id"] = str(event.channel_id)
            elif isinstance(event, DirectMessageCreateEvent):
                event_dict["detail_type"] = "private"
            if event.reply:
                event_dict["message"].insert(
                    0,
                    OneBotMessageSegment.reply(
                        str(event.reply.id), user_id=str(event.reply.author.id)
                    ),
                )

        if event_out := OneBotAdapter.json_to_event(
            event_dict, "nonebot-plugin-all4one"
        ):
            return [event_out]
        return []

    async def get_supported_message_segments(self, **kwargs: Any) -> list[str]:
        return [
            "text",
            "mention",
            "mention_all",
            "image",
            "file",
            "reply",
        ]

    async def to_onebot_message(self, event: MessageEvent) -> OneBotMessage:
        message_list = []
        for segment in event.original_message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "mention_user":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["user_id"])
                )
        for attachment in event.attachments:
            file_id = await upload_file(
                attachment.filename, self.get_name(), attachment.id, url=attachment.url
            )
            if attachment.content_type.startswith("image"):
                message_list.append(OneBotMessageSegment.image(file_id))
            else:
                message_list.append(OneBotMessageSegment.file(file_id))
        if event.original_message.count("mention_everyone"):
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
    ) -> dict[Union[Literal["message_id", "time"], str], Any]:
        if detail_type == "group":
            chat_id = group_id
        elif detail_type == "private" and user_id is not None:
            chat_id = (await self.bot.create_DM(recipient_id=int(user_id))).id
        else:
            chat_id = channel_id
        chat_id = str(chat_id)

        message_list = []
        message = TypeAdapter(OneBotMessage).validate_python(message)
        for segment in message:
            if segment.type == "text":
                message_list.append(MessageSegment.text(segment.data["text"]))
            elif segment.type == "mention":
                message_list.append(
                    MessageSegment.mention_user(int(segment.data["user_id"]))
                )
            elif segment.type == "mention_all":
                message_list.append(MessageSegment.mention_everyone())
            elif segment.type == "reply":
                message_list.append(
                    MessageSegment.reference(int(segment.data["message_id"]))
                )
            elif segment.type in ("image", "file"):
                file = await get_file(segment.data["file_id"], self.get_name())
                if file.path:
                    async with await open_file(file.path, "rb") as f:
                        data = await f.read()
                    message_list.append(
                        MessageSegment.attachment(file.name, content=data)
                    )
        discord_message = Message(message_list)
        result = await self.bot.send_to(int(chat_id), discord_message)
        return {
            "message_id": str(result.id),
            "time": result.timestamp,
        }

    # TODO: OBA 扩展
    # @supported_action
    # async def delete_message(
    #     self, *, channel_id: str, message_id: str, **kwargs: Any
    # ) -> None:
    #     await self.bot.delete_message(
    #         channel_id=int(message_id), message_id=int(message_id)
    #     )

    @supported_action
    async def get_self_info(
        self, **kwargs: Any
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        return {
            "user_id": str(self.bot.self_id),
            "user_name": self.bot.self_info.username,
            "user_displayname": self.bot.self_info.global_name or "",
        }

    @supported_action
    async def get_user_info(self, *, user_id: str, **kwargs: Any) -> dict[
        Union[Literal["user_id", "user_name", "user_displayname", "user_remark"], str],
        str,
    ]:
        result = await self.bot.get_user(user_id=int(user_id))
        return {
            "user_id": str(result.id),
            "user_name": result.username,
            "user_displayname": result.global_name or "",
            "user_remark": "",
        }

    @supported_action
    async def get_guild_info(
        self, *, guild_id: str, **kwargs: Any
    ) -> dict[Union[Literal["guild_id", "guild_name"], str], str]:
        result = await self.bot.get_guild(guild_id=int(guild_id))
        return {"guild_id": str(result.id), "guild_name": result.name}

    @supported_action
    async def set_guild_name(
        self, *, guild_id: str, guild_name: str, **kwargs: Any
    ) -> None:
        await self.bot.modify_guild(guild_id=int(guild_id), name=guild_name)

    @supported_action
    async def get_guild_member_info(
        self, *, guild_id: str, user_id: str, **kwargs: Any
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_guild_member(
            guild_id=int(guild_id), user_id=int(user_id)
        )
        return {
            "user_id": str(result.user.id),
            "user_name": result.user.username,
            "user_displayname": result.nick or result.user.global_name or "",
        }

    @supported_action
    async def get_guild_member_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> list[
        dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
        result = await self.bot.list_guild_members(guild_id=int(guild_id))
        return [
            {
                "user_id": str(member.user.id),
                "user_name": member.user.username,
                "user_displayname": member.nick or member.user.global_name or "",
            }
            for member in result
        ]

    @supported_action
    async def leave_guild(self, *, guild_id: str, **kwargs: Any) -> None:
        await self.bot.leave_guild(guild_id=int(guild_id))

    @supported_action
    async def get_channel_info(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> dict[Union[Literal["channel_id", "channel_name"], str], str]:
        result = await self.bot.get_channel(channel_id=int(channel_id))
        return {"channel_id": str(result.id), "channel_name": result.name or ""}

    @supported_action
    async def get_channel_list(
        self, *, guild_id: str, joined_only: bool = False, **kwargs: Any
    ) -> list[dict[Union[Literal["channel_id", "channel_name"], str], str]]:
        result = await self.bot.get_guild_channels(guild_id=int(guild_id))
        return [
            {"channel_id": str(channel.id), "channel_name": channel.name or ""}
            for channel in result
        ]

    @supported_action
    async def set_channel_name(
        self, *, guild_id: str, channel_id: str, channel_name: str, **kwargs: Any
    ) -> None:
        await self.bot.modify_channel(channel_id=int(channel_id), name=channel_name)

    @supported_action
    async def get_channel_member_info(
        self, *, guild_id: str, channel_id: str, user_id: str, **kwargs: Any
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        # TODO: OBA 扩展更多返回字段
        return await self.get_guild_member_info(guild_id=guild_id, user_id=user_id)

    # TODO: 只能通过检测权限判断是否频道成员
    # async def get_channel_member_list(
    #     self, *, guild_id: str, channel_id: str, **kwargs: Any
    # ) -> list[
    #     dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    # ]:
