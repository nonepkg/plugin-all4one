from hashlib import sha256
from base64 import b64decode
from typing import Dict, Optional

from anyio import open_file
from httpx import AsyncClient
from nonebot.adapters.onebot.v12 import BadParam
from sqlmodel import JSON, Field, Column, select
from nonebot.adapters.onebot.v12.exception import DatabaseError
from nonebot_plugin_datastore import create_session, get_plugin_data

plugin_data = get_plugin_data()
Model = plugin_data.Model


def get_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


class File(Model, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    src: Optional[str] = None
    src_id: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    path: str
    sha256: str


DATA_PATH = plugin_data.data_dir
FILE_PATH = DATA_PATH / "file"
FILE_PATH.mkdir(parents=True, exist_ok=True)


async def get_file(file_id: str, src: Optional[str] = None) -> File:
    async with create_session() as session:
        statement = select(File).where(File.sha256 == file_id).where(File.src == src)
        result = await session.execute(statement)
        if file := result.first():
            return file[0]
        else:
            result = await session.execute(select(File).where(File.sha256 == file_id))
            if file := result.first():
                return file[0]
            else:
                raise DatabaseError("failed", 31001, "file not found", {})


async def upload_file(
    type: str,
    name: str,
    src: Optional[str] = None,
    src_id: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    path: Optional[str] = None,
    data: Optional[bytes] = None,
    sha256: Optional[str] = None,
) -> str:
    if type == "url":
        if url is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="url must be provided when type is url",
                data={},
            )
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.content
    elif type == "path":
        if path is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="path must be provided when type is path",
                data={},
            )
        async with await open_file(path, "rb") as f:
            data = await f.read()
    elif type == "data":
        if data is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="data must be provided when type is data",
                data={},
            )
        # 如果是 JSON 格式，bytes 编码为 base64
        # https://12.onebot.dev/connect/data-protocol/basic-types/#_5
        if isinstance(data, str):
            data = b64decode(data)
    else:
        raise BadParam(
            status="failed",
            retcode=10003,
            message="type must be url, path or data",
            data={},
        )
    if sha256 is None:
        sha256 = get_sha256(data)
    if path is None:
        path = str(FILE_PATH / sha256)
        async with await open_file(path, "wb") as f:
            await f.write(data)
    file = File(
        name=name,
        src=src,
        src_id=src_id,
        url=url,
        headers=headers,
        path=path,
        sha256=sha256,
    )
    async with create_session() as session, session.begin():
        session.add(file)
    return sha256
