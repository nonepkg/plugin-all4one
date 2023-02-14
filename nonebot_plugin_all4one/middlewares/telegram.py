from typing import Any, Dict, List, Union, Literal, Optional

from pydantic import parse_obj_as
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


class Middleware(BaseMiddleware):
    bot: Bot

    @staticmethod
    def get_name():
        return Adapter.get_name()

    def get_platform(self):
        return "telegram"

    def to_onebot_event(self, event: Event) -> List[OneBotEvent]:
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
            event_dict["message_id"] = str(event.message_id)
            event_dict["message"] = self.to_onebot_message(event.message)
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
                        str(event.reply_to_message.message_id),
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
                    if event_out := OneBotAdapter.json_to_event(event_dict, "telegram"):
                        event_list.append(event_out)
                return event_list
            if isinstance(event, LeftChatMemberEvent):
                event_dict["time"] = event.date
                event_dict["detail_type"] = "group_member_decrease"
                event_dict["sub_type"] = "leave"
                event_dict["group_id"] = str(event.chat.id)
                event_dict["user_id"] = event.left_chat_member.id
                event_dict["operator_id"] = str(event.from_.id) if event.from_ else ""
        if event_out := OneBotAdapter.json_to_event(event_dict, "telegram"):
            return [event_out]
        raise NotImplementedError

    def to_onebot_message(self, message: Message) -> OneBotMessage:
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
                pass  # TODO Should raise an error
            elif segment.type in ("image", "voice", "audio", "video"):
                message_list.append(
                    File(segment.type, {"file": segment.data["file_id"]})
                )
            elif segment.type == "file":
                message_list.append(File.document(segment.data["file_id"]))
        telegram_message = Message(message_list)

        reply_to_message_id = None
        if message.count("reply"):
            reply_to_message_id = int(message["reply", 0].data["message_id"])

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
