import json
from pathlib import Path

from nonebug import App
from nonebot.adapters.telegram.model import Chat
from nonebot.adapters.telegram.model import Message
from nonebot.adapters.telegram.config import BotConfig
from nonebot.adapters.telegram.message import File, Entity
from nonebot.adapters.onebot.v12 import PrivateMessageEvent
from nonebot.adapters.telegram import Bot, Event, MessageSegment
from nonebot.adapters.telegram.model import File as TelegramFile
from nonebot.adapters.onebot.v12 import MessageSegment as OneBotMessageSegment

bot_config = BotConfig(token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHI")


async def test_to_onebot_event(app: App):
    from nonebot_plugin_all4one.middlewares.telegram import Middleware

    with (Path(__file__).parent / "updates.json").open("r", encoding="utf8") as f:
        test_updates = json.load(f)

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, self_id=bot_config)  # type:ignore
        middleware = Middleware(bot)

        event = Event.parse_event(test_updates[0])
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)

        event = Event.parse_event(test_updates[3])
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)
        assert event[0].message[0].type == "reply"

        event = Event.parse_event(test_updates[6])
        ctx.should_call_api(
            "get_file",
            {"file_id": "AwADBAADbXXXXXXXXXXXGBdhD2l6_XX"},
            TelegramFile(file_id="AwADBAADbXXXXXXXXXXXGBdhD2l6_XX", file_unique_id=""),
        )
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)
        assert event[0].message[0].type == "audio"

        event = Event.parse_event(test_updates[7])
        ctx.should_call_api(
            "get_file",
            {"file_id": "AwADBAADbXXXXXXXXXXXGBdhD2l6_XX"},
            TelegramFile(file_id="AwADBAADbXXXXXXXXXXXGBdhD2l6_XX", file_unique_id=""),
        )
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)
        assert event[0].message[0].type == "voice"

        event = Event.parse_event(test_updates[8])
        ctx.should_call_api(
            "get_file",
            {"file_id": "AwADBAADbXXXXXXXXXXXGBdhD2l6_XX"},
            TelegramFile(file_id="AwADBAADbXXXXXXXXXXXGBdhD2l6_XX", file_unique_id=""),
        )
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)
        assert event[0].message[0].type == "file"


async def test_send_message(app: App):
    from nonebot_plugin_all4one.database import upload_file
    from nonebot_plugin_all4one.middlewares.telegram import Middleware

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, self_id=bot_config)  # type:ignore
        middleware = Middleware(bot)

        class FakeEvent(Event):
            chat: Chat

        fake_event = FakeEvent(
            **{
                "chat": Chat(id=1111, type="private"),
                "message_thread_id": None,
            }
        )

        file_id = await upload_file(
            name="test",
            data=b"test",
            src=middleware.get_platform(),
            src_id="test",
        )
        ctx.should_call_send(
            fake_event,
            Entity.text("Test") + File.photo("test"),
            Message(message_id=2222, date=1, chat=fake_event.chat),
            reply_to_message_id=None,
        )
        await middleware.send_message(
            detail_type="private",
            user_id="1111",
            message=OneBotMessageSegment.text("Test")
            + OneBotMessageSegment.image(file_id),
        )


async def test_delete_message(app: App):
    from nonebot_plugin_all4one.middlewares.telegram import Middleware

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, self_id=bot_config)  # type:ignore
        middleware = Middleware(bot)
        ctx.should_call_api(
            "delete_message", {"chat_id": 1111, "message_id": 2222}, True
        )
        await middleware.delete_message(message_id="1111/2222")
