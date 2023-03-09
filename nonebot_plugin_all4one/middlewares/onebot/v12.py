from typing import Any, Dict, List, Union, Literal, Optional

from anyio import open_file
from pydantic import parse_obj_as
from nonebot.adapters.onebot.v12.event import MessageEvent
from nonebot.adapters.onebot.v12 import Bot, Event, Adapter, Message

from .. import supported_action
from .. import Middleware as BaseMiddleware
from ...database import get_file, upload_file


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return self.bot.platform

    async def to_onebot_event(self, event: Event) -> List[Event]:
        if isinstance(event, MessageEvent):
            message_list = []
            for segment in event.original_message:
                if segment.type in ("image", "voice", "audio", "video", "file"):
                    file = await self.bot.get_file(
                        type="data", file_id=segment.data["file_id"]
                    )
                    segment.data["file_id"] = await upload_file(
                        file["name"],
                        self.bot.impl,
                        segment.data["file_id"],
                        data=file["data"],
                        sha256=file["sha256"],
                    )
                message_list.append(segment)
            event.message = Message(message_list)
        return [event]

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
        message = parse_obj_as(Message, message)
        message_list = []
        for segment in message:
            if segment.type in ("image", "voice", "audio", "video", "file"):
                file = await get_file(
                    file_id=segment.data["file_id"], src=self.bot.impl
                )
                if file.path and file.sha256:
                    async with await open_file(file.path, "rb") as f:
                        data = await f.read()
                    segment.data["file_id"] = (
                        await self.bot.upload_file(
                            type="data", name=file.name, data=data, sha256=file.sha256
                        )
                    )["file_id"]
            message_list.append(segment)
        if detail_type == "private":
            return await self.bot.send_message(
                detail_type=detail_type,
                user_id=user_id,  # type:ignore
                message=message,
                **kwargs,
            )
        elif detail_type == "group":
            return await self.bot.send_message(
                detail_type=detail_type,
                group_id=group_id,  # type:ignore
                message=message,
                **kwargs,
            )
        elif detail_type == "channel":
            return await self.bot.send_message(
                detail_type=detail_type,
                guild_id=guild_id,  # type:ignore
                channel_id=channel_id,  # type:ignore
                message=message,
                **kwargs,
            )
        return await self.bot.send_message(
            detail_type=detail_type, message=message, **kwargs
        )  # type:ignore

    async def get_supported_actions(self, **kwargs: Any) -> List[str]:
        _ = set()
        _.update(self._supported_actions)
        _.update(await self.bot.get_supported_actions(**kwargs))
        return list(_)

    async def _call_api(self, api: str, **kwargs: Any) -> Any:
        if api in self._supported_actions:
            return await getattr(self, api)(**kwargs)
        return await self.bot.call_api(api, **kwargs)
