from typing import Set, List, Union, Optional

from pydantic import BaseModel

from .onebotimpl.config import (
    HTTPConfig,
    WebsocketConfig,
    HTTPWebhookConfig,
    WebsocketReverseConfig,
)


class Config(BaseModel):
    obimpl_connections: List[
        Union[HTTPConfig, HTTPWebhookConfig, WebsocketConfig, WebsocketReverseConfig]
    ] = []
    middlewares: Optional[Set[str]] = None
    block_event: bool = True
    blocked_plugins: Optional[Set[str]] = None

    class Config:
        extra = "ignore"
