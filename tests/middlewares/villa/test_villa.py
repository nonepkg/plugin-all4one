import json
from pathlib import Path

from nonebug import App
from pydantic import parse_obj_as
from nonebot.adapters.villa.config import BotInfo
from nonebot.adapters.villa import Bot, SendMessageEvent
from nonebot.adapters.villa.event import pre_handle_event
from nonebot.adapters.onebot.v12 import ChannelMessageEvent as OB12ChannelMessageEvent

bot_info = BotInfo(
    bot_id="test",
    bot_secret="123",
    pub_key="""-----BEGIN PUBLIC KEY----- MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCuPr64CTkonwYjeLsAuKZ7HmSS 0gvB3p2kP82BFsEwYiDmlNuzV2aCu/CvfqA9jwGt+lBDzpkb4PyK8tdDNo8RXtUf GJhmY6Qq/Hxn1Zd2AAXeQE6bqyHE0JuM/9APmzfNzVw/UhrNamxXuEM8Xx12NEe8 UpxBHmCQ4dpBlTnVyQIDAQAB -----END PUBLIC KEY-----""",
)


async def test_to_onebot_event(app: App):
    from nonebot_plugin_all4one.middlewares.villa import Middleware

    with (Path(__file__).parent / "events.json").open("r", encoding="utf8") as f:
        test_events = json.load(f)

    message_event = parse_obj_as(SendMessageEvent, pre_handle_event(test_events[0]))

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, bot_info=bot_info)
        middleware = Middleware(bot)

        channel_create = (await middleware.to_onebot_event(message_event))[0]
        assert isinstance(channel_create, OB12ChannelMessageEvent)
        assert channel_create.message_id == "C9G5-O2GK-FJB9-EVB0"
        assert channel_create.channel_id == "39761"
        assert (
            channel_create.alt_message
            == "MentionedRobot(bot_id='bot_nUcp9kz0I2AhxZGVQDUQ', bot_name='琪露诺')/帮助"
        )
