import datetime
from typing import Union
from base64 import b64encode
from functools import partial

import msgpack
from nonebot.adapters.onebot.v12 import Event
from pydantic.json import custom_pydantic_encoder


def timestamp(obj: datetime.datetime):
    return obj.timestamp()


def encode_bytes(obj: bytes):
    return b64encode(obj).decode()


# https://12.onebot.dev/connect/data-protocol/basic-types/
msgpack_type_encoders = {
    datetime.datetime: timestamp,
}
json_type_encoders = {
    datetime.datetime: timestamp,
    bytes: encode_bytes,
}

msgpack_encoder = partial(custom_pydantic_encoder, msgpack_type_encoders)  # type: ignore
json_encoder = partial(custom_pydantic_encoder, json_type_encoders)  # type: ignore


def encode_event(event: Event, enable_msgpack: bool) -> Union[str, bytes]:
    """编码事件

    根据配置决定是否使用 msgpack 编码事件
    """
    if enable_msgpack:
        return msgpack.packb(event.dict(), default=msgpack_encoder)  # type: ignore
    else:
        return event.json(encoder=json_encoder)
