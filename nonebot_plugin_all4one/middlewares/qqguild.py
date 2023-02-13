from pathlib import Path
from base64 import b64decode
from datetime import datetime
from typing import Any, Dict, List, Union, Literal, Optional

from pydantic import parse_obj_as
from nonebot.drivers import Request, ForwardDriver
import nonebot.adapters.onebot.v12.exception as ob_exception
from nonebot.adapters.onebot.v12 import Event as OneBotEvent
from nonebot.adapters.onebot.v12 import Adapter as OneBotAdapter
from nonebot.adapters.onebot.v12 import Message as OneBotMessage
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment
from nonebot.adapters.qqguild import (
    Bot,
    Event,
    Message,
    MessageEvent,
    MessageSegment,
    MessageCreateEvent,
    DirectMessageCreateEvent,
)

from . import supported_action
from . import Middleware as BaseMiddleware

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "qqguild"
DATA_PATH.mkdir(parents=True, exist_ok=True)


class Middleware(BaseMiddleware):
    bot: Bot

    def get_platform(self):
        return "qqguild"

    def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
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
            event_dict["message"] = self.to_onebot_message(event.get_message())
            event_dict["alt_message"] = str(event.get_message())
            if isinstance(event, DirectMessageCreateEvent):
                event_dict["detail_type"] = "private"
                event_dict["user_id"] = event.get_user_id()
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

    def to_onebot_message(self, message: Message) -> OneBotMessage:
        message_list = []
        for segment in message:
            if segment.type == "text":
                message_list.append(OneBotMessageSegment.text(segment.data["text"]))
            elif segment.type == "mention_user":
                message_list.append(
                    OneBotMessageSegment.mention(segment.data["user_id"])
                )
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
        if detail_type != "channel":
            raise NotImplementedError

        message_list = []
        message = parse_obj_as(OneBotMessage, message)
        for segment in message:
            if segment.type == "text":
                message_list.append(MessageSegment.text(segment.data["text"]))
            elif segment.type == "mention":
                message_list.append(
                    MessageSegment.mention_user(int(segment.data["user_id"]))
                )
        qqguild_message = Message(message_list)
        content = qqguild_message.extract_content() or None

        if file_image := (message["image"] or None):
            with open(DATA_PATH / file_image[-1].data["file_id"], "rb") as f:
                file_image = f.read()

        try:
            result = await self.bot.post_messages(
                channel_id=int(channel_id),  # type: ignore
                content=content,
                msg_id=kwargs.get("event_id"),
                file_image=file_image,  # type: ignore
            )
        except Exception as e:
            raise e
        # FIXME: 如果是主动消息，返回的时间会是 None
        # 暂时不清楚原因，先用当前时间代替
        time = (
            result.timestamp.timestamp()
            if result.timestamp
            else datetime.now().timestamp()
        )
        return {"message_id": str(result.id), "time": time}

    @supported_action
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
        if type == "url":
            if not url:
                raise ob_exception.BadParam("failed", 10003, "url 不能为空", None)
            driver = self.bot.adapter.driver
            if not isinstance(driver, ForwardDriver):
                raise NotImplementedError
            result = await driver.request(Request("GET", url, headers=headers))
            if result.status_code != 200:
                raise ob_exception.ExecutionError("failed", 33001, "文件下载失败", None)
            data = result.content  # type: ignore
        elif type == "path":
            if not path:
                raise ob_exception.BadParam("failed", 10003, "path 不能为空", None)
            with open(path, "rb") as f:
                data = f.read()
        elif type == "data":
            if not data:
                raise ob_exception.BadParam("failed", 10003, "data 不能为空", None)
            if isinstance(data, str):
                data = b64decode(data)
        else:
            raise ob_exception.BadParam("failed", 10003, "不支持的类型", None)

        if not data:
            raise ob_exception.ExecutionError("failed", 35001, "文件为空", None)

        with open(DATA_PATH / name, "wb") as f:
            f.write(data)
        return {"file_id": name}
