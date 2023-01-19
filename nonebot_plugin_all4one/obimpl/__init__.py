import json
import uuid
import asyncio
from datetime import datetime
from functools import partial
from contextlib import asynccontextmanager
from typing import Dict, Optional, AsyncGenerator, cast

import msgpack
from nonebot import Driver
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from pydantic.json import pydantic_encoder
from nonebot.exception import WebSocketClosed
from nonebot.adapters.onebot.utils import get_auth_bearer
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
from .config import (
    Config,
    HTTPConfig,
    WebsocketConfig,
    HTTPWebhookConfig,
    WebsocketReverseConfig,
)


class OneBotImplementation:
    def __init__(self, driver: Driver):
        self.driver = driver
        self.config = Config(**self.driver.config.dict())
        self.middleswares: Dict[str, Middleware] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.setup()

    def setup_http_server(self, setup: HTTPServerSetup):
        """设置一个 HTTP 服务器路由配置"""
        if not isinstance(self.driver, ReverseDriver):
            raise TypeError("Current driver does not support http server")
        self.driver.setup_http_server(setup)

    def setup_websocket_server(self, setup: WebSocketServerSetup):
        """设置一个 WebSocket 服务器路由配置"""
        if not isinstance(self.driver, ReverseDriver):
            raise TypeError("Current driver does not support websocket server")
        self.driver.setup_websocket_server(setup)

    async def request(self, setup: Request) -> Response:
        """进行一个 HTTP 客户端请求"""
        if not isinstance(self.driver, ForwardDriver):
            raise TypeError("Current driver does not support http client")
        return await self.driver.request(setup)

    @asynccontextmanager
    async def websocket(self, setup: Request) -> AsyncGenerator[WebSocket, None]:
        """建立一个 WebSocket 客户端连接请求"""
        if not isinstance(self.driver, ForwardDriver):
            raise TypeError("Current driver does not support websocket client")
        async with self.driver.websocket(setup) as ws:
            yield ws

    def _check_access_token(
        self, request: Request, access_token: str
    ) -> Optional[Response]:
        token = get_auth_bearer(request.headers.get("Authorization"))
        if token is None:
            token = request.url.query.get("access_token")

        if access_token and access_token != token:
            msg = (
                "Authorization Header is invalid"
                if token
                else "Missing Authorization Header"
            )
            return Response(401, content=msg)

    async def _ws_send(self, middleware: Middleware, websocket: WebSocket) -> None:
        try:
            while True:
                try:
                    event = middleware.events.pop()
                    await websocket.send(event.json())
                except IndexError:
                    pass
                await asyncio.sleep(0.05)
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
                resp = (
                    json.dumps(resp)
                    if isinstance(raw_data, str)
                    else msgpack.packb(resp)
                )
                await websocket.send(resp)  # type:ignore
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

    async def _handle_http(
        self, middleware: Middleware, conn: HTTPConfig, request: Request
    ) -> Response:
        if response := self._check_access_token(request, conn.access_token):
            return response
        try:
            if request.content:
                if request.headers.get("Content-Type") == "application/msgpack":
                    data = msgpack.unpackb(request.content)
                elif request.headers.get("Content-Type") == "application/json":
                    data = json.loads(request.content)
                else:
                    return Response(415, content="Invalid Content-Type")
                resp = await getattr(middleware, data["action"])(**data["params"])
                resp = {"status": "ok", "retcode": 0, "data": resp, "message": ""}
                if "echo" in data:
                    resp["echo"] = data["echo"]
                if request.headers.get("Content-Type") == "application/json":
                    return Response(200, content=json.dumps(resp))
                else:
                    return Response(200, content=msgpack.packb(resp))
        except Exception as e:
            print(e)
        return Response(204)

    async def _handle_ws(
        self, middleware: Middleware, conn: WebsocketConfig, websocket: WebSocket
    ) -> None:
        if response := self._check_access_token(websocket.request, conn.access_token):
            content = cast(str, response.content)
            await websocket.close(1008, content)
            return
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
        if self.config.obimpl_connections:
            for conn in self.config.obimpl_connections:
                if isinstance(conn, HTTPConfig):
                    self.setup_http_server(
                        HTTPServerSetup(
                            URL(f"/obimpl/{bot.self_id}/"),
                            "POST",
                            "OneBotImpl",
                            partial(self._handle_http, middleware, conn),
                        )
                    )
                elif isinstance(conn, HTTPWebhookConfig):
                    self.tasks[bot.self_id] = asyncio.create_task(
                        self._http_webhook(middleware, conn)
                    )
                elif isinstance(conn, WebsocketConfig):
                    self.setup_websocket_server(
                        WebSocketServerSetup(
                            URL(f"/obimpl/{bot.self_id}/"),
                            "OneBotImpl",
                            partial(self._handle_ws, middleware, conn),
                        )
                    )
                elif isinstance(conn, WebsocketReverseConfig):
                    self.tasks[bot.self_id] = asyncio.create_task(
                        self._websocket_rev(middleware, conn)
                    )

    async def _http_webhook(self, middleware: Middleware, conn: HTTPWebhookConfig):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OneBot/12 NoneBot Plugin All4One/0.1.0",
            "X-OneBot-Version": "12",
            "X-Impl": "nonebot-plugin-all4one",
        }
        if conn.access_token:
            headers["Authorization"] = f"Bearer {conn.access_token}"
        while True:
            try:
                event = middleware.events.pop()
                request = Request(
                    "POST",
                    conn.url,
                    headers=headers,
                    content=event.json(
                        encoder=lambda v: int(v.timestamp())
                        if isinstance(v, datetime)
                        else pydantic_encoder(v)
                    ),
                )
                resp = await self.request(request)
                if resp.status_code == 200:
                    if resp.content:
                        if resp.headers.get("Content-Type") == "application/msgpack":
                            data = msgpack.unpackb(resp.content)
                        elif resp.headers.get("Content-Type") == "application/json":
                            data = json.loads(resp.content)
                        else:
                            logger.exception("Invalid Content-Type")
                            continue
                        for action in data:
                            await getattr(middleware, action["action"])(
                                **action["params"]
                            )
            except IndexError:
                pass
            except Exception as e:
                print(e)
            await asyncio.sleep(0.01)

    async def _websocket_rev(
        self, middleware: Middleware, conn: WebsocketReverseConfig
    ) -> None:
        headers = {
            "User-Agent": "OneBot/12 NoneBot Plugin All4One/0.1.0",
            "Sec-WebSocket-Protocol": "12.nonebot-plugin-all4one",
        }
        if conn.access_token:
            headers["Authorization"] = f"Bearer {conn.access_token}"
        req = Request(
            "GET",
            conn.url,
            headers=headers,
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
                            f"{escape_tag(str(conn.url))}. Trying to reconnect...</bg #f8bbd0></r>",
                            e,
                        )
            except Exception as e:
                logger.log(
                    "ERROR",
                    "<r><bg #f8bbd0>Error while setup websocket to "
                    f"{escape_tag(str(conn.url))}. Trying to reconnect...</bg #f8bbd0></r>",
                    e,
                )
            await asyncio.sleep(conn.reconnect_interval)

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
