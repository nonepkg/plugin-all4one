import json
import time
import asyncio
from typing import List

from pydantic import parse_obj_as
from nonebot.adapters import Event
from nonebot import get_bot, get_driver
from nonebot.adapters.onebot.v12.message import Message
from nonebot.adapters.onebot.v12 import PrivateMessageEvent
from nonebot.drivers import (
    URL,
    Request,
    Response,
    ForwardDriver,
    ReverseDriver,
    HTTPServerSetup,
)

driver = get_driver()
tasks: List[asyncio.Task] = []
events = []


async def handle_http(request: Request) -> Response:
    # TODO
    return Response(200)


if isinstance(driver, ReverseDriver):
    driver.setup_http_server(
        HTTPServerSetup(
            URL("/obimpl/"),
            "POST",
            "OneBotImpl",
            handle_http,
        )
    )

if isinstance(driver, ForwardDriver):

    @driver.on_startup
    async def _():
        async def post():
            while True:
                try:
                    event = events.pop()
                    print(event)
                    request = Request(
                        "POST",
                        f"http://127.0.0.1:4000/onebot/v12/http/",
                        headers={"X-OneBot-Version": "12", "X-Impl": "NoneBot"},
                        json=event,
                    )
                    print((await driver.request(request)).content)
                except IndexError:
                    pass
                except Exception as e:
                    print(e)
                await asyncio.sleep(0.01)

        tasks.append(asyncio.create_task(post()))

    @driver.on_shutdown
    async def _():
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
