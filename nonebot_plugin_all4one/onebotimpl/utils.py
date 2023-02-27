import datetime
from typing import Union
from base64 import b64encode
from functools import partial

import msgpack
from nonebot.adapters.onebot.v12 import Event
from pydantic.json import custom_pydantic_encoder

from .. import a4o_config


def timestamp(obj: datetime.datetime):
    return obj.timestamp()


def encode_bytes(obj: bytes):
    if a4o_config.enable_msgpack:
        return obj
    else:
        return b64encode(obj).decode()


# https://12.onebot.dev/connect/data-protocol/basic-types/
type_encoders = {
    datetime.datetime: timestamp,
    bytes: encode_bytes,
}

encoder = partial(custom_pydantic_encoder, type_encoders)  # type: ignore


def encode_event(event: Event) -> Union[str, bytes]:
    """编码事件

    根据配置决定是否使用 msgpack 编码事件
    """
    if a4o_config.enable_msgpack:
        return msgpack.packb(event.dict(), default=encoder)  # type: ignore
    else:
        return event.json(encoder=encoder)
