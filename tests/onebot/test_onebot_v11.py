import json
from pathlib import Path

from nonebug import App
from nonebot.adapters.onebot.v11 import Bot, Adapter
from nonebot.adapters.onebot.v12 import GroupMessageEvent, PrivateMessageEvent


async def test_to_onebot_event(app: App):
    from nonebot_plugin_all4one.middlewares.onebot.v11 import Middleware

    with (Path(__file__).parent / "events.json").open("r", encoding="utf8") as f:
        test_events = json.load(f)

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, self_id="0")
        middleware = Middleware(bot)

        event = Adapter.json_to_event(test_events[0])
        assert event
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], PrivateMessageEvent)
        assert event[0].message[0].type == "mention_all"

        event = Adapter.json_to_event(test_events[1])
        assert event
        event = await middleware.to_onebot_event(event)
        assert isinstance(event[0], GroupMessageEvent)
        assert event[0].message[0].type == "mention_all"
