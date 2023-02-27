from typing import Set, Optional

from pydantic import BaseModel


class Config(BaseModel):
    block_event: bool = True
    blocked_plugins: Optional[Set[str]] = None
    enable_msgpack: bool = False

    class Config:
        extra = "ignore"
