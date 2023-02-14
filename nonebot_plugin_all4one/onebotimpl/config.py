from enum import Enum
from typing import Set, List, Union, Literal, Optional

from pydantic import AnyUrl, BaseModel
from nonebot.adapters.onebot.v12.config import WSUrl


class ConnectionType(str, Enum):
    HTTP = "http"
    HTTP_WEBHOOK = "http_webhook"
    WEBSOCKET = "websocket"
    WEBSOCKET_REV = "websocket_rev"


class BaseConnectionConfig(BaseModel):
    type: ConnectionType
    access_token: str = ""
    self_id_prefix: bool = False

    class Config:
        extra = "ignore"


class HTTPConfig(BaseConnectionConfig):
    type: Literal[ConnectionType.HTTP]
    event_enabled: bool = False
    event_buffer_size: int = 16


class HTTPWebhookConfig(BaseConnectionConfig):
    type: Literal[ConnectionType.HTTP_WEBHOOK]
    url: AnyUrl
    timeout: int = 4


class WebsocketConfig(BaseConnectionConfig):
    type: Literal[ConnectionType.WEBSOCKET]


class WebsocketReverseConfig(BaseConnectionConfig):
    type: Literal[ConnectionType.WEBSOCKET_REV]
    url: WSUrl
    reconnect_interval: int = 4


class Config(BaseModel):
    obimpl_connections: List[
        Union[HTTPConfig, HTTPWebhookConfig, WebsocketConfig, WebsocketReverseConfig]
    ] = []
    middlewares: Optional[Set[str]] = None

    class Config:
        extra = "ignore"
