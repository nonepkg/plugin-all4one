import json
import asyncio
from datetime import datetime
from functools import partial
from typing import Any, Dict

from nonebot.adapters import Bot
from pydantic.json import pydantic_encoder
from nonebot import Driver
from nonebot.drivers import (
    URL,
    Request,
    Response,
    ForwardDriver,
    ReverseDriver,
    HTTPServerSetup,
)

from ..middlewares import Middleware, _middlewares


class OneBotImplementation:
    def __init__(self, driver: Driver, **kwargs: Any):
        self.driver: Driver = driver
        self.middleswares: Dict[str, Middleware] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.setup()

    async def handle_http(self, middleware: Middleware, request: Request) -> Response:
        try:
            if request.content:
                data = json.loads(request.content)
                resp = await getattr(middleware, data["action"])(**data["params"])
                return Response(
                    200,
                    content=json.dumps(
                        {"status": "ok", "retcode": 0, "data": resp, "message": ""}
                    ),
                )
        except Exception as e:
            print(e)
        return Response(200)

    def bot_connect(self, bot: Bot) -> None:
        middleware = _middlewares[bot.type](bot)
        self.middleswares[bot.self_id] = middleware
        if isinstance(self.driver, ReverseDriver):
            self.driver.setup_http_server(
                HTTPServerSetup(
                    URL(f"/obimpl/{bot.self_id}/"),
                    "POST",
                    "OneBotImpl",
                    partial(self.handle_http, middleware),
                )
            )
        if isinstance(self.driver, ForwardDriver):

            async def post(middle: Middleware):
                while True:
                    try:
                        event = middle.events.pop()
                        if event.type == "meta":
                            continue
                        request = Request(
                            "POST",
                            f"http://127.0.0.1:4000/onebot/v12/http/",
                            headers={
                                "Content-Type": "application/json",
                                "User-Agent": "OneBot/12 NoneBot Plugin All4One/0.1.0",
                                "X-OneBot-Version": "12",
                                "X-Impl": "nonebot-plugin-all4one",
                            },
                            content=event.json(
                                encoder=lambda v: v.timestamp()
                                if isinstance(v, datetime)
                                else pydantic_encoder(v)
                            ),
                        )
                        await self.driver.request(request)  # type: ignore
                    except IndexError:
                        pass
                    except Exception as e:
                        print(e)
                    await asyncio.sleep(0.01)

            self.tasks[bot.self_id] = asyncio.create_task(post(middleware))

    def bot_disconnect(self, bot: Bot) -> None:
        self.middleswares.pop(bot.self_id, None)
        task = self.tasks[bot.self_id]
        if not task.done():
            task.cancel()

    def setup(self):
        @self.driver.on_shutdown
        async def _():
            for task in self.tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
