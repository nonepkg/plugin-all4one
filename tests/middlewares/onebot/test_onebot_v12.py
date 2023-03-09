from nonebug import App
from nonebot.adapters.onebot.v12 import Bot


async def test_get_supported_action(app: App):
    from nonebot_plugin_all4one.middlewares.onebot.v12 import Middleware

    async with app.test_api() as ctx:
        bot = ctx.create_bot(base=Bot, impl="test", platform="test")
        middleware = Middleware(bot)
        ctx.should_call_api("get_supported_actions", {}, [])
        supported_actions = await middleware.get_supported_actions()
        assert set(supported_actions) == {
            "upload_file",
            "get_file",
            "get_supported_actions",
            "send_message",
        }
