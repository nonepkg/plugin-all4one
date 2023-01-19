from enum import Enum
from typing import Set, List, Union, Literal, Optional

from pydantic import AnyUrl, BaseModel
from nonebot.adapters.onebot.v12.config import WSUrl


class ConnectionType(str, Enum):
    HTTP = "http"
    HTTP_WEBHOOK = "http_webhook"
    WEBSOCKET = "websocket"
    WEBSOCKET_REV = "websocket_rev"


class HTTPConfig(BaseModel):
    type: Literal[ConnectionType.HTTP]
    access_token: str = ""
    event_enabled: bool = True
    event_buffer_size: int = 16


class HTTPWebhookConfig(BaseModel):
    type: Literal[ConnectionType.HTTP_WEBHOOK]
    url: AnyUrl
    timeout: int = 4


class WebsocketConfig(BaseModel):
    type: Literal[ConnectionType.WEBSOCKET]
    access_token: str = ""


class WebsocketReverseConfig(BaseModel):
    type: Literal[ConnectionType.WEBSOCKET_REV]
    url: WSUrl
    access_token: str = ""
    reconnect_interval: int = 4


class Config(BaseModel):
    """OneBot 实现配置类。"""

    obimpl_connections: Optional[
        List[
            Union[
                HTTPConfig, HTTPWebhookConfig, WebsocketConfig, WebsocketReverseConfig
            ]
        ]
    ] = None
    raise_ignored_exception: bool = True
    skip_plugins: Optional[Set[str]] = None

    class Config:
        extra = "ignore"
