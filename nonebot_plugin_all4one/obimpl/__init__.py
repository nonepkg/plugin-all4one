import json
import uuid
import asyncio
from typing import Any, Dict
from datetime import datetime
from functools import partial

import msgpack
from nonebot import Driver
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from pydantic.json import pydantic_encoder
from nonebot.exception import WebSocketClosed
from nonebot.adapters.onebot.v12.event import ImplVersion, ConnectMetaEvent
from nonebot.drivers import (
    URL,
    Request,
    Response,
    WebSocket,
    ForwardDriver,
    ReverseDriver,
    HTTPServerSetup,
    WebSocketServerSetup,
)

from ..middlewares import Middleware, _middlewares


class OneBotImplementation:
    def __init__(self, driver: Driver, **kwargs: Any):
        self.driver: Driver = driver
        self.middleswares: Dict[str, Middleware] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.setup()

    async def _ws_send(self, middleware: Middleware, websocket: WebSocket) -> None:
        try:
            while True:
                try:
                    event = middleware.events.pop()
                    await websocket.send(event.json())
                except IndexError:
                    pass
                await asyncio.sleep(0.01)
        except WebSocketClosed as e:
            logger.log(
                "ERROR",
                "<r><bg #f8bbd0>WebSocket Closed</bg #f8bbd0></r>",
                e,
            )
        except Exception as e:
            logger.log(
                "ERROR",
                "<r><bg #f8bbd0>Error while process data from websocket"
                ". Trying to reconnect...</bg #f8bbd0></r>",
                e,
            )

    async def _ws_recv(self, middleware: Middleware, websocket: WebSocket) -> None:
        try:
            while True:
                raw_data = await websocket.receive()
                data = (
                    json.loads(raw_data)
                    if isinstance(raw_data, str)
                    else msgpack.unpackb(raw_data)
                )
                resp = await getattr(middleware, data["action"])(**data["params"])
                resp = {"status": "ok", "retcode": 0, "data": resp, "message": ""}
                if "echo" in data:
                    resp["echo"] = data["echo"]
                await websocket.send(json.dumps(resp))
        except WebSocketClosed:
            logger.log(
                "WARNING",
                f"WebSocket for Bot {escape_tag(middleware.bot.self_id)} closed by peer",
            )
        except Exception as e:
            logger.log(
                "ERROR",
                "<r><bg #f8bbd0>Error while process data from websocket "
                f"for bot {escape_tag(middleware.bot.self_id)}.</bg #f8bbd0></r>",
                e,
            )

    async def _handle_http(self, middleware: Middleware, request: Request) -> Response:
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

    async def _handle_ws(self, middleware: Middleware, websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send(
            ConnectMetaEvent(
                id=uuid.uuid4().hex,
                time=datetime.now(),
                type="meta",
                detail_type="connect",
                sub_type="",
                version=ImplVersion(**await middleware.get_version()),
            ).json()
        )
        t1 = asyncio.create_task(self._ws_send(middleware, websocket))
        t2 = asyncio.create_task(self._ws_recv(middleware, websocket))
        while not (t1.done() or t2.done()):
            await asyncio.sleep(0.01)

    def bot_connect(self, bot: Bot) -> None:
        middleware = _middlewares[bot.type](bot)
        self.middleswares[bot.self_id] = middleware
        if isinstance(self.driver, ReverseDriver):
            self.driver.setup_http_server(
                HTTPServerSetup(
                    URL(f"/obimpl/{bot.self_id}/"),
                    "POST",
                    "OneBotImpl",
                    partial(self._handle_http, middleware),
                )
            )
            self.driver.setup_websocket_server(
                WebSocketServerSetup(
                    URL(f"/obimpl/{bot.self_id}/"),
                    "OneBotImpl",
                    partial(self._handle_ws, middleware),
                )
            )
        if isinstance(self.driver, ForwardDriver):
            # self.tasks[bot.self_id] = asyncio.create_task(
            #    self._http_webhook(middleware)
            # )
            self.tasks[bot.self_id] = asyncio.create_task(
                self._websocket_rev(
                    middleware, URL("ws://127.0.0.1:4000/onebot/v12/ws")
                )
            )

    async def _http_webhook(self, middleware: Middleware, url: URL):
        while True:
            try:
                event = middleware.events.pop()
                if event.type == "meta":
                    continue
                request = Request(
                    "POST",
                    url,
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

    async def _websocket_rev(self, middleware: Middleware, url: URL) -> None:
        req = Request(
            "GET",
            url,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "OneBot/12 NoneBot Plugin All4One/0.1.0",
                "Sec-WebSocket-Protocol": "12.nonebot-plugin-all4one",
            },
            timeout=30.0,
        )
        while True:
            try:
                async with self.driver.websocket(req) as ws:  # type:ignore
                    try:
                        await ws.send(
                            ConnectMetaEvent(
                                id=uuid.uuid4().hex,
                                time=datetime.now(),
                                type="meta",
                                detail_type="connect",
                                sub_type="",
                                version=ImplVersion(**await middleware.get_version()),
                            ).json()
                        )
                        t1 = asyncio.create_task(self._ws_send(middleware, ws))
                        t2 = asyncio.create_task(self._ws_recv(middleware, ws))
                        while not (t1.done() or t2.done()):
                            await asyncio.sleep(0.01)
                    except WebSocketClosed as e:
                        logger.log(
                            "ERROR",
                            "<r><bg #f8bbd0>WebSocket Closed</bg #f8bbd0></r>",
                            e,
                        )
                    except Exception as e:
                        logger.log(
                            "ERROR",
                            "<r><bg #f8bbd0>Error while process data from websocket"
                            f"{escape_tag(str(url))}. Trying to reconnect...</bg #f8bbd0></r>",
                            e,
                        )
            except Exception as e:
                logger.log(
                    "ERROR",
                    "<r><bg #f8bbd0>Error while setup websocket to "
                    f"{escape_tag(str(url))}. Trying to reconnect...</bg #f8bbd0></r>",
                    e,
                )

            await asyncio.sleep(3.0)  # TODO 配置

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
