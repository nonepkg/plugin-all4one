from nonebug import App
from nonebot import get_driver


async def test_bot_connect(app: App, FakeMiddleware):
    from nonebot_plugin_all4one import obimpl

    obimpl.register_middleware(FakeMiddleware)

    async with app.test_api() as ctx:
        bot = ctx.create_bot()
        obimpl.bot_connect(bot)
        assert obimpl.middlewares[bot.self_id].bot == bot
