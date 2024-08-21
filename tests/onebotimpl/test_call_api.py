from nonebug import App


async def test_get_supported_action(app: App, FakeMiddleware):
    from nonebot_plugin_all4one import obimpl

    async with app.test_api() as ctx:
        bot = ctx.create_bot()
        middleware = FakeMiddleware(bot)
        supported_actions = await obimpl.get_supported_actions(middleware)
        assert set(supported_actions) == {
            "upload_file",
            "get_file",
            "get_supported_actions",
            "get_supported_message_segments",
        }
