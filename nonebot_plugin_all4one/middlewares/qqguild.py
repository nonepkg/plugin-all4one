from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Union, Literal, Optional

from nonebot import logger
from anyio import open_file
from pydantic import parse_obj_as
from nonebot.adapters.qqguild.api.model import Member
from nonebot.adapters.qqguild.api import MessageReference
import nonebot.adapters.onebot.v12.exception as ob_exception
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.qqguild.exception import ActionFailed, AuditException
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.qqguild.event import GuildMemberAddEvent, GuildMemberRemoveEvent
from nonebot.adapters.qqguild import (
    Bot,
    Event,
    Adapter,
    Message,
    ChannelEvent,
    MessageEvent,
    MessageSegment,
    GuildMemberEvent,
    ChannelCreateEvent,
    ChannelDeleteEvent,
    ChannelUpdateEvent,
    MessageCreateEvent,
    GuildMemberUpdateEvent,
    DirectMessageCreateEvent,
)

from . import supported_action
from . import Middleware as BaseMiddleware
from ..database import get_file, upload_file


class Middleware(BaseMiddleware):
    bot: Bot

    @property
    def self_id(self) -> str:
        """OneBot 12 通过 self_id 来判断是否是 to_me 的消息

        QQ 频道 at 机器人时为 bot.self_info.id，所以需要用这个 id，而不是 bot.self_id
        """
        return str(self.bot.self_info.id)

    @staticmethod
    def _to_ob_message_id(
        *,
        message_id: Optional[str],
        guild_id: Optional[int],
        channel_id: Optional[int],
    ) -> str:
        """转换成 OneBot 消息 id

        由 message_id, guild_id, channel_id 组成
        """
        message = message_id if message_id else ""
        guild = str(guild_id) if guild_id else ""
        channel = str(channel_id) if channel_id else ""
        return f"{message}-{guild}-{channel}"

    @staticmethod
    def _from_ob_message_id(
        message_id: str,
    ) -> Tuple[str, Optional[int], Optional[int]]:
        """从 OneBot 的消息 id 中解析出 message_id, guild_id, channel_id"""
        message, guild, channel = message_id.split("-")
        return message, int(guild) if guild else None, int(channel) if channel else None

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
        event_dict["sub_type"] = ""
        if isinstance(event, MessageEvent):
            event_dict["id"] = event.id
            event_dict["time"] = (
                event.timestamp.timestamp()
                if event.timestamp
                else datetime.now().timestamp()
            )
            event_dict["message_id"] = self._to_ob_message_id(
                message_id=event.id,
                guild_id=event.guild_id,
                channel_id=event.channel_id,
            )
            event_dict["message"] = await self.to_onebot_message(event)
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
        # 频道成员事件
        # https://bot.q.qq.com/wiki/develop/api/gateway/guild_member.html
        elif isinstance(event, GuildMemberEvent):
            # 随便拼了个 id
            event_dict["id"] = f"{event.guild_id}-{event.op_user_id}"
            event_dict["time"] = (
                event.joined_at.timestamp()
                if event.joined_at
                else datetime.now().timestamp()
            )
            event_dict["guild_id"] = event.guild_id
            event_dict["user_id"] = event.get_user_id()
            event_dict["operator_id"] = event.op_user_id
            if isinstance(event, GuildMemberAddEvent):
                event_dict["detail_type"] = "guild_member_increase"
            elif isinstance(event, GuildMemberRemoveEvent):
                event_dict["detail_type"] = "guild_member_decrease"
            elif isinstance(event, GuildMemberUpdateEvent):
                event_dict["detail_type"] = "guild_member_update"
        # 子频道事件
        # https://bot.q.qq.com/wiki/develop/api/gateway/channel.html
        elif isinstance(event, ChannelEvent):
            event_dict["id"] = event.id
            event_dict["time"] = datetime.now().timestamp()
            event_dict["guild_id"] = event.guild_id
            event_dict["operator_id"] = event.op_user_id
            if isinstance(event, ChannelCreateEvent):
                event_dict["detail_type"] = "channel_create"
            elif isinstance(event, ChannelDeleteEvent):
                event_dict["detail_type"] = "channel_delete"
            elif isinstance(event, ChannelUpdateEvent):
                event_dict["detail_type"] = "channel_update"
        else:
            logger.warning(f"未转换事件: {event}")
            return []

        if event_out := OneBotAdapter.json_to_event(
            event_dict, "nonebot-plugin-all4one"
        ):
            return [event_out]
        return []

    async def to_onebot_message(self, event: MessageEvent) -> OneBotMessage:
        message = event.get_message()

        message_list = []
        # 适配器会处理 mention 和 reply 机器人的消息段，转化成 to_me 和 reply
        if event.reply:
            message_list.append(
                OneBotMessageSegment.reply(
                    self._to_ob_message_id(
                        message_id=event.message_reference.message_id,  # type: ignore
                        guild_id=event.guild_id,
                        channel_id=event.channel_id,
                    ),
                    user_id=event.reply.message.author.id,  # type: ignore
                )
            )
        # 如果是私聊默认是 to_me 的，不需要再次 @ 机器人
        if event.to_me and not isinstance(event, DirectMessageCreateEvent):
            message_list.append(OneBotMessageSegment.mention(self.self_id))
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "mention_user":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["user_id"])
                )
            elif segment.type == "attachment":
                url = segment.data["url"]
                http_url = f"https://{url}" if not url.startswith("https") else url
                file_id = await upload_file(
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
            if file.path:
                async with await open_file(Path(file.path), "rb") as f:
                    file_image = await f.read()
        message_reference = None
        if reply := (message["reply"] or None):
            message_id = reply[-1].data["message_id"]
            message_id, _, _ = self._from_ob_message_id(message_id)
            message_reference = MessageReference(message_id=message_id)

        try:
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
            time = result.timestamp.timestamp()  # type: ignore
            message_id = {
                "message_id": result.id,
                "guild_id": result.guild_id,
                "channel_id": result.channel_id,
            }
        except AuditException as e:
            # https://bot.q.qq.com/wiki/develop/api/openapi/message/post_messages.html#%E9%94%99%E8%AF%AF%E7%A0%81
            # NoneBot 的默认 API_TIMEOUT 为 30s，这里设置为 25s
            result = await e.get_audit_result(timeout=25)
            if result.message_id is None:
                raise ob_exception.PlatformError("failed", 34001, "消息审核未通过", None)
            time = result.audit_time.timestamp()  # type: ignore
            message_id = {
                "message_id": result.message_id,
                "guild_id": result.guild_id,
                "channel_id": result.channel_id,
            }
        except ActionFailed as e:
            raise ob_exception.PlatformError("failed", 34001, str(e), None)

        return {
            "message_id": self._to_ob_message_id(**message_id),
            "time": time,
        }

    @supported_action
    async def get_guild_info(
        self, *, guild_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["guild_id", "guild_name"], str], str]:
        guild = await self.bot.get_guild(guild_id=int(guild_id))

        guild_dict = guild.dict()
        guild_dict["guild_id"] = str(guild_dict["id"])
        guild_dict["guild_name"] = guild_dict["name"]
        return guild_dict

    @supported_action
    async def get_guild_list(
        self, **kwargs: Any
    ) -> List[Dict[Union[Literal["guild_id", "guild_name"], str], str]]:
        """获取群列表"""
        guilds = []

        # 有分页，每页 100 个
        # https://bot.q.qq.com/wiki/develop/api/openapi/user/guilds.html#%E5%8F%82%E6%95%B0
        after = None
        while result := await self.bot.guilds(after=after, limit=100):
            guilds.extend(result)
            if len(result) < 100:
                break
            after = str(result[-1].id)

        guilds_list = []
        for guild in guilds:
            guild_dict = guild.dict()
            guild_dict["guild_id"] = str(guild_dict["id"])
            guild_dict["guild_name"] = guild_dict["name"]
            guilds_list.append(guild_dict)
        return guilds_list

    @supported_action
    async def get_guild_member_info(
        self, *, guild_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_member(guild_id=int(guild_id), user_id=int(user_id))

        return {
            "user_id": str(result.user.id),  # type: ignore
            "user_name": result.user.username,  # type: ignore
            "user_displayname": result.nick,  # type: ignore
        }

    async def _get_all_members(self, guild_id: str) -> List[Member]:
        members = []
        # 有分页，每页 400 个
        # https://bot.q.qq.com/wiki/develop/api/openapi/member/get_members.html#%E5%8F%82%E6%95%B0
        after = "0"
        while result := await self.bot.get_members(
            guild_id=int(guild_id), after=after, limit=400
        ):
            members.extend(result)
            if len(result) < 400:
                break
            after = str(result[-1].user.id)  # type: ignore
        return members

    @supported_action
    async def get_guild_member_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[
        Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
        members = await self._get_all_members(guild_id=guild_id)

        members_list = []
        for member in members:
            members_list.append(
                {
                    "user_id": str(member.user.id),  # type: ignore
                    "user_name": member.user.username,  # type: ignore
                    "user_displayname": member.nick,  # type: ignore
                }
            )
        return members_list

    @supported_action
    async def get_channel_info(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["channel_id", "channel_name"], str], str]:
        result = await self.bot.get_channel(channel_id=int(channel_id))

        return {
            "channel_id": str(result.id),
            "channel_name": result.name,  # type: ignore
        }

    @supported_action
    async def get_channel_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["channel_id", "channel_name"], str], str]]:
        result = await self.bot.get_channels(guild_id=int(guild_id))

        channels_list = []
        for channel in result:
            channels_list.append(
                {
                    "channel_id": str(channel.id),
                    "channel_name": channel.name,  # type: ignore
                }
            )
        return channels_list

    @supported_action
    async def set_channel_name(
        self, *, guild_id: str, channel_id: str, channel_name: str, **kwargs: Any
    ) -> None:
        await self.bot.patch_channel(channel_id=int(channel_id), name=channel_name)

    @supported_action
    async def get_channel_member_info(
        self, *, guild_id: str, channel_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        result = await self.bot.get_member(guild_id=int(guild_id), user_id=int(user_id))

        return {
            "user_id": str(result.user.id),  # type: ignore
            "user_name": result.user.username,  # type: ignore
            "user_displayname": result.nick,  # type: ignore
        }

    @supported_action
    async def get_channel_member_list(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> List[
        Dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
        """返回可以查看该频道的用户列表"""
        guild_members = await self._get_all_members(guild_id=guild_id)

        channel = await self.bot.get_channel(channel_id=int(channel_id))
        # https://bot.q.qq.com/wiki/develop/api/openapi/channel/model.html#privatetype
        if channel.private_type == 0:
            # 如果是公开频道则直接返回所有成员
            view_members = guild_members
        else:
            # FIXME: 如果子频道里有指定成员可见，无法显示那些成员。
            roles = await self.bot.get_guild_roles(guild_id=int(guild_id))

            view_roles = []
            for role in roles.roles:  # type: ignore
                # https://bot.q.qq.com/wiki/develop/api/openapi/channel_permissions/model.html#permissions
                try:
                    resp = await self.bot.get_channel_roles_permissions(
                        channel_id=int(channel_id), role_id=role.id  # type: ignore
                    )
                except ActionFailed as e:
                    # 需要将机器人设置为管理员，可能没有权限
                    raise ob_exception.PlatformError(
                        "failed", 34001, e.message or "", None
                    )
                permission = int(resp.permissions or 0)
                if permission & 1:
                    view_roles.append(role.id)

            def can_view(member: Member) -> bool:
                for role in member.roles or []:
                    if role in view_roles:
                        return True
                return False

            view_members = [member for member in guild_members if can_view(member)]

        members_list = []
        for member in view_members:
            members_list.append(
                {
                    "user_id": str(member.user.id),  # type: ignore
                    "user_name": member.user.username,  # type: ignore
                    "user_displayname": member.nick,  # type: ignore
                }
            )
        return members_list

    @supported_action
    async def delete_message(self, *, message_id: str, **kwargs: Any) -> None:
        message, _, channel = self._from_ob_message_id(message_id)
        if channel is None or message is None:
            raise ob_exception.BadParam("failed", 10003, "消息 ID 缺少需要的部分", None)
        try:
            await self.bot.delete_message(
                channel_id=channel, message_id=message, **kwargs
            )
        except ActionFailed as e:
            raise ob_exception.PlatformError("failed", 34001, e.message or "", None)
