import asyncio
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Union, Literal, Optional, TypedDict

from nonebot.log import logger
from pydantic import Extra, BaseModel
from nonebot.adapters import Bot, Event, Adapter, Message
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12.event import BotSelf, BotStatus

middlewares_map = {"telegram": "telegram", "console": "console"}

_middlewares: Dict[str, Type["Middleware"]] = {}


def import_middlewares(*adapters):
    for adapter in set(adapter.split(maxsplit=1)[0].lower() for adapter in adapters):
        try:
            if adapter in middlewares_map:
                module = importlib.import_module(
                    f"nonebot_plugin_all4one.middlewares.{middlewares_map[adapter]}"
                )
                _middlewares[adapter] = getattr(module, "Middleware")
            else:
                logger.warning(f"Can not find middleware for Adapter {adapter}")
        except Exception:
            logger.warning(f"Can not find middleware for Adapter {adapter}")


class Middleware(ABC):
    def __init__(self, bot: "Bot"):
        self.bot = bot
        self.events: List[OneBotEvent] = []

    def get_bot_self(self) -> BotSelf:
        return BotSelf(platform=self.get_platform(), user_id=f"a4o@{self.bot.self_id}")

    async def get_latest_events(
        self,
        *,
        limit: int = 0,
        timeout: int = 0,
        **kwargs: Any,
    ) -> List[OneBotEvent]:
        """获取最新事件列表

        参数:
            limit: 获取的事件数量上限，0 表示不限制
            timeout: 没有事件时要等待的秒数，0 表示使用短轮询，不等待
            kwargs: 扩展字段
        """
        if self.events:
            if limit == 0:
                return self.events
            events = self.events[:limit]
            self.events = self.events[limit:]
            return events
        else:
            await asyncio.sleep(timeout)
            return []

    async def get_supported_actions(self, **kwargs: Any) -> List[str]:
        """获取支持的动作列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_status(self, **kwargs: Any) -> BotStatus:
        """获取运行状态

        参数:
            kwargs: 扩展字段
        """
        return BotStatus(
            **{
                "good": True,
                "bots": [
                    {
                        "self": self.get_bot_self(),
                        "online": True,
                    },
                ],
            }
        )

    async def get_version(
        self,
        **kwargs: Any,
    ) -> Dict[Union[Literal["impl", "version", "onebot_version"], str], str]:
        """获取版本信息

        参数:
            kwargs: 扩展字段
        """
        return {
            "impl": "nonebot-plugin-all4one",
            "version": "0.1.0",
            "onebot_version": "12",
        }

    @abstractmethod
    def get_platform(self):
        raise NotImplementedError

    @abstractmethod
    def to_onebot_event(self, event: Event) -> OneBotEvent:
        raise NotImplementedError

    @abstractmethod
    def from_onebot_message(self, message: OneBotMessage) -> Message:
        raise NotImplementedError

    @abstractmethod
    def to_onebot_message(self, message: Message) -> OneBotMessage:
        raise NotImplementedError

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
        """发送消息

        参数:
            detail_type: 发送的类型，可以为 private、group 或扩展的类型，和消息事件的 detail_type 字段对应
            user_id: 用户 ID，当 detail_type 为 private 时必须传入
            group_id: 群 ID，当 detail_type 为 group 时必须传入
            guild_id: Guild 群组 ID，当 detail_type 为 channel 时必须传入
            channel_id: 频道 ID，当 detail_type 为 channel 时必须传入
            message: 消息内容
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def delete_message(self, *, message_id: str, **kwargs: Any) -> None:
        """撤回消息

        参数:
            message_id: 唯一的消息 ID
        """
        raise NotImplementedError

    async def get_self_info(
        self, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        """获取机器人自身信息"""
        raise NotImplementedError

    async def get_user_info(
        self, *, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        """获取用户信息

        参数:
            user_id: 用户 ID，可以是好友，也可以是陌生人
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_friend_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        """获取好友列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_info(
        self, *, group_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["group_id", "group_name"], str], str]:
        """获取群信息

        参数:
            group_id: 群 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["group_id", "group_name"], str], str]]:
        """获取群列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_member_info(
        self, *, group_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        """获取群成员信息

        参数:
            group_id: 群 ID
            user_id: 用户 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_member_list(
        self, *, group_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        """获取群成员列表

        参数:
            group_id: 群 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def set_group_name(
        self, *, group_id: str, group_name: str, **kwargs: Any
    ) -> None:
        """设置群名称

        参数:
            group_id: 群 ID
            group_name: 群名称
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def leave_group(self, *, group_id: str, **kwargs: Any) -> None:
        """退出群

        参数:
            group_id: 群 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_info(
        self, *, guild_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["guild_id", "guild_name"], str], str]:
        """获取 Guild 信息

        参数:
            guild_id: 群组 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_list(
        self,
        **kwargs: Any,
    ) -> List[Dict[Union[Literal["guild_id", "guild_name"], str], str]]:
        """获取群组列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def set_guild_name(
        self, *, guild_id: str, guild_name: str, **kwargs: Any
    ) -> None:
        """设置群组名称

        参数:
            guild_id: 群组 ID
            guild_name: 群组名称
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_member_info(
        self, *, guild_id: str, user_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["user_id", "nickname"], str], str]:
        """获取群组成员信息

        参数:
            guild_id: 群组 ID
            user_id: 用户 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_member_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["user_id", "nickname"], str], str]]:
        """获取群组成员列表

        参数:
            guild_id: 群组 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def leave_guild(self, *, guild_id: str, **kwargs: Any) -> None:
        """退出群组

        参数:
            guild_id: 群组 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_channel_info(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> Dict[Union[Literal["channel_id", "channel_name"], str], str]:
        """获取频道信息

        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_channel_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> List[Dict[Union[Literal["channel_id", "channel_name"], str], str]]:
        """获取频道列表

        参数:
            guild_id: 群组 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def set_channel_name(
        self, *, guild_id: str, channel_id: str, channel_name: str, **kwargs: Any
    ) -> None:
        """设置频道名称

        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            channel_name: 频道名称
            kwargs: 扩展字段
        """
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
        """上传文件

        参数:
            type: 上传文件的方式，可以为 url、path、data 或扩展的方式
            name: 文件名
            url: 文件 URL，当 type 为 url 时必须传入
            headers: 下载 URL 时需要添加的 HTTP 请求头，可选传入
            path: 文件路径，当 type 为 path 时必须传入
            data: 文件数据，当 type 为 data 时必须传入
            sha256: 文件数据（原始二进制）的 SHA256 校验和，全小写，可选传入
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def upload_file_fragmented(
        self,
        stage: Literal["prepare", "transfer", "finish"],
        name: Optional[str] = None,
        total_size: Optional[int] = None,
        sha256: Optional[str] = None,
        file_id: Optional[str] = None,
        offset: Optional[int] = None,
        size: Optional[int] = None,
        data: Optional[bytes] = None,
        **kwargs: Any,
    ) -> Optional[Dict[Union[Literal["file_id"], str], str]]:
        """分片上传文件

        参数:
            stage: 上传阶段
            name: 文件名
            total_size: 文件完整大小
            sha256: 整个文件的 SHA256 校验和，全小写
            file_id: 准备阶段返回的文件 ID
            offset: 本次传输的文件偏移，单位：字节
            size: 本次传输的文件大小，单位：字节
            data: 本次传输的文件数据
            kwargs: 扩展字段
        """
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
        """获取文件

        参数:
            type: 获取文件的方式，可以为 url、path、data 或扩展的方式
            file_id: 文件 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_file_fragmented(
        self,
        *,
        stage: Literal["prepare", "transfer"],
        file_id: str,
        offset: Optional[int] = None,
        size: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[Union[Literal["name", "total_size", "sha256", "data"], str], str]:
        """分片获取文件

        参数:
            stage: 获取阶段
            file_id: 文件 ID
            offset: 本次获取的文件偏移，单位：字节
            size: 本次获取的文件大小，单位：字节
            kwargs: 扩展字段
        """
        raise NotImplementedError
