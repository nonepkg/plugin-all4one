from enum import Enum
from typing import Set, Optional

from pydantic import AnyUrl, BaseModel


class Type(Enum):
    HTTP = "http"
    HTTP_WEBHOOK = "http_webhook"
    WEBSOCKET = "websocket"
    WEBSOCKET_REV = "websocket_rev"


class ConnectionConfig(BaseModel):
    type: Type
    url: Optional[AnyUrl]
    access_token: str = ""
    event_enabled: bool = True
    event_buffer_size: int = 16
    timeout: int = 4
    reconnect_interval = 4


class Config(BaseModel):
    """OneBot 实现配置类。"""

    obimpl_connections: Optional[Set[ConnectionConfig]] = None

    class Config:
        extra = "ignore"
