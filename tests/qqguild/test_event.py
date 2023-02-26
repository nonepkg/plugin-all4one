import json
from pathlib import Path

from nonebug import App
from nonebot.adapters.qqguild.api import User
from nonebot.adapters.qqguild.config import BotInfo
from nonebot.adapters.onebot.v12 import ChannelMessageEvent
from nonebot.adapters.qqguild import Bot, MessageCreateEvent

bot_info = BotInfo(id="333333", token="token", secret="secret")


async def test_to_onebot_event(app: App):
    from nonebot_plugin_all4one.middlewares.qqguild import Middleware

    with (Path(__file__).parent / "events.json").open("r", encoding="utf8") as f:
        test_events = json.load(f)

    event = MessageCreateEvent.parse_obj(test_events[0])

    async with app.test_api() as ctx:
        bot = ctx.create_bot(
            base=Bot, self_id=bot_info.id, auto_connect=False, bot_info=bot_info
        )
        bot._self_info = User(id=333333, username="bot")  # type: ignore
        middleware = Middleware(bot)
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], ChannelMessageEvent)
