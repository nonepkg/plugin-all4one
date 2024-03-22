from typing import Optional

from pydantic import BaseModel


class Config(BaseModel):
    block_event: bool = True
    blocked_plugins: Optional[set[str]] = None

    class Config:
        extra = "ignore"
