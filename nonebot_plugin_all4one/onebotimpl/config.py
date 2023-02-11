from enum import Enum
from typing import Literal

from pydantic import AnyUrl, BaseModel
from nonebot.adapters.onebot.v12.config import WSUrl


class ConnectionType(str, Enum):
    HTTP = "http"
    HTTP_WEBHOOK = "http_webhook"
    WEBSOCKET = "websocket"
    WEBSOCKET_REV = "websocket_rev"


class ConnectionConfig(BaseModel):
    type: ConnectionType
    access_token: str = ""
    self_id_prefix: bool = False

    class Config:
        extra = "ignore"


class HTTPConfig(ConnectionConfig):
    type: Literal[ConnectionType.HTTP]
    event_enabled: bool = False
    event_buffer_size: int = 16


class HTTPWebhookConfig(ConnectionConfig):
    type: Literal[ConnectionType.HTTP_WEBHOOK]
    url: AnyUrl
    timeout: int = 4


class WebsocketConfig(ConnectionConfig):
    type: Literal[ConnectionType.WEBSOCKET]


class WebsocketReverseConfig(ConnectionConfig):
    type: Literal[ConnectionType.WEBSOCKET_REV]
    url: WSUrl
    reconnect_interval: int = 4
