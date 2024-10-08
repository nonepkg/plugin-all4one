import json
import uuid
from datetime import datetime
from functools import partial
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Union, Literal, ClassVar, Optional, cast
from asyncio import Task, Queue, sleep, gather, wait_for, create_task

import msgpack
from nonebot.adapters import Bot
from nonebot.utils import escape_tag
from nonebot.exception import WebSocketClosed
from nonebot.adapters.onebot.utils import get_auth_bearer
from nonebot.adapters.onebot.v12 import Event, StatusUpdateMetaEvent
from nonebot.adapters.onebot.v12.exception import (
    WhoAmI,
    UnknownSelf,
    ActionFailedWithRetcode,
)
from nonebot.adapters.onebot.v12.event import (
    Status,
    BotStatus,
    ImplVersion,
    ConnectMetaEvent,
)
from nonebot.drivers import (
    URL,
    Driver,
    Request,
    Response,
    ASGIMixin,
    WebSocket,
    HTTPClientMixin,
    HTTPServerSetup,
    WebSocketClientMixin,
    WebSocketServerSetup,
)

from ..logger import log
from .utils import encode_data
from ..__version__ import __version__
from ..middlewares import MIDDLEWARE_MAP, Middleware
from .config import (
    Config,
    HTTPConfig,
    WebsocketConfig,
    HTTPWebhookConfig,
    WebsocketReverseConfig,
)


class OneBotImplementation:
    USER_AGENT: ClassVar[str] = f"OneBot4All NoneBot-Plugin-All4One/{__version__}"
    ONEBOT_VERSION: ClassVar[str] = "A"
    IMPL_NAME: ClassVar[str] = "nonebot-plugin-all4one"

    def __init__(self, driver: Driver):
        self.driver = driver
        self.config = Config(**self.driver.config.model_dump())
        self.tasks: list[Task] = []
        self.queues: list[Queue[Event]] = []
        self._middlewares: dict[str, type[Middleware]] = {}
        self.middlewares: dict[str, Middleware] = {}
        self.setup()

    def setup_http_server(self, setup: HTTPServerSetup):
        """设置一个 HTTP 服务器路由配置"""
        if not isinstance(self.driver, ASGIMixin):
            raise TypeError("Current driver does not support http server")
        self.driver.setup_http_server(setup)

    def setup_websocket_server(self, setup: WebSocketServerSetup):
        """设置一个 WebSocket 服务器路由配置"""
        if not isinstance(self.driver, ASGIMixin):
            raise TypeError("Current driver does not support websocket server")
        self.driver.setup_websocket_server(setup)

    async def request(self, setup: Request) -> Response:
        """进行一个 HTTP 客户端请求"""
        if not isinstance(self.driver, HTTPClientMixin):
            raise TypeError("Current driver does not support http client")
        return await self.driver.request(setup)

    @asynccontextmanager
    async def websocket(self, setup: Request) -> AsyncGenerator[WebSocket, None]:
        """建立一个 WebSocket 客户端连接请求"""
        if not isinstance(self.driver, WebSocketClientMixin):
            raise TypeError("Current driver does not support websocket client")
        async with self.driver.websocket(setup) as ws:
            yield ws

    def register_middleware(self, middleware: type[Middleware]):
        """注册一个中间件"""
        name = middleware.get_name()
        if name in self._middlewares:
            log("WARNING", f'Middleware "<y>{escape_tag(name)}</y>" already exists')
            return
        self._middlewares[name] = middleware
        log("INFO", f'Succeeded to load middleware "<y>{escape_tag(name)}</y>"')

    async def _call_api(self, data: dict[str, Any]) -> Any:
        try:
            if (api := data["action"]) in (
                "get_latest_events",
                "get_status",
                "get_version",
            ):
                resp = await getattr(self, api)(**data)
            else:
                if bot_self := data.pop("self", None):
                    if middleware := self.middlewares.get(
                        bot_self.get("user_id", ""), None
                    ):
                        resp = await middleware._call_api(api, **data["params"])
                    else:
                        raise UnknownSelf("failed", 10102, "Unknown Self", {})
                else:
                    raise WhoAmI("failed", 10101, "Who Am I", {})
            return {"status": "ok", "retcode": 0, "data": resp, "message": ""}
        except ActionFailedWithRetcode as e:
            return {
                "status": "failed",
                "retcode": e.retcode,
                "data": e.data,
                "message": e.message,
            }

    async def get_latest_events(
        self,
        queue: Queue[Event],
        *,
        limit: int = 0,
        timeout: int = 0,
        **kwargs: Any,
    ) -> list[Event]:
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
                    await wait_for(queue.get(), timeout),
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
    ) -> list[str]:
        """获取支持的动作列表

        参数:
            kwargs: 扩展字段
        """
        return await middleware.get_supported_actions()

    async def get_status(self, **kwargs: Any) -> Status:
        """获取运行状态

        参数:
            kwargs: 扩展字段
        """
        return Status(
            good=True,
            bots=[
                BotStatus(self=await middleware.get_bot_self(), online=True)
                for middleware in self.middlewares.values()
            ],
        )

    async def get_version(
        self,
        **kwargs: Any,
    ) -> dict[Union[Literal["impl", "version", "onebot_version"], str], str]:
        """获取版本信息

        参数:
            kwargs: 扩展字段
        """
        return {
            "impl": self.IMPL_NAME,
            "version": __version__,
            "onebot_version": self.ONEBOT_VERSION,
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
        self,
        websocket: WebSocket,
        conn: Union[WebsocketConfig, WebsocketReverseConfig],
    ) -> None:
        queue = Queue[Event]()
        self.queues.append(queue)
        try:
            while True:
                event = await queue.get()
                await websocket.send(encode_data(event.model_dump(), conn.use_msgpack))
        except WebSocketClosed:
            log("WARNING", "<y>WebSocket Closed</y>")
        except Exception as e:
            log(
                "ERROR",
                "<r>Error while process data from websocket. "
                "Trying to reconnect...</r>",
                e,
            )
        finally:
            self.queues.remove(queue)

    async def _ws_recv(self, websocket: WebSocket) -> None:
        try:
            while True:
                echo = None
                raw_data = await websocket.receive()
                try:
                    data = (
                        json.loads(raw_data)
                        if isinstance(raw_data, str)
                        else msgpack.unpackb(raw_data)
                    )
                    if "echo" in data:
                        echo = data["echo"]
                    resp = await self._call_api(data)
                # 格式错误（包括实现不支持 MessagePack 的情况）、必要字段缺失或类型错误
                except (json.JSONDecodeError, msgpack.UnpackException):
                    resp = {
                        "status": "failed",
                        "retcode": 10001,
                        "data": None,
                        "message": "Invalid data format",
                    }
                # OneBot 实现内部发生了未捕获的意料之外的异常
                except Exception as e:
                    resp = {
                        "status": "failed",
                        "retcode": 20002,
                        "data": None,
                        "message": str(e),
                    }
                if echo is not None:
                    resp["echo"] = echo
                await websocket.send(encode_data(resp, isinstance(raw_data, bytes)))
        except WebSocketClosed:
            log("WARNING", "WebSocket closed by peer")
        # 与 WebSocket 服务器的连接发生了意料之外的错误
        except Exception as e:
            log(
                "ERROR",
                "<r>Error while process data from websocket</r>",
                e,
            )

    async def _handle_http(
        self,
        queue: Optional[Queue[Event]],
        conn: HTTPConfig,
        request: Request,
    ) -> Response:
        if response := self._check_access_token(request, conn.access_token):
            return response

        # 如果收到不支持的 Content-Type 请求头，必须返回 HTTP 状态码 415
        content_type = request.headers.get("Content-Type")
        if content_type not in ("application/json", "application/msgpack"):
            return Response(415, content="Invalid Content-Type")

        echo = None
        try:
            if request.content is None:
                raise ValueError("Empty request body")
            if content_type == "application/msgpack":
                data = msgpack.unpackb(request.content)
            else:
                data = json.loads(request.content)
            if "echo" in data:
                echo = data["echo"]
            data["params"]["queue"] = queue
            resp = await self._call_api(data)
        except (json.JSONDecodeError, msgpack.UnpackException, ValueError):
            resp = {
                "status": "failed",
                "retcode": 10001,
                "data": None,
                "message": "Invalid data format",
            }
        except Exception as e:
            resp = {
                "status": "failed",
                "retcode": 20002,
                "data": None,
                "message": str(e),
            }
        if echo is not None:
            resp["echo"] = echo
        return Response(
            200,
            headers={"Content-Type": content_type},
            content=encode_data(resp, content_type != "application/json"),
        )

    async def _handle_ws(self, conn: WebsocketConfig, websocket: WebSocket) -> None:
        if response := self._check_access_token(websocket.request, conn.access_token):
            content = cast(str, response.content)
            await websocket.close(1008, content)
            return
        await websocket.accept()
        await websocket.send(
            encode_data(
                ConnectMetaEvent(
                    id=uuid.uuid4().hex,
                    time=datetime.now(),
                    type="meta",
                    detail_type="connect",
                    sub_type="",
                    version=ImplVersion(**await self.get_version()),
                ).model_dump(),
                conn.use_msgpack,
            )
        )
        await websocket.send(
            encode_data(
                StatusUpdateMetaEvent(
                    id=uuid.uuid4().hex,
                    time=datetime.now(),
                    type="meta",
                    detail_type="status_update",
                    sub_type="",
                    status=await self.get_status(),
                ).model_dump(),
                conn.use_msgpack,
            )
        )
        t1 = create_task(self._ws_send(websocket, conn))
        t2 = create_task(self._ws_recv(websocket))
        await t2
        t1.cancel()

    async def _http_webhook(self, conn: HTTPWebhookConfig):
        headers = {
            "Content-Type": (
                "application/msgpack" if conn.use_msgpack else "application/json"
            ),
            "User-Agent": self.USER_AGENT,
            "X-OneBot-Version": self.ONEBOT_VERSION,
            "X-Impl": self.IMPL_NAME,
        }
        if conn.access_token:
            headers["Authorization"] = f"Bearer {conn.access_token}"
        queue = Queue[Event]()
        self.queues.append(queue)
        await queue.put(
            StatusUpdateMetaEvent(
                id=uuid.uuid4().hex,
                time=datetime.now(),
                type="meta",
                detail_type="status_update",
                sub_type="",
                status=await self.get_status(),
            )
        )
        while True:
            try:
                event = await queue.get()
                request = Request(
                    "POST",
                    str(conn.url),
                    headers=headers,
                    content=encode_data(event.model_dump(), conn.use_msgpack),
                )
                resp = await self.request(request)
                if resp.status_code == 200:
                    try:
                        if resp.content is None:
                            raise ValueError("Empty response body")
                        if (
                            content_type := resp.headers.get("Content-Type")
                        ) == "application/msgpack":
                            data = msgpack.unpackb(resp.content)
                        elif content_type == "application/json":
                            data = json.loads(resp.content)
                        else:
                            log("ERROR", "Invalid Content-Type")
                            continue
                        for action in data:
                            await self._call_api(action)
                    # 动作请求执行出错
                    except Exception as e:
                        log("ERROR", "HTTP Webhook Response action failed", e)
                # 事件推送成功，并不做更多处理
                elif resp.status_code == 204:
                    pass
                # 事件推送失败
                else:
                    log("ERROR", f"HTTP Webhook event push failed: {resp}")
            except (NotImplementedError, TypeError):
                log(
                    "ERROR",
                    f"Current driver {self.driver.type} does not support http client",
                )
                self.queues.remove(queue)
                break
            except Exception as e:
                log("ERROR", "HTTP Webhook event push failed", e)

    async def _websocket_rev(self, conn: WebsocketReverseConfig) -> None:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Sec-WebSocket-Protocol": f"{self.ONEBOT_VERSION}.{self.IMPL_NAME}",
        }
        if conn.access_token:
            headers["Authorization"] = f"Bearer {conn.access_token}"
        req = Request(
            "GET",
            str(conn.url),
            headers=headers,
            timeout=30.0,
        )
        while True:
            try:
                async with self.websocket(req) as ws:
                    try:
                        await ws.send(
                            encode_data(
                                ConnectMetaEvent(
                                    id=uuid.uuid4().hex,
                                    time=datetime.now(),
                                    type="meta",
                                    detail_type="connect",
                                    sub_type="",
                                    version=ImplVersion(**await self.get_version()),
                                ).model_dump(),
                                conn.use_msgpack,
                            )
                        )
                        await ws.send(
                            encode_data(
                                StatusUpdateMetaEvent(
                                    id=uuid.uuid4().hex,
                                    time=datetime.now(),
                                    type="meta",
                                    detail_type="status_update",
                                    sub_type="",
                                    status=await self.get_status(),
                                ).model_dump(),
                                conn.use_msgpack,
                            )
                        )
                        t1 = create_task(self._ws_send(ws, conn))
                        t2 = create_task(self._ws_recv(ws))
                        await t2
                        t1.cancel()
                    except WebSocketClosed:
                        log("WARNING", "<y>WebSocket Closed</y>")
                    except Exception as e:
                        log(
                            "ERROR",
                            "<r>Error while process data from websocket"
                            f"{escape_tag(str(conn.url))}. Trying to reconnect...</r>",
                            e,
                        )
            except (NotImplementedError, TypeError):
                log(
                    "ERROR",
                    f"Current driver {self.driver.type} "
                    "does not support websocket server",
                )
                break
            except Exception:
                log(
                    "WARNING",
                    "<y>Error while setup websocket to "
                    f"{escape_tag(str(conn.url))}. Trying to reconnect...</y>",
                )
            await sleep(conn.reconnect_interval)

    async def bot_connect(self, bot: Bot) -> None:
        if (middleware := self._middlewares.get(bot.type, None)) is None:
            return
        middleware = middleware(bot)
        self.middlewares[bot.self_id] = middleware
        for queue in self.queues:
            event = StatusUpdateMetaEvent(
                id=uuid.uuid4().hex,
                time=datetime.now(),
                type="meta",
                detail_type="status_update",
                sub_type="",
                status=Status(
                    good=True,
                    bots=[BotStatus(self=await middleware.get_bot_self(), online=True)],
                ),
            )
            await queue.put(event)

    async def bot_disconnect(self, bot: Bot) -> None:
        if (middleware := self.middlewares.pop(bot.self_id, None)) is None:
            return
        for queue in self.queues:
            event = StatusUpdateMetaEvent(
                id=uuid.uuid4().hex,
                time=datetime.now(),
                type="meta",
                detail_type="status_update",
                sub_type="",
                status=Status(
                    good=True,
                    bots=[
                        BotStatus(self=await middleware.get_bot_self(), online=False)
                    ],
                ),
            )
            await queue.put(event)

    def _register_middlewares(self, middlewares: Optional[set[str]] = None):
        if middlewares is None:
            middlewares = set(self.driver._adapters.keys())
        for middleware in middlewares:
            if middleware in MIDDLEWARE_MAP:
                self.register_middleware(MIDDLEWARE_MAP[middleware])
            else:
                log("ERROR", f"Can not find middleware for Adapter {middleware}")

    def setup(self):
        @self.driver.on_startup
        async def _():
            self._register_middlewares(self.config.middlewares)
            for conn in self.config.obimpl_connections:
                if isinstance(conn, HTTPConfig):
                    queue = None
                    if conn.event_enabled:
                        queue = Queue[Event](conn.event_buffer_size)
                    self.setup_http_server(
                        HTTPServerSetup(
                            URL("/all4one/"),
                            "POST",
                            "All4One",
                            partial(self._handle_http, queue, conn),
                        )
                    )
                elif isinstance(conn, HTTPWebhookConfig):
                    self.tasks.append(create_task(self._http_webhook(conn)))
                elif isinstance(conn, WebsocketConfig):
                    self.setup_websocket_server(
                        WebSocketServerSetup(
                            URL("/all4one/"),
                            "All4One",
                            partial(self._handle_ws, conn),
                        )
                    )
                elif isinstance(conn, WebsocketReverseConfig):
                    self.tasks.append(create_task(self._websocket_rev(conn)))

        @self.driver.on_shutdown
        async def _():
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            await gather(*self.tasks, return_exceptions=True)

        @self.driver.on_bot_connect
        async def _(bot: Bot):
            await self.bot_connect(bot)

        @self.driver.on_bot_disconnect
        async def _(bot: Bot):
            await self.bot_disconnect(bot)
