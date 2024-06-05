import json
import datetime
from typing import Union
from base64 import b64encode
from functools import partial

import msgpack
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

msgpack_encoder = partial(custom_pydantic_encoder, msgpack_type_encoders)
json_encoder = partial(custom_pydantic_encoder, json_type_encoders)


def encode_data(data: dict, use_msgpack: bool) -> Union[str, bytes]:
    """编码数据"""
    if use_msgpack:
        return msgpack.packb(data, default=msgpack_encoder)  # type: ignore
    else:
        return json.dumps(data, default=json_encoder)
