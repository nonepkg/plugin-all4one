import json
from pathlib import Path

from nonebug import App
from nonebot.adapters.qqguild.api import User
from nonebot.adapters.qqguild.config import BotInfo
from nonebot.adapters.onebot.v12 import ChannelMessageEvent as OB12ChannelMessageEvent
from nonebot.adapters.onebot.v12 import ChannelCreateEvent as OB12ChannelCreateEvent

from nonebot.adapters.qqguild import Bot, MessageCreateEvent, ChannelCreateEvent

bot_info = BotInfo(id="333333", token="token", secret="secret")


async def test_to_onebot_event(app: App):
    from nonebot_plugin_all4one.middlewares.qqguild import Middleware

    with (Path(__file__).parent / "events.json").open("r", encoding="utf8") as f:
        test_events = json.load(f)

    message_create_event = MessageCreateEvent.parse_obj(test_events[0])
    channel_create_event = ChannelCreateEvent.parse_obj(test_events[1])

    async with app.test_api() as ctx:
        bot = ctx.create_bot(
            base=Bot, self_id=bot_info.id, auto_connect=False, bot_info=bot_info
        )
        bot._self_info = User(id=333333, username="bot")  # type: ignore
        middleware = Middleware(bot)
        message_create_event = await middleware.to_onebot_event(message_create_event)
        assert isinstance(message_create_event[0], OB12ChannelMessageEvent)

        channel_create_event = await middleware.to_onebot_event(channel_create_event)
        assert isinstance(channel_create_event[0], OB12ChannelCreateEvent)
