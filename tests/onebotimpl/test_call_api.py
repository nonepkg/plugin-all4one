from nonebug import App


async def test_get_latest_event(app: App, FakeMiddleware):
    from nonebot_plugin_all4one import obimpl

    async with app.test_api() as ctx:
        bot = ctx.create_bot()
        middleware = FakeMiddleware(bot)
        queue = middleware.new_queue()
        events = await obimpl.get_latest_events(queue)
        assert events[0].type == "meta"
        assert events[0].detail_type == "status_update"


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
        }
