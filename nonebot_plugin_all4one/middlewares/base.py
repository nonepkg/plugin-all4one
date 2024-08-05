from abc import ABC, abstractmethod
from typing import Any, Union, Literal, Optional

from anyio import open_file
from nonebot.adapters import Bot, Event, Message
from nonebot.adapters.onebot.v12.event import BotSelf
from nonebot.adapters.onebot.v12 import UnsupportedAction
from nonebot.adapters.onebot.v12.exception import BadParam
from nonebot.adapters.onebot.v12 import Event as OneBotEvent

from ..database import get_file, upload_file


def supported_action(func):
    """标记支持的动作"""
    func.__supported__ = True
    return func


class Middleware(ABC):
    def __init__(self, bot: Bot):
        self.bot = bot
        self._supported_actions = self._get_supported_actions()

    def _get_supported_actions(self) -> list[str]:
        """获取支持的动作列表"""
        supported_actions = set()
        for class_ in self.__class__.__mro__:
            for name, attr in class_.__dict__.items():
                if not name.startswith("_") and getattr(attr, "__supported__", False):
                    supported_actions.add(name)
        return list(supported_actions)

    @supported_action
    async def get_supported_actions(self, **kwargs: Any) -> list[str]:
        """获取支持的动作列表

        参数:
            kwargs: 扩展字段
        """
        return self._supported_actions

    async def _call_api(self, api: str, **kwargs: Any) -> Any:
        if api not in self._supported_actions:
            raise UnsupportedAction(
                status="failed",
                retcode=10002,
                data={},
                message=f"不支持动作请求 {api}",
            )
        return await getattr(self, api)(**kwargs)

    @property
    def self_id(self) -> str:
        return self.bot.self_id

    def get_bot_self(self) -> BotSelf:
        return BotSelf(
            platform=self.get_platform(),
            user_id=self.self_id,
        )

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """对应协议适配器的名称"""
        raise NotImplementedError

    @abstractmethod
    def get_platform(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def to_onebot_event(self, event: Event) -> list[OneBotEvent]:
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
    ) -> dict[Union[Literal["message_id", "time"], str], Any]:
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
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        """获取机器人自身信息"""
        raise NotImplementedError

    async def get_user_info(self, *, user_id: str, **kwargs: Any) -> dict[
        Union[Literal["user_id", "user_name", "user_displayname", "user_remark"], str],
        str,
    ]:
        """获取用户信息

        参数:
            user_id: 用户 ID，可以是好友，也可以是陌生人
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_friend_list(
        self,
        **kwargs: Any,
    ) -> list[
        dict[
            Union[
                Literal["user_id", "user_name", "user_displayname", "user_remark"], str
            ],
            str,
        ]
    ]:
        """获取好友列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_info(
        self, *, group_id: str, **kwargs: Any
    ) -> dict[Union[Literal["group_id", "group_name"], str], str]:
        """获取群信息

        参数:
            group_id: 群 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_list(
        self,
        **kwargs: Any,
    ) -> list[dict[Union[Literal["group_id", "group_name"], str], str]]:
        """获取群列表

        参数:
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_member_info(
        self, *, group_id: str, user_id: str, **kwargs: Any
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        """获取群成员信息

        参数:
            group_id: 群 ID
            user_id: 用户 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_group_member_list(
        self, *, group_id: str, **kwargs: Any
    ) -> list[
        dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
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
    ) -> dict[Union[Literal["guild_id", "guild_name"], str], str]:
        """获取 Guild 信息

        参数:
            guild_id: 群组 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_list(
        self,
        **kwargs: Any,
    ) -> list[dict[Union[Literal["guild_id", "guild_name"], str], str]]:
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
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        """获取群组成员信息

        参数:
            guild_id: 群组 ID
            user_id: 用户 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_guild_member_list(
        self, *, guild_id: str, **kwargs: Any
    ) -> list[
        dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
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
    ) -> dict[Union[Literal["channel_id", "channel_name"], str], str]:
        """获取频道信息

        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_channel_list(
        self, *, guild_id: str, joined_only: bool = False, **kwargs: Any
    ) -> list[dict[Union[Literal["channel_id", "channel_name"], str], str]]:
        """获取频道列表

        参数:
            guild_id: 群组 ID
            joined_only: 只获取机器人账号已加入的频道列表
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

    async def get_channel_member_info(
        self, *, guild_id: str, channel_id: str, user_id: str, **kwargs: Any
    ) -> dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]:
        """获取频道成员信息
        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            user_id: 用户 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def get_channel_member_list(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> list[
        dict[Union[Literal["user_id", "user_name", "user_displayname"], str], str]
    ]:
        """获取频道成员列表
        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    async def leave_channel(
        self, *, guild_id: str, channel_id: str, **kwargs: Any
    ) -> None:
        """退出频道
        参数:
            guild_id: 群组 ID
            channel_id: 频道 ID
            kwargs: 扩展字段
        """
        raise NotImplementedError

    @supported_action
    async def upload_file(
        self,
        *,
        type: Union[Literal["url", "path", "data"], str],
        name: str,
        url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        path: Optional[str] = None,
        data: Optional[bytes] = None,
        sha256: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[Union[Literal["file_id"], str], str]:
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
        if type == "url":
            if url is None:
                raise BadParam(
                    status="failed",
                    retcode=10003,
                    message="url must be provided when type is url",
                    data={},
                )
        elif type == "path":
            if path is None:
                raise BadParam(
                    status="failed",
                    retcode=10003,
                    message="path must be provided when type is path",
                    data={},
                )
        elif type == "data":
            if data is None:
                raise BadParam(
                    status="failed",
                    retcode=10003,
                    message="data must be provided when type is data",
                    data={},
                )
        else:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="type must be url, path or data",
                data={},
            )
        return {
            "file_id": await upload_file(
                name=name,
                url=url,
                headers=headers,
                path=path,
                data=data,
                sha256=sha256,
            )
        }

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
    ) -> Optional[dict[Union[Literal["file_id"], str], str]]:
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

    @supported_action
    async def get_file(
        self,
        *,
        type: Union[Literal["url", "path", "data"], str],
        file_id: str,
        **kwargs: Any,
    ) -> dict[
        Union[Literal["name", "url", "headers", "path", "data", "sha256"], str], Any
    ]:
        """获取文件

        参数:
            type: 获取文件的方式，可以为 url、path、data 或扩展的方式
            file_id: 文件 ID
            kwargs: 扩展字段
        """
        file = await get_file(file_id=file_id)
        if type == "url":
            result = {"url": file.url, "headers": file.headers}
        elif type == "path":
            result = {"path": file.path}
        elif type == "data" and file.path:
            async with await open_file(file.path, "rb") as f:
                result = {"data": await f.read()}
        else:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="type must be url, path or data",
                data={},
            )
        return {"name": file.name, "sha256": file.sha256, **result}

    async def get_file_fragmented(
        self,
        *,
        stage: Literal["prepare", "transfer"],
        file_id: str,
        offset: Optional[int] = None,
        size: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[Union[Literal["name", "total_size", "sha256", "data"], str], str]:
        """分片获取文件

        参数:
            stage: 获取阶段
            file_id: 文件 ID
            offset: 本次获取的文件偏移，单位：字节
            size: 本次获取的文件大小，单位：字节
            kwargs: 扩展字段
        """
        raise NotImplementedError
