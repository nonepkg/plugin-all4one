import json
import datetime
from base64 import b64encode
from functools import partial
from typing import Any, Dict, Union

import msgpack
from nonebot.adapters.onebot.v12 import Event
from pydantic.json import custom_pydantic_encoder
from nonebot.adapters.onebot.v12.utils import CustomEncoder


def timestamp(obj: datetime.datetime):
    return obj.timestamp()


def encode_bytes(obj: bytes):
    return b64encode(obj).decode()


# https://12.onebot.dev/connect/data-protocol/basic-types/
msgpack_type_encoders = {
    datetime.datetime: timestamp,
}

msgpack_encoder = partial(custom_pydantic_encoder, msgpack_type_encoders)  # type: ignore


def encode_data(data: Dict, use_msgpack: bool) -> Union[str, bytes]:
    """编码数据"""
    if use_msgpack:
        return msgpack.packb(data, default=msgpack_encoder)  # type: ignore
    else:
        return json.dumps(data, cls=CustomEncoder)
