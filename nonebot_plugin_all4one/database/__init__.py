from hashlib import sha256
from base64 import b64decode
from uuid import UUID, uuid4
from typing import Dict, Union, Optional, cast

from anyio import open_file
from httpx import AsyncClient
from sqlmodel import JSON, Field, Column, select
from nonebot.adapters.onebot.v12.exception import DatabaseError
from nonebot_plugin_datastore import create_session, get_plugin_data

plugin_data = get_plugin_data()
Model = plugin_data.Model


def get_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


class File(Model, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    src: Optional[str] = None
    src_id: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    path: Optional[str] = None
    sha256: Optional[str] = None


DATA_PATH = plugin_data.data_dir
FILE_PATH = DATA_PATH / "file"
FILE_PATH.mkdir(parents=True, exist_ok=True)


async def get_file(file_id: str, src: Optional[str] = None) -> File:
    async with create_session() as session:
        file = (
            await session.execute(select(File).where(File.id == file_id))
        ).one_or_none()
        if file:
            file = cast(File, file[0])
            if src is None:
                if file.sha256:
                    return file
            else:
                if file.src == src:
                    return file
                else:
                    if file.sha256:
                        if file_ := (
                            await session.execute(
                                select(File).where(
                                    File.sha256 == file.sha256, File.src == src
                                )
                            )
                        ).first():
                            return file_[0]
                        else:
                            file.src = src
                            file.src_id = None
                            return file

        raise DatabaseError("failed", 31001, "file not found", {})


async def upload_file(
    name: str,
    src: Optional[str] = None,
    src_id: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    path: Optional[str] = None,
    data: Optional[Union[str, bytes]] = None,
    sha256: Optional[str] = None,
) -> str:
    if src and src_id:
        async with create_session() as session:
            if file := (
                await session.execute(
                    select(File).where(File.src == src).where(File.src_id == src_id)
                )
            ).first():
                return file[0].id.hex
    if sha256:
        async with create_session() as session, session.begin():
            if file := (
                await session.execute(select(File).where(File.sha256 == sha256))
            ).first():
                file = File(
                    name=name,
                    src=src,
                    src_id=src_id,
                    url=file[0].url,
                    headers=file[0].headers,
                    path=file[0].path,
                    sha256=sha256,
                )
                session.add(file)
                return file.id.hex

    if path:
        async with await open_file(path, "rb") as f:
            data = await f.read()
    elif url:
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.content
    if data:
        # 如果是 JSON 格式，bytes 编码为 base64
        # https://12.onebot.dev/connect/data-protocol/basic-types/#_5
        if isinstance(data, str):
            data = b64decode(data)
        sha256 = get_sha256(data)
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
        return file.id.hex
