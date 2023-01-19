from typing import Set, List, Optional

from pydantic import BaseModel

from .obimpl.config import ConnectionConfig


class Config(BaseModel):
    obimpl_connections: Optional[List[ConnectionConfig]] = None
    middlewares: Optional[Set[str]] = None
    self_id_prefix: bool = True
    block_event: bool = True
    blocked_plugins: Optional[Set[str]] = None

    class Config:
        extra = "ignore"
