import json
import uuid
import asyncio
import importlib
from datetime import datetime
from functools import partial
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Type, Union, Literal, Optional, AsyncGenerator, cast

import msgpack
from nonebot import Driver
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from pydantic.json import pydantic_encoder
from nonebot.adapters.onebot.v12 import Event
from nonebot.exception import WebSocketClosed
from nonebot.adapters.onebot.utils import get_auth_bearer
from nonebot.adapters.onebot.v12.exception import ActionFailedWithRetcode
from nonebot.adapters.onebot.v12.event import (
    Status,
    BotStatus,
    ImplVersion,
    ConnectMetaEvent,
)
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

from ..middlewares import MIDDLEWARE_MAP, Middleware
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
        self._middlewares: Dict[str, Type[Middleware]] = {}
        self.middlewares: Dict[str, Middleware] = {}
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

    def register_middleware(self, middleware: Type[Middleware]):
        """注册一个中间件"""
        name = middleware.get_name()
        if name in self._middlewares:
            logger.opt(colors=True).debug(
                f'Middleware "<y>{escape_tag(name)}</y>" already exists'
            )
            return
        self._middlewares[name] = middleware
        logger.opt(colors=True).debug(
            f'Succeeded to load middleware "<y>{escape_tag(name)}</y>"'
        )

    async def _call_api(self, middleware: Middleware, api: str, **kwargs: Any) -> Any:
        try:
            if api in (
                "get_latest_events",
                "get_supported_actions",
                "get_status",
                "get_version",
            ):
                resp = await getattr(self, api)(middleware=middleware, **kwargs)
            else:
                resp = await middleware._call_api(api, **kwargs)
            return {"status": "ok", "retcode": 0, "data": resp, "message": ""}
        except ActionFailedWithRetcode as e:
            return {
                "status": "failed",
                "retcode": e.retcode,
                "data": e.data,
                "message": e.message,
            }
        except Exception as e:
            logger.debug(e)

    async def get_latest_events(
        self,
        queue: asyncio.Queue[Event],
        *,
        limit: int = 0,
        timeout: int = 0,
        **kwargs: Any,
    ) -> List[Event]:
        """获取最新事件列表

        参数:
            limit: 获取的事件数量上限，0 表示不限制
            timeout: 没有事件时要等待的秒数，0 表示使用短轮询，不等待
            kwargs: 扩展字段
        """
        event_list = []
        if queue.empty():
            if timeout > 0:
                event_list.append(
                    await asyncio.wait_for(queue.get(), timeout),
                )
        else:
            if limit > 0:
                for _ in range(limit):
                    if not queue.empty():
                        event_list.append(await queue.get())
            else:
                while not queue.empty():
                    event_list.append(await queue.get())
        return event_list

    async def get_supported_actions(
        self, middleware: Middleware, **kwargs: Any
    ) -> List[str]:
        """获取支持的动作列表

        参数:
            kwargs: 扩展字段
        """
        return await middleware.get_supported_actions()

    async def get_status(self, middleware: Middleware, **kwargs: Any) -> Status:
        """获取运行状态

        参数:
            kwargs: 扩展字段
        """
        return Status(
            good=True, bots=[BotStatus(self=middleware.get_bot_self(), online=True)]
        )

    async def get_version(
        self,
        **kwargs: Any,
    ) -> Dict[Union[Literal["impl", "version", "onebot_version"], str], str]:
        """获取版本信息

        参数:
            kwargs: 扩展字段
        """
        return {
            "impl": "nonebot-plugin-all4one",
            "version": "0.1.0",
            "onebot_version": "12",
        }

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

    async def _ws_send(
        self, middleware: Middleware, websocket: WebSocket, self_id_prefix: bool = False
    ) -> None:
        queue = middleware.new_queue(self_id_prefix)
        try:
            while True:
                event = await queue.get()
                await websocket.send(event.json())
        except WebSocketClosed as e:
            logger.opt(colors=True).log(
                "ERROR",
                "<r><bg #f8bbd0>WebSocket Closed</bg #f8bbd0></r>",
                e,
            )
        except Exception as e:
            logger.opt(colors=True).log(
                "ERROR",
                "<r><bg #f8bbd0>Error while process data from websocket"
                ". Trying to reconnect...</bg #f8bbd0></r>",
                e,
            )
        finally:
            middleware.queues.remove(queue)

    async def _ws_recv(self, middleware: Middleware, websocket: WebSocket) -> None:
        try:
            while True:
                raw_data = await websocket.receive()
                data = (
                    json.loads(raw_data)
                    if isinstance(raw_data, str)
                    else msgpack.unpackb(raw_data)
                )
                resp = await self._call_api(
                    middleware, data["action"], **data["params"]
                )
                if "echo" in data:
                    resp["echo"] = data["echo"]
                resp = (
                    json.dumps(resp)
                    if isinstance(raw_data, str)
                    else msgpack.packb(resp)
                )
                await websocket.send(resp)  # type:ignore
        except WebSocketClosed:
            logger.opt(colors=True).log(
                "WARNING",
                f"WebSocket for Bot {escape_tag(middleware.self_id)} closed by peer",
            )
        except Exception as e:
            logger.opt(colors=True).log(
                "ERROR",
                "<r><bg #f8bbd0>Error while process data from websocket "
                f"for bot {escape_tag(middleware.self_id)}.</bg #f8bbd0></r>",
                e,
            )

    async def _handle_http(
        self,
        middleware: Middleware,
        queue: Optional[asyncio.Queue[Event]],
        conn: HTTPConfig,
        request: Request,
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
                resp = await self._call_api(
                    middleware,
                    data["action"],
                    queue=queue,
                    **data["params"],
                )
                if "echo" in data:
                    resp["echo"] = data["echo"]
                if request.headers.get("Content-Type") == "application/json":
                    return Response(200, content=json.dumps(resp))
                else:
                    return Response(200, content=msgpack.packb(resp))
        except Exception as e:
            logger.debug(e)
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
                version=ImplVersion(**await self.get_version()),
            ).json()
        )
        t1 = asyncio.create_task(
            self._ws_send(middleware, websocket, conn.self_id_prefix)
        )
        t2 = asyncio.create_task(self._ws_recv(middleware, websocket))
        await t2
        t1.cancel()

    async def bot_connect(self, bot: Bot) -> None:
        if (middleware := self._middlewares.get(bot.type, None)) is None:
            return
        middleware = middleware(bot)
        self.middlewares[bot.self_id] = middleware
        for conn in self.config.obimpl_connections:
            if isinstance(conn, HTTPConfig):
                queue = None
                if conn.event_enabled:
                    queue = middleware.new_queue(
                        conn.self_id_prefix, conn.event_buffer_size
                    )
                self.setup_http_server(
                    HTTPServerSetup(
                        URL(f"/obimpl/{middleware.self_id}/"),
                        "POST",
                        "OneBotImpl",
                        partial(self._handle_http, middleware, queue, conn),
                    )
                )
            elif isinstance(conn, HTTPWebhookConfig):
                middleware.tasks.append(
                    asyncio.create_task(self._http_webhook(middleware, conn))
                )
            elif isinstance(conn, WebsocketConfig):
                self.setup_websocket_server(
                    WebSocketServerSetup(
                        URL(f"/obimpl/{middleware.self_id}/"),
                        "OneBotImpl",
                        partial(self._handle_ws, middleware, conn),
                    )
                )
            elif isinstance(conn, WebsocketReverseConfig):
                middleware.tasks.append(
                    asyncio.create_task(self._websocket_rev(middleware, conn))
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
        queue = middleware.new_queue(conn.self_id_prefix)
        while True:
            try:
                event = await queue.get()
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
                            await self._call_api(
                                middleware, action["action"], **action["params"]
                            )
            except Exception as e:
                logger.debug(e)

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
                async with self.websocket(req) as ws:  # type:ignore
                    try:
                        await ws.send(
                            ConnectMetaEvent(
                                id=uuid.uuid4().hex,
                                time=datetime.now(),
                                type="meta",
                                detail_type="connect",
                                sub_type="",
                                version=ImplVersion(**await self.get_version()),
                            ).json()
                        )
                        t1 = asyncio.create_task(
                            self._ws_send(middleware, ws, conn.self_id_prefix)
                        )
                        t2 = asyncio.create_task(self._ws_recv(middleware, ws))
                        await t2
                        t1.cancel()
                    except WebSocketClosed as e:
                        logger.opt(colors=True).log(
                            "ERROR",
                            "<r><bg #f8bbd0>WebSocket Closed</bg #f8bbd0></r>",
                            e,
                        )
                    except Exception as e:
                        logger.opt(colors=True).log(
                            "ERROR",
                            "<r><bg #f8bbd0>Error while process data from websocket"
                            f"{escape_tag(str(conn.url))}. Trying to reconnect...</bg #f8bbd0></r>",
                            e,
                        )
            except Exception as e:
                logger.opt(colors=True).log(
                    "ERROR",
                    "<r><bg #f8bbd0>Error while setup websocket to "
                    f"{escape_tag(str(conn.url))}. Trying to reconnect...</bg #f8bbd0></r>",
                    e,
                )
            await asyncio.sleep(conn.reconnect_interval)

    async def bot_disconnect(self, bot: Bot) -> None:
        if (middleware := self.middlewares.pop(bot.self_id, None)) is None:
            return
        for task in middleware.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*middleware.tasks)

    def setup(self):
        @self.driver.on_startup
        async def _():
            adapters = (
                self.driver._adapters.keys()
                if self.config.middlewares is None
                else self.config.middlewares
            )

            for adapter in adapters:
                try:
                    if adapter in MIDDLEWARE_MAP:
                        module = importlib.import_module(
                            f"nonebot_plugin_all4one.middlewares.{MIDDLEWARE_MAP[adapter]}"
                        )
                        self.register_middleware(getattr(module, "Middleware"))
                    else:
                        logger.warning(f"Can not find middleware for Adapter {adapter}")
                except Exception as e:
                    logger.warning(
                        f"Can not load middleware for Adapter {adapter}: {e}"
                    )

        @self.driver.on_shutdown
        async def _():
            for middleware in self.middlewares.values():
                for task in middleware.tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*middleware.tasks, return_exceptions=True)

        @self.driver.on_bot_connect
        async def _(bot: Bot):
            if bot.self_id.startswith("a4o@"):
                return
            await self.bot_connect(bot)

        @self.driver.on_bot_disconnect
        async def _(bot: Bot):
            if bot.self_id.startswith("a4o@"):
                return
            await self.bot_disconnect(bot)
